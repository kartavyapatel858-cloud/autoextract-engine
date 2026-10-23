"""Custom exceptions for the AutoExtract engine."""

from typing import Optional


class AutoExtractError(Exception):
    """Base exception for all AutoExtract engine errors."""

    def __init__(self, message: str, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class NetworkError(AutoExtractError):
    """Raised when an HTTP request fails after retries."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        merged_details = dict(details or {})
        if status_code is not None:
            merged_details["status_code"] = status_code
        if url:
            merged_details["url"] = url
        super().__init__(message, merged_details)
        self.status_code = status_code
        self.url = url


class RateLimitError(AutoExtractError):
    """Raised when rate limits are exceeded or backing off is required."""


class ParseError(AutoExtractError):
    """Raised when parsing fails or payload structure is invalid."""

    def __init__(
        self,
        message: str,
        parser_name: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        merged = dict(details or {})
        if parser_name:
            merged["parser"] = parser_name
        super().__init__(message, merged)
        self.parser_name = parser_name


class ExportError(AutoExtractError):
    """Raised when exporting extracted records fails."""


class ConfigurationError(AutoExtractError):
    """Raised when an invalid configuration is supplied."""
