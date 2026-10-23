"""Abstract base exporter definition."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from autoextract.core.models import EngineStats, ExportConfig, ExtractedRecord


class BaseExporter(ABC):
    """Abstract base class for data exporters."""

    @abstractmethod
    def export(
        self,
        records: List[ExtractedRecord],
        stats: Optional[EngineStats] = None,
        config: Optional[ExportConfig] = None,
    ) -> Path:
        """
        Exports extracted records to disk.
        
        Returns:
            The Path of the exported file.
        """
        pass
