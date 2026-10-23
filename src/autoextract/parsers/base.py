"""Abstract Base Parser definition."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseParser(ABC):
    """Abstract base class for all content extractors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this parser."""
        pass

    @abstractmethod
    def can_parse(self, content_type: str, raw_content: str) -> bool:
        """Determines whether this parser can handle the provided content."""
        pass

    @abstractmethod
    def parse(self, raw_content: str, target_url: str = "") -> Dict[str, Any]:
        """
        Parses raw text into a structured dictionary.

        Raises:
            ParseError: If critical parsing failures occur.
        """
        pass
