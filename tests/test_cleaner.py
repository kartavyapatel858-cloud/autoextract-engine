"""Unit tests for data sanitization and cleaner utilities."""

import pytest
from autoextract.parsers.cleaner import (
    clean_text,
    estimate_reading_time,
    extract_tags,
    normalize_url,
    parse_datetime,
    parse_price,
)


def test_clean_text_basic():
    raw = "   \n\t Hello   World! \t \n  "
    assert clean_text(raw) == "Hello World!"


def test_clean_text_strips_html_and_entities():
    raw = "<p>Clean <b>bold</b> text &amp; &quot;quotes&quot; &#39;apostrophe&#39;</p>"
    assert clean_text(raw) == "Clean bold text & \"quotes\" 'apostrophe'"


def test_clean_text_strips_script_style_tags():
    raw = "<div>Visible<script>alert('xss');</script><style>body {color:red;}</style> Content</div>"
    assert clean_text(raw) == "Visible Content"


def test_clean_text_empty_and_none():
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("   \n\t  ") == ""


@pytest.mark.parametrize(
    "raw_input,expected_amount,expected_currency",
    [
        ("$19.99", 19.99, "USD"),
        ("USD 49.50", 49.50, "USD"),
        ("£ 1,450.00", 1450.00, "GBP"),
        ("99.95 EUR", 99.95, "EUR"),
        ("₹4,999", 4999.0, "INR"),
        ("Free", None, None),
        ("", None, None),
        ("Price: $ 120", 120.0, "USD"),
    ],
)
def test_parse_price(raw_input, expected_amount, expected_currency):
    amount, currency = parse_price(raw_input)
    assert amount == expected_amount
    assert currency == expected_currency


def test_parse_datetime_iso():
    iso_str = "2026-10-23T12:30:00Z"
    parsed = parse_datetime(iso_str)
    assert parsed is not None
    assert "2026-10-23" in parsed


def test_parse_datetime_standard_strings():
    date_str = "October 23, 2026"
    parsed = parse_datetime(date_str)
    assert parsed is not None
    assert "2026-10-23" in parsed


def test_parse_datetime_invalid():
    assert parse_datetime("not-a-valid-date") is None
    assert parse_datetime("") is None
    assert parse_datetime(None) is None


def test_normalize_url_removes_tracking_and_fragment():
    dirty_url = "https://example.com/item?id=42&utm_source=twitter&utm_medium=social#overview"
    cleaned = normalize_url(dirty_url)
    assert cleaned == "https://example.com/item?id=42"


def test_normalize_url_resolves_relative():
    base = "https://example.com/blog/"
    rel = "../products/widget"
    assert normalize_url(rel, base_url=base) == "https://example.com/products/widget"


def test_extract_tags():
    tags_str = "Python, AI, MACHINE LEARNING, Python, Web!Extraction"
    tags = extract_tags(tags_str)
    assert tags == ["python", "ai", "machine learning", "webextraction"]


def test_estimate_reading_time():
    # 400 words at 200 WPM should take ~2 minutes
    sample_text = " ".join(["word"] * 400)
    assert estimate_reading_time(sample_text) == 2

    # 50 words should return minimum 1 minute
    short_text = " ".join(["word"] * 50)
    assert estimate_reading_time(short_text) == 1

    assert estimate_reading_time("") == 0
