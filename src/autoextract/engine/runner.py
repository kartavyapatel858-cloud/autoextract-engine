"""
Concurrent Extraction Engine Coordinator.
Executes batch extractions with rate limiting, resilience, and metrics collection.
"""

from __future__ import annotations

import concurrent.futures
import time
from typing import Callable, Dict, List, Optional

from autoextract.core.exceptions import AutoExtractError
from autoextract.core.logging import setup_logger
from autoextract.core.models import (
    EngineStats,
    ExtractedRecord,
    ExtractionTarget,
    RunConfig,
)
from autoextract.engine.fetcher import ResourceFetcher
from autoextract.engine.rate_limiter import RateLimiter
from autoextract.parsers.base import BaseParser
from autoextract.parsers.html_parser import (
    ArticleExtractor,
    CatalogExtractor,
    MetadataExtractor,
)
from autoextract.parsers.json_parser import JSONParser


class ExtractionEngine:
    """
    High-performance, concurrent extraction runner.
    
    Orchestrates:
    - ThreadPool concurrency
    - Token-bucket rate limiting
    - Automatic parser detection and routing
    - Fault isolation & detailed telemetry
    """

    def __init__(self, config: Optional[RunConfig] = None) -> None:
        self.config = config or RunConfig()
        self.logger = setup_logger(verbose=self.config.verbose)
        self.rate_limiter = RateLimiter(requests_per_second=self.config.rate_limit)
        self.fetcher = ResourceFetcher(
            timeout=self.config.timeout,
            retries=self.config.retries,
            backoff_factor=self.config.backoff_factor,
            user_agent=self.config.user_agent,
            mock_responses=self.config.mock_responses,
        )

        # Register default parsers
        self.parsers: Dict[str, BaseParser] = {
            "article": ArticleExtractor(),
            "catalog": CatalogExtractor(),
            "metadata": MetadataExtractor(),
            "json": JSONParser(),
        }

    def register_parser(self, parser: BaseParser) -> None:
        """Register or override a custom parser."""
        self.parsers[parser.name] = parser

    def _detect_parser(self, content_type: str, raw_content: str) -> BaseParser:
        """Auto-detects the most suitable parser for raw payload."""
        # 1. JSON detection
        if self.parsers["json"].can_parse(content_type, raw_content):
            return self.parsers["json"]

        # 2. Catalog / E-commerce detection
        if self.parsers["catalog"].can_parse(content_type, raw_content):
            # Check if actual product cards exist
            try:
                res = self.parsers["catalog"].parse(raw_content)
                if res.get("item_count", 0) > 0:
                    return self.parsers["catalog"]
            except Exception:
                pass

        # 3. Article detection
        if self.parsers["article"].can_parse(content_type, raw_content):
            return self.parsers["article"]

        # 4. Fallback to general Metadata
        return self.parsers["metadata"]

    def extract_single(self, target: ExtractionTarget) -> ExtractedRecord:
        """Extract data from a single target resource."""
        self.rate_limiter.acquire()
        t0 = time.perf_counter()

        try:
            fetch_res = self.fetcher.fetch(
                target.url,
                custom_headers=target.headers,
                timeout_override=target.timeout,
            )

            # Resolve parser
            if target.parser_type == "auto":
                parser = self._detect_parser(fetch_res.content_type, fetch_res.content)
            else:
                parser = self.parsers.get(target.parser_type)
                if not parser:
                    parser = self._detect_parser(fetch_res.content_type, fetch_res.content)

            # Parse content
            parsed_data = parser.parse(fetch_res.content, target_url=target.url)
            duration_ms = (time.perf_counter() - t0) * 1000.0

            return ExtractedRecord(
                target_url=target.url,
                parser_type=parser.name,
                data=parsed_data,
                status="success",
                duration_ms=duration_ms,
                raw_size_bytes=fetch_res.byte_size,
            )

        except AutoExtractError as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.logger.warning("Extraction error for %s: %s", target.url, exc)
            return ExtractedRecord(
                target_url=target.url,
                parser_type=target.parser_type,
                data={},
                status="error",
                duration_ms=duration_ms,
                errors=[str(exc)],
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.logger.error("Unexpected error for %s: %s", target.url, exc, exc_info=True)
            return ExtractedRecord(
                target_url=target.url,
                parser_type=target.parser_type,
                data={},
                status="error",
                duration_ms=duration_ms,
                errors=[f"Unexpected error: {exc}"],
            )

    def run(
        self,
        targets: List[ExtractionTarget],
        progress_callback: Optional[Callable[[ExtractedRecord, int, int], None]] = None,
    ) -> tuple[List[ExtractedRecord], EngineStats]:
        """
        Executes parallel extraction across multiple targets.
        
        Args:
            targets: List of ExtractionTarget items to process.
            progress_callback: Optional callback invoked as each target finishes:
                               (record, completed_count, total_count)
                               
        Returns:
            Tuple of (list_of_extracted_records, engine_statistics)
        """
        stats = EngineStats(total_targets=len(targets))
        records: List[ExtractedRecord] = []

        if not targets:
            stats.finish()
            return records, stats

        completed_count = 0

        # Concurrent execution with ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.concurrency,
            thread_name_prefix="AutoExtractWorker",
        ) as executor:
            future_to_target = {
                executor.submit(self.extract_single, target): target for target in targets
            }

            for future in concurrent.futures.as_completed(future_to_target):
                record = future.result()
                records.append(record)
                completed_count += 1

                if record.status == "success":
                    stats.successful += 1
                else:
                    stats.failed += 1

                stats.total_bytes_downloaded += record.raw_size_bytes

                if progress_callback:
                    progress_callback(record, completed_count, len(targets))

        stats.finish()
        return records, stats
