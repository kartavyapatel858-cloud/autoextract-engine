"""
HTTP and Local Resource Fetcher.
Zero external dependencies, built on urllib.request with exponential retries.
"""

from __future__ import annotations

import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from autoextract.core.exceptions import NetworkError


@dataclass
class FetchResult:
    """Standardized response from resource fetching."""

    content: str
    status_code: int
    content_type: str
    url: str
    duration_ms: float
    byte_size: int


class ResourceFetcher:
    """
    Resilient HTTP and local filesystem resource fetcher.
    
    Includes:
    - Exponential backoff with jitter
    - Configurable retries and timeouts
    - Mock adapters for offline / zero-cost operation
    - Local file path resolution
    """

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 AutoExtract/1.0"
    )

    def __init__(
        self,
        timeout: float = 10.0,
        retries: int = 3,
        backoff_factor: float = 0.5,
        user_agent: Optional[str] = None,
        mock_responses: Optional[Dict[str, str]] = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.mock_responses = mock_responses or {}

    def fetch(
        self,
        url_or_path: str,
        custom_headers: Optional[Dict[str, str]] = None,
        timeout_override: Optional[float] = None,
    ) -> FetchResult:
        """
        Fetches resource content with automatic retry logic.
        Handles mock responses, local files, and remote HTTP(S) endpoints.
        """
        start = time.perf_counter()
        timeout = timeout_override if timeout_override is not None else self.timeout

        # 1. Check Mock Responses (for offline demos & unit tests)
        if url_or_path in self.mock_responses:
            mock_text = self.mock_responses[url_or_path]
            elapsed = (time.perf_counter() - start) * 1000.0
            return FetchResult(
                content=mock_text,
                status_code=200,
                content_type="text/html; charset=utf-8",
                url=url_or_path,
                duration_ms=elapsed,
                byte_size=len(mock_text.encode("utf-8")),
            )

        # 2. Check Local File Path (e.g. ./fixtures/sample.html or C:/...)
        path_candidate = Path(url_or_path.replace("file://", ""))
        if path_candidate.exists() and path_candidate.is_file():
            try:
                content = path_candidate.read_text(encoding="utf-8")
                elapsed = (time.perf_counter() - start) * 1000.0
                ct = "application/json" if path_candidate.suffix == ".json" else "text/html"
                return FetchResult(
                    content=content,
                    status_code=200,
                    content_type=ct,
                    url=str(path_candidate.resolve()),
                    duration_ms=elapsed,
                    byte_size=len(content.encode("utf-8")),
                )
            except Exception as exc:
                raise NetworkError(
                    f"Failed to read local file {url_or_path}: {exc}",
                    url=url_or_path,
                ) from exc

        # 3. HTTP(S) Remote Fetch with Retries
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if custom_headers:
            headers.update(custom_headers)

        last_error: Optional[Exception] = None

        for attempt in range(self.retries + 1):
            try:
                req = urllib.request.Request(url_or_path, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw_bytes = resp.read()
                    status_code = resp.status
                    content_type = resp.headers.get("Content-Type", "text/html")
                    charset = resp.headers.get_content_charset() or "utf-8"
                    content = raw_bytes.decode(charset, errors="replace")

                    elapsed = (time.perf_counter() - start) * 1000.0
                    return FetchResult(
                        content=content,
                        status_code=status_code,
                        content_type=content_type,
                        url=url_or_path,
                        duration_ms=elapsed,
                        byte_size=len(raw_bytes),
                    )

            except urllib.error.HTTPError as err:
                last_error = err
                # Do not retry on 4xx client errors (except 429 Too Many Requests)
                if 400 <= err.code < 500 and err.code != 429:
                    raise NetworkError(
                        f"HTTP {err.code}: {err.reason}",
                        status_code=err.code,
                        url=url_or_path,
                    ) from err

            except (urllib.error.URLError, TimeoutError, OSError) as err:
                last_error = err

            # If more attempts remain, sleep with exponential backoff & jitter
            if attempt < self.retries:
                backoff = (self.backoff_factor * (2**attempt)) + random.uniform(0.05, 0.2)
                time.sleep(backoff)

        raise NetworkError(
            f"Failed to fetch {url_or_path} after {self.retries} retries: {last_error}",
            url=url_or_path,
        )
