"""CSV Data Exporter with automatic dictionary flattening."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from autoextract.core.exceptions import ExportError
from autoextract.core.models import EngineStats, ExportConfig, ExtractedRecord
from autoextract.exporters.base import BaseExporter


def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = "",
    sep: str = "_",
) -> Dict[str, Any]:
    """
    Flattens arbitrary nested dicts and lists into single-level key-values.
    Lists are converted to semicolon-delimited strings.
    """
    items: List[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            if v and isinstance(v[0], dict):
                # We handle nested object lists separately or serialize to string
                items.append((new_key, f"[{len(v)} items]"))
            else:
                items.append((new_key, "; ".join(str(x) for x in v)))
        else:
            items.append((new_key, v if v is not None else ""))
    return dict(items)


class CSVExporter(BaseExporter):
    """Exports extracted records to clean, flattened CSV files."""

    def export(
        self,
        records: List[ExtractedRecord],
        stats: Optional[EngineStats] = None,
        config: Optional[ExportConfig] = None,
    ) -> Path:
        cfg = config or ExportConfig()
        output_dir = Path(cfg.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        target_file = output_dir / f"{cfg.base_filename}.csv"

        try:
            flattened_rows: List[Dict[str, Any]] = []

            for record in records:
                base_info = {
                    "target_url": record.target_url,
                    "parser_type": record.parser_type,
                    "status": record.status,
                    "duration_ms": round(record.duration_ms, 2),
                }

                # Check if payload contains an item collection (e.g. catalog products)
                items_collection = record.data.get("items")
                if isinstance(items_collection, list) and items_collection:
                    for item in items_collection:
                        row = dict(base_info)
                        row.update(flatten_dict(item, parent_key="item"))
                        flattened_rows.append(row)
                else:
                    row = dict(base_info)
                    row.update(flatten_dict(record.data, parent_key="data"))
                    flattened_rows.append(row)

            # Determine all unique headers across all rows
            fieldnames = []
            seen = set()
            for r in flattened_rows:
                for k in r.keys():
                    if k not in seen:
                        seen.add(k)
                        fieldnames.append(k)

            # Write with utf-8-sig BOM for Microsoft Excel compatibility
            with open(target_file, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for row in flattened_rows:
                    writer.writerow(row)

            return target_file

        except Exception as exc:
            raise ExportError(f"Failed to export CSV to {target_file}: {exc}") from exc
