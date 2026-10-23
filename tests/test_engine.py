"""Unit tests for the concurrent extraction engine and resource fetcher."""

import pytest
from autoextract.core.models import ExtractionTarget, RunConfig
from autoextract.engine.fetcher import ResourceFetcher
from autoextract.engine.runner import ExtractionEngine


def test_resource_fetcher_mock():
    mock_url = "https://mock.example.com/test"
    mock_body = "<h1>Mock Page</h1>"
    fetcher = ResourceFetcher(mock_responses={mock_url: mock_body})

    res = fetcher.fetch(mock_url)
    assert res.status_code == 200
    assert res.content == mock_body
    assert res.byte_size == len(mock_body.encode("utf-8"))


def test_resource_fetcher_local_file(fixtures_dir):
    article_path = str((fixtures_dir / "sample_article.html").resolve())
    fetcher = ResourceFetcher()

    res = fetcher.fetch(article_path)
    assert res.status_code == 200
    assert "Scaling Microservices" in res.content


def test_extraction_engine_single(sample_article_html):
    mock_url = "https://example.com/post-1"
    config = RunConfig(
        concurrency=2,
        rate_limit=100.0,
        mock_responses={mock_url: sample_article_html},
    )
    engine = ExtractionEngine(config=config)
    target = ExtractionTarget(url=mock_url, parser_type="article")

    record = engine.extract_single(target)
    assert record.status == "success"
    assert record.parser_type == "article"
    assert record.data["title"] == "Scaling Microservices with Event-Driven Architecture"


def test_extraction_engine_batch_concurrent(
    sample_article_html,
    sample_catalog_html,
    sample_api_json,
):
    mocks = {
        "https://example.com/article": sample_article_html,
        "https://example.com/shop": sample_catalog_html,
        "https://example.com/api.json": sample_api_json,
    }
    config = RunConfig(
        concurrency=3,
        rate_limit=100.0,
        mock_responses=mocks,
    )
    engine = ExtractionEngine(config=config)

    targets = [
        ExtractionTarget(url="https://example.com/article", parser_type="auto"),
        ExtractionTarget(url="https://example.com/shop", parser_type="auto"),
        ExtractionTarget(url="https://example.com/api.json", parser_type="auto"),
    ]

    records, stats = engine.run(targets)

    assert len(records) == 3
    assert stats.total_targets == 3
    assert stats.successful == 3
    assert stats.failed == 0
    assert stats.success_rate == 100.0
    assert stats.total_bytes_downloaded > 0


def test_extraction_engine_handles_partial_failure(sample_article_html):
    mocks = {
        "https://example.com/valid": sample_article_html,
    }
    # One valid URL and one nonexistent URL with retries=0 for fast test
    config = RunConfig(
        concurrency=2,
        rate_limit=100.0,
        retries=0,
        timeout=1.0,
        mock_responses=mocks,
    )
    engine = ExtractionEngine(config=config)

    targets = [
        ExtractionTarget(url="https://example.com/valid", parser_type="article"),
        ExtractionTarget(url="https://invalid-domain-does-not-exist-1234567.com/404", parser_type="article"),
    ]

    records, stats = engine.run(targets)

    assert len(records) == 2
    assert stats.total_targets == 2
    assert stats.successful == 1
    assert stats.failed == 1
    assert stats.success_rate == 50.0

    statuses = {r.target_url: r.status for r in records}
    assert statuses["https://example.com/valid"] == "success"
    assert statuses["https://invalid-domain-does-not-exist-1234567.com/404"] == "error"
