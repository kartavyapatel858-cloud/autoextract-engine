"""Data models and type definitions for AutoExtract."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

ParserType = Literal["auto", "article", "catalog", "metadata", "json"]
ExportFormat = Literal["json", "csv", "markdown", "all"]


@dataclass
class ExtractionTarget:
    """Represents a URL or file resource to fetch and extract."""

    url: str
    parser_type: ParserType = "auto"
    headers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[float] = None

    def __post_init__(self) -> None:
        self.url = self.url.strip()


@dataclass
class ExtractedRecord:
    """Represents the standardized result of an extraction run."""

    target_url: str
    parser_type: str
    data: Dict[str, Any]
    status: Literal["success", "partial", "error"] = "success"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    raw_size_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a standard dictionary representation."""
        return {
            "target_url": self.target_url,
            "parser_type": self.parser_type,
            "status": self.status,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 2),
            "raw_size_bytes": self.raw_size_bytes,
            "errors": self.errors,
            "data": self.data,
        }


@dataclass
class EngineStats:
    """Aggregated execution metrics for the extraction run."""

    total_targets: int = 0
    successful: int = 0
    failed: int = 0
    total_bytes_downloaded: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time if self.end_time is not None else time.time()
        return max(0.001, end - self.start_time)

    @property
    def requests_per_second(self) -> float:
        return round(self.total_targets / self.elapsed_seconds, 2)

    @property
    def success_rate(self) -> float:
        if self.total_targets == 0:
            return 0.0
        return round((self.successful / self.total_targets) * 100, 2)

    def finish(self) -> None:
        """Mark completion timestamp."""
        self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_targets": self.total_targets,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate_percent": self.success_rate,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "requests_per_second": self.requests_per_second,
            "total_bytes_downloaded": self.total_bytes_downloaded,
        }


@dataclass
class RunConfig:
    """Runtime execution configuration."""

    concurrency: int = 4
    timeout: float = 10.0
    retries: int = 3
    backoff_factor: float = 0.5
    rate_limit: float = 10.0  # max requests per second
    user_agent: str = "AutoExtract/1.0 (+https://github.com/kartavyapatel858-cloud)"
    mock_responses: Optional[Dict[str, str]] = None
    verbose: bool = False

    def __post_init__(self) -> None:
        if self.concurrency < 1:
            raise ValueError("Concurrency must be at least 1")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.rate_limit <= 0:
            raise ValueError("Rate limit must be positive")


@dataclass
class ExportConfig:
    """Configuration for data export."""

    format: ExportFormat = "json"
    output_dir: Path = field(default_factory=lambda: Path("output"))
    base_filename: str = "extracted_data"
    pretty_json: bool = True
    include_metadata: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
