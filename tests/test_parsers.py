"""Unit tests for HTML DOM parsing, specialized extractors, and JSON querying."""

import pytest
from autoextract.parsers.html_parser import (
    ArticleExtractor,
    CatalogExtractor,
    MetadataExtractor,
    parse_html,
)
from autoextract.parsers.json_parser import JSONParser, query_json_path


def test_dom_node_querying():
    html_doc = """
    <div id="container" class="wrapper">
      <h1 class="heading">Main Title</h1>
      <ul class="items">
        <li class="item" data-id="1">First</li>
        <li class="item" data-id="2">Second</li>
      </ul>
    </div>
    """
    root = parse_html(html_doc)
    container = root.find("div", {"id": "container"})
    assert container is not None
    assert container.get_attr("class") == "wrapper"

    h1 = root.find("h1")
    assert h1 is not None
    assert h1.text == "Main Title"

    items = root.find_all("li")
    assert len(items) == 2
    assert items[0].text == "First"
    assert items[1].text == "Second"


def test_dom_css_selectors():
    html_doc = """
    <div class="card">
      <h2 class="title">Product 1</h2>
      <span class="price">$50</span>
    </div>
    <div class="card">
      <h2 class="title">Product 2</h2>
      <span class="price">$100</span>
    </div>
    """
    root = parse_html(html_doc)
    cards = root.select(".card")
    assert len(cards) == 2

    prices = root.select(".price")
    assert len(prices) == 2
    assert prices[0].text == "$50"


def test_metadata_extractor(sample_article_html):
    extractor = MetadataExtractor()
    assert extractor.can_parse("text/html", sample_article_html)

    data = extractor.parse(sample_article_html, target_url="https://blog.cloudcraft.io/microservices-architecture")
    assert data["title"] == "Scaling Microservices with Event-Driven Architecture"
    assert "blueprint" in data["description"]
    assert data["canonical_url"] == "https://blog.cloudcraft.io/microservices-architecture"
    assert data["opengraph"]["title"] == "Scaling Microservices with Event-Driven Architecture"


def test_article_extractor(sample_article_html):
    extractor = ArticleExtractor()
    assert extractor.can_parse("text/html", sample_article_html)

    data = extractor.parse(sample_article_html)
    assert data["title"] == "Scaling Microservices with Event-Driven Architecture"
    assert data["author"] == "Alex Mercer"
    assert data["published_at"] is not None
    assert "2026-10-15" in data["published_at"]
    assert "Modern distributed platforms demand" in data["lead_summary"]
    assert len(data["headings"]) == 3
    assert data["headings"][0]["text"] == "Decoupling Producers and Consumers"
    assert "microservices" in data["tags"]
    assert data["word_count"] > 30
    assert data["reading_time_minutes"] >= 1


def test_catalog_extractor(sample_catalog_html):
    extractor = CatalogExtractor()
    assert extractor.can_parse("text/html", sample_catalog_html)

    data = extractor.parse(sample_catalog_html, target_url="https://catalog.example.com")
    assert data["item_count"] == 3
    items = data["items"]

    # First item
    assert items[0]["title"] == "Blade Server Node 64-Core AMD EPYC"
    assert items[0]["price"] == 4850.00
    assert items[0]["currency"] == "USD"
    assert items[0]["rating"] == 4.95
    assert items[0]["in_stock"] is True
    assert items[0]["url"] == "https://catalog.example.com/servers/blade-64c"

    # Third item
    assert items[2]["title"] == "100GbE Managed Top-of-Rack Switch"
    assert items[2]["price"] == 3420.00
    assert items[2]["in_stock"] is False


def test_json_parser_and_query_path(sample_api_json):
    parser = JSONParser()
    assert parser.can_parse("application/json", sample_api_json)

    data = parser.parse(sample_api_json)
    assert data["is_collection"] is False
    assert data["payload"]["api_version"] == "2.4.0"

    # Query JSON path
    payload = data["payload"]
    cluster = query_json_path(payload, "meta.cluster")
    assert cluster == "us-central1-k8s"

    first_svc_name = query_json_path(payload, "services[0].name")
    assert first_svc_name == "auth-service"

    all_svc_names = query_json_path(payload, "services.*.name")
    assert all_svc_names == ["auth-service", "billing-pipeline", "etl-processor"]
