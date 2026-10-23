"""
Command Line Interface for AutoExtract Engine.
Zero external runtime dependencies.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

from autoextract.core.models import (
    ExportConfig,
    ExportFormat,
    ExtractionTarget,
    ParserType,
    RunConfig,
)
from autoextract.engine.runner import ExtractionEngine
from autoextract.exporters.csv_exporter import CSVExporter
from autoextract.exporters.json_exporter import JSONExporter
from autoextract.exporters.markdown_exporter import MarkdownExporter

DEMO_ARTICLE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>The Future of Autonomous AI Agents</title>
  <meta name="author" content="Dr. Elena Vance">
  <meta property="article:published_time" content="2026-10-23T08:00:00Z">
  <meta name="keywords" content="AI, Autonomous Agents, Python, Machine Learning">
  <meta property="og:title" content="The Future of Autonomous AI Agents">
  <meta property="og:description" content="An in-depth analysis of autonomous agentic systems in modern software engineering.">
  <link rel="canonical" href="https://tech-insights.example.com/ai-agents">
</head>
<body>
  <article>
    <h1>The Future of Autonomous AI Agents</h1>
    <p class="lead">Autonomous systems are reshaping how software engineers build, test, and maintain codebases.</p>
    <h2>Architectural Paradigms</h2>
    <p>By decoupling orchestration from specialized worker subagents, modern architectures achieve unprecedented modularity and resilience.</p>
    <h2>Zero-Cost Tooling</h2>
    <p>Leveraging Python standard libraries enables scalable automation without recurring licensing fees or cloud subscription lock-in.</p>
  </article>
</body>
</html>
"""

DEMO_CATALOG_HTML = """
<!DOCTYPE html>
<html>
<head><title>Cloud Developer Gear Shop</title></head>
<body>
  <div class="products">
    <div class="product-card">
      <h3 class="title">Ergonomic Mechanical Keyboard</h3>
      <span class="price">$149.99</span>
      <span class="rating">4.8 / 5.0</span>
      <span class="stock">In Stock</span>
      <a href="/products/mech-keyboard">View Details</a>
    </div>
    <div class="product-card">
      <h3 class="title">Ultra-Wide 4K Monitor 34-inch</h3>
      <span class="price">$599.00</span>
      <span class="rating">4.9 / 5.0</span>
      <span class="stock">In Stock</span>
      <a href="/products/monitor-4k">View Details</a>
    </div>
    <div class="product-card">
      <h3 class="title">Noise Cancelling Studio Headphones</h3>
      <span class="price">$229.50</span>
      <span class="rating">4.7 / 5.0</span>
      <span class="stock">Out of Stock</span>
      <a href="/products/headphones">View Details</a>
    </div>
  </div>
</body>
</html>
"""

DEMO_JSON_API = """
{
  "status": "success",
  "total": 2,
  "data": {
    "organization": "Cloud Innovation Labs",
    "deployments": [
      {"id": "dep-101", "service": "web-gateway", "status": "healthy", "uptime_pct": 99.98},
      {"id": "dep-102", "service": "data-pipeline", "status": "healthy", "uptime_pct": 99.95}
    ]
  }
}
"""


def run_demo(output_dir: str = "output") -> int:
    """Runs the built-in offline showcase demonstration."""
    print("=" * 70)
    print("🚀 AutoExtract Engine - Zero-Cost Offline Demonstration")
    print("=" * 70)

    demo_mocks = {
        "https://demo.example.com/article": DEMO_ARTICLE_HTML,
        "https://demo.example.com/shop": DEMO_CATALOG_HTML,
        "https://demo.example.com/api/status.json": DEMO_JSON_API,
    }

    config = RunConfig(
        concurrency=3,
        rate_limit=20.0,
        mock_responses=demo_mocks,
    )

    targets = [
        ExtractionTarget(url="https://demo.example.com/article", parser_type="article"),
        ExtractionTarget(url="https://demo.example.com/shop", parser_type="catalog"),
        ExtractionTarget(url="https://demo.example.com/api/status.json", parser_type="json"),
    ]

    print(f"[*] Processing {len(targets)} targets concurrently with mock adapters...")

    engine = ExtractionEngine(config=config)

    def on_progress(rec, completed, total):
        print(f"  [{completed}/{total}] Finished: {rec.target_url} -> Parser: {rec.parser_type} ({rec.duration_ms:.1f}ms)")

    records, stats = engine.run(targets, progress_callback=on_progress)

    print("\n📊 Extraction Metrics:")
    print(f"  - Total Targets: {stats.total_targets}")
    print(f"  - Successful: {stats.successful}")
    print(f"  - Failed: {stats.failed}")
    print(f"  - Success Rate: {stats.success_rate}%")
    print(f"  - Throughput: {stats.requests_per_second} req/sec")

    # Export to all formats
    export_cfg = ExportConfig(
        format="all",
        output_dir=Path(output_dir),
        base_filename="demo_extraction",
    )

    json_path = JSONExporter().export(records, stats, export_cfg)
    csv_path = CSVExporter().export(records, stats, export_cfg)
    md_path = MarkdownExporter().export(records, stats, export_cfg)

    print("\n📁 Exported Showcase Artifacts:")
    print(f"  - JSON:     {json_path.resolve()}")
    print(f"  - CSV:      {csv_path.resolve()}")
    print(f"  - Markdown: {md_path.resolve()}")
    print("\n✅ Showcase demonstration completed successfully!")
    print("=" * 70)
    return 0


