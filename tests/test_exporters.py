"""Unit tests for JSON, CSV, and Markdown data exporters."""

import json
from pathlib import Path
import pytest
from autoextract.core.models import EngineStats, ExportConfig, ExtractedRecord
from autoextract.exporters.csv_exporter import CSVExporter, flatten_dict
from autoextract.exporters.json_exporter import JSONExporter
from autoextract.exporters.markdown_exporter import MarkdownExporter


@pytest.fixture
def sample_records() -> list[ExtractedRecord]:
    return [
        ExtractedRecord(
            target_url="https://example.com/article/1",
            parser_type="article",
            data={
                "title": "Autonomous Systems",
                "author": "Dr. Vance",
                "reading_time_minutes": 3,
                "tags": ["ai", "agents"],
            },
            status="success",
            duration_ms=45.2,
            raw_size_bytes=1024,
        ),
        ExtractedRecord(
            target_url="https://example.com/shop/catalog",
            parser_type="catalog",
            data={
                "item_count": 2,
                "items": [
                    {"title": "Keyboard", "price": 120.0, "currency": "USD"},
                    {"title": "Mouse", "price": 45.0, "currency": "USD"},
                ],
            },
            status="success",
            duration_ms=62.8,
            raw_size_bytes=2048,
        ),
    ]


@pytest.fixture
def sample_stats() -> EngineStats:
    stats = EngineStats(total_targets=2, successful=2, failed=0, total_bytes_downloaded=3072)
    stats.finish()
    return stats


def test_flatten_dict():
    nested = {
        "id": 101,
        "meta": {"created": "2026-10-23", "author": {"name": "Kartavya"}},
        "tags": ["python", "ai"],
    }
    flattened = flatten_dict(nested)
    assert flattened["id"] == 101
    assert flattened["meta_created"] == "2026-10-23"
    assert flattened["meta_author_name"] == "Kartavya"
    assert flattened["tags"] == "python; ai"


def test_json_exporter(tmp_path: Path, sample_records, sample_stats):
    cfg = ExportConfig(
        output_dir=tmp_path,
        base_filename="test_out",
        include_metadata=True,
    )
    exporter = JSONExporter()
    out_file = exporter.export(sample_records, sample_stats, cfg)

    assert out_file.exists()
    content = json.loads(out_file.read_text(encoding="utf-8"))
    assert content["generator"] == "AutoExtract Engine"
    assert content["record_count"] == 2
    assert content["statistics"]["successful"] == 2
    assert len(content["records"]) == 2


def test_csv_exporter(tmp_path: Path, sample_records, sample_stats):
    cfg = ExportConfig(
        output_dir=tmp_path,
        base_filename="test_csv",
    )
    exporter = CSVExporter()
    out_file = exporter.export(sample_records, sample_stats, cfg)

    assert out_file.exists()
    lines = out_file.read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) >= 4  # Header + 1 article row + 2 exploded catalog item rows
    header = lines[0]
    assert "target_url" in header
    assert "parser_type" in header
    assert "item_title" in header or "data_title" in header


def test_markdown_exporter(tmp_path: Path, sample_records, sample_stats):
    cfg = ExportConfig(
        output_dir=tmp_path,
        base_filename="test_report",
    )
    exporter = MarkdownExporter()
    out_file = exporter.export(sample_records, sample_stats, cfg)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "# 🚀 AutoExtract Engine - Execution Report" in content
    assert "Autonomous Systems" in content
    assert "Keyboard" in content or "catalog" in content
    assert "Success Rate" in content
