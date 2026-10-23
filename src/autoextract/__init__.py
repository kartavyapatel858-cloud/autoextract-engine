"""
AutoExtract Engine
~~~~~~~~~~~~~~~~~~
A modern, concurrent Python automation & web extraction engine.
Zero external runtime dependencies. Production-grade resilience,
modular parser architecture, and multi-format exporters.

(c) 2026 Kartavya Patel (@kartavyapatel858-cloud)
"""

__version__ = "1.0.0"
__author__ = "Kartavya Patel"
__license__ = "MIT"

from autoextract.core.models import (
    ExtractionTarget,
    ExtractedRecord,
    EngineStats,
    RunConfig,
    ExportConfig,
)
from autoextract.engine.runner import ExtractionEngine

__all__ = [
    "ExtractionTarget",
    "ExtractedRecord",
    "EngineStats",
    "RunConfig",
    "ExportConfig",
    "ExtractionEngine",
]