def create_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="autoextract",
        description="High-performance, zero-cost concurrent web extraction engine.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: run
    run_cmd = subparsers.add_parser("run", help="Run extraction against specified URLs or files")
    run_cmd.add_argument("urls", nargs="*", help="Target URLs or local file paths")
    run_cmd.add_argument("-i", "--input-file", help="File with list of URLs (one per line)")
    run_cmd.add_argument(
        "-p",
        "--parser",
        choices=["auto", "article", "catalog", "metadata", "json"],
        default="auto",
        help="Target parser type (default: auto)",
    )
    run_cmd.add_argument("-c", "--concurrency", type=int, default=4, help="Concurrent workers (default: 4)")
    run_cmd.add_argument("-r", "--rate-limit", type=float, default=10.0, help="Max requests per second (default: 10.0)")
    run_cmd.add_argument("-t", "--timeout", type=float, default=10.0, help="Timeout in seconds (default: 10.0)")
    run_cmd.add_argument("--retries", type=int, default=3, help="Retry attempts (default: 3)")
    run_cmd.add_argument(
        "-f",
        "--format",
        choices=["json", "csv", "markdown", "all"],
        default="all",
        help="Export format (default: all)",
    )
    run_cmd.add_argument("-o", "--output-dir", default="output", help="Directory for exported results (default: output)")
    run_cmd.add_argument("-n", "--name", default="extraction_results", help="Base output filename")
    run_cmd.add_argument("-v", "--verbose", action="store_true", help="Enable verbose debug logging")

    # Subcommand: demo
    demo_cmd = subparsers.add_parser("demo", help="Run built-in offline showcase demo")
    demo_cmd.add_argument("-o", "--output-dir", default="output", help="Directory for exported demo files")

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """CLI Entry point."""
    arg_parser = create_parser()
    parsed_args = arg_parser.parse_args(args)

    if not parsed_args.command:
        arg_parser.print_help()
        return 0

    if parsed_args.command == "demo":
        return run_demo(output_dir=parsed_args.output_dir)

    if parsed_args.command == "run":
        target_urls: List[str] = list(parsed_args.urls or [])

        if parsed_args.input_file:
            input_path = Path(parsed_args.input_file)
            if input_path.exists():
                for line in input_path.read_text(encoding="utf-8").splitlines():
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("#"):
                        target_urls.append(cleaned)
            else:
                print(f"Error: input file {parsed_args.input_file} not found.", file=sys.stderr)
                return 1

        if not target_urls:
            print("Error: No URLs or files specified to extract. Use --help for usage.", file=sys.stderr)
            return 1

        run_cfg = RunConfig(
            concurrency=parsed_args.concurrency,
            rate_limit=parsed_args.rate_limit,
            timeout=parsed_args.timeout,
            retries=parsed_args.retries,
            verbose=parsed_args.verbose,
        )

        targets = [
            ExtractionTarget(url=u, parser_type=parsed_args.parser)
            for u in target_urls
        ]

        print(f"[*] Initiating extraction for {len(targets)} targets (Concurrency: {run_cfg.concurrency})...")
        engine = ExtractionEngine(config=run_cfg)

        def on_progress(rec, completed, total):
            status_symbol = "✓" if rec.status == "success" else "✗"
            print(f"  [{completed}/{total}] {status_symbol} {rec.target_url} ({rec.duration_ms:.1f}ms)")

        records, stats = engine.run(targets, progress_callback=on_progress)

        print("\n📊 Extraction Metrics:")
        print(f"  - Processed: {stats.total_targets} | Success: {stats.successful} | Failed: {stats.failed}")
        print(f"  - Elapsed: {stats.elapsed_seconds:.2f}s | Rate: {stats.requests_per_second} req/s")

        # Handle exports
        fmt: ExportFormat = parsed_args.format
        export_cfg = ExportConfig(
            format=fmt,
            output_dir=Path(parsed_args.output_dir),
            base_filename=parsed_args.name,
        )

        out_files = []
        if fmt in ("json", "all"):
            out_files.append(JSONExporter().export(records, stats, export_cfg))
        if fmt in ("csv", "all"):
            out_files.append(CSVExporter().export(records, stats, export_cfg))
        if fmt in ("markdown", "all"):
            out_files.append(MarkdownExporter().export(records, stats, export_cfg))

        print("\n📁 Output Files:")
        for fp in out_files:
            print(f"  - {fp.resolve()}")

        return 0 if stats.failed == 0 else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
