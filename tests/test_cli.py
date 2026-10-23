"""Unit tests for the CLI command line interface."""

from pathlib import Path
import pytest
from autoextract.cli import create_parser, main


def test_cli_parser_defaults():
    parser = create_parser()
    args = parser.parse_args(["run", "https://example.com/test"])
    assert args.command == "run"
    assert args.urls == ["https://example.com/test"]
    assert args.concurrency == 4
    assert args.parser == "auto"
    assert args.format == "all"
    assert args.rate_limit == 10.0


def test_cli_parser_custom_flags():
    parser = create_parser()
    args = parser.parse_args([
        "run",
        "-c", "8",
        "-r", "25.0",
        "-p", "catalog",
        "-f", "csv",
        "-o", "custom_dir",
        "-n", "export_name",
        "--verbose",
        "https://example.com/1",
        "https://example.com/2",
    ])
    assert args.concurrency == 8
    assert args.rate_limit == 25.0
    assert args.parser == "catalog"
    assert args.format == "csv"
    assert args.output_dir == "custom_dir"
    assert args.name == "export_name"
    assert args.verbose is True
    assert len(args.urls) == 2


def test_cli_demo_execution(tmp_path: Path):
    out_dir = str(tmp_path / "demo_output")
    exit_code = main(["demo", "-o", out_dir])
    assert exit_code == 0

    demo_dir = Path(out_dir)
    assert demo_dir.exists()
    assert (demo_dir / "demo_extraction.json").exists()
    assert (demo_dir / "demo_extraction.csv").exists()
    assert (demo_dir / "demo_extraction_summary.md").exists()


def test_cli_run_local_fixture(tmp_path: Path, fixtures_dir: Path):
    article_fixture = str(fixtures_dir / "sample_article.html")
    out_dir = str(tmp_path / "run_output")

    exit_code = main([
        "run",
        "-o", out_dir,
        "-f", "json",
        "-p", "article",
        article_fixture,
    ])
    assert exit_code == 0
    assert (Path(out_dir) / "extraction_results.json").exists()


def test_cli_run_input_file(tmp_path: Path, fixtures_dir: Path):
    article_fixture = str(fixtures_dir / "sample_article.html")
    catalog_fixture = str(fixtures_dir / "sample_catalog.html")

    urls_txt = tmp_path / "urls.txt"
    urls_txt.write_text(f"{article_fixture}\n{catalog_fixture}\n# comment line\n", encoding="utf-8")

    out_dir = str(tmp_path / "file_output")
    exit_code = main([
        "run",
        "-i", str(urls_txt),
        "-o", out_dir,
        "-f", "all",
    ])
    assert exit_code == 0
    assert (Path(out_dir) / "extraction_results.json").exists()
    assert (Path(out_dir) / "extraction_results.csv").exists()
    assert (Path(out_dir) / "extraction_results_summary.md").exists()
