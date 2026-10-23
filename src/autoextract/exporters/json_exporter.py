"""JSON Data Exporter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from autoextract.core.exceptions import ExportError
from autoextract.core.models import EngineStats, ExportConfig, ExtractedRecord
from autoextract.exporters.base import BaseExporter


class JSONExporter(BaseExporter):
    """Exports extracted records to clean, formatted JSON."""

    def export(
        self,
        records: List[ExtractedRecord],
        stats: Optional[EngineStats] = None,
        config: Optional[ExportConfig] = None,
    ) -> Path:
        cfg = config or ExportConfig()
        output_dir = Path(cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        target_file = output_dir / f"{cfg.base_filename}.json"

        try:
            records_data = [r.to_dict() for r in records]

            if cfg.include_metadata:
                payload: Dict[str, Any] = {
                    "version": "1.0",
                    "generator": "AutoExtract Engine",
                    "record_count": len(records),
                    "statistics": stats.to_dict() if stats else None,
                    "records": records_data,
                }
            else:
                payload = records_data  # type: ignore

            indent = 2 if cfg.pretty_json else None
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=indent, ensure_ascii=False)

            return target_file

        except Exception as exc:
            raise ExportError(f"Failed to export JSON to {target_file}: {exc}") from exc
