"""Data sanitization, cleaning, and normalization utilities."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import List, Optional, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

# Common currency symbols and codes
CURRENCY_MAP = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
    "₹": "INR",
    "C$": "CAD",
    "A$": "AUD",
    "USD": "USD",
    "EUR": "EUR",
    "GBP": "GBP",
    "INR": "INR",
}

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "source",
}


def clean_text(text: Optional[str]) -> str:
    """
    Sanitizes raw web text:
    - Strips leftover HTML tags
    - Unescapes HTML entities
    - Collapses consecutive whitespace and linebreaks
    - Strips leading and trailing whitespace
    """
    if not text:
        return ""

    # Remove script and style contents if any raw tags leaked
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Unescape HTML entities (e.g. &amp;, &quot;, &#39;)
    text = html.unescape(text)

    # Replace non-breaking spaces and exotic whitespace with standard space
    text = text.replace("\xa0", " ").replace("\u200b", "")

    # Collapse consecutive whitespace characters
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def parse_price(text: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts numerical price value and currency symbol/code.
    Handles formats like:
      - "$19.99" -> (19.99, "USD")
      - "£ 1,450.50" -> (1450.50, "GBP")
      - "99.00 EUR" -> (99.00, "EUR")
      - "₹4,999" -> (4999.0, "INR")
    """
    if not text:
        return None, None

    cleaned = clean_text(text)
    if not cleaned:
        return None, None

    # Detect currency
    detected_currency: Optional[str] = None
    for symbol, code in CURRENCY_MAP.items():
        if symbol in cleaned:
            detected_currency = code
            break

    # Look for numeric patterns: handles optional commas and decimals
    match = re.search(r"(\d{1,3}(?:[,\s]\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)", cleaned)
    if not match:
        return None, detected_currency

    num_str = match.group(1).replace(",", "").replace(" ", "")
    try:
        val = float(num_str)
        return val, detected_currency
    except ValueError:
        return None, detected_currency


def parse_datetime(date_str: Optional[str]) -> Optional[str]:
    """
    Parses common web date/time strings into standardized ISO 8601 UTC format.
    Returns ISO formatted string or None if unparseable.
    """
    if not date_str:
        return None

    cleaned = clean_text(date_str)
    if not cleaned:
        return None

    # Common formats to try
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]

    # Quick ISO normalization (replace Z with +00:00)
    norm = cleaned.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(norm)
        return dt.isoformat()
    except (ValueError, TypeError):
        pass

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.isoformat()
        except ValueError:
            continue

    return None


def normalize_url(url: str, base_url: str = "") -> str:
    """
    Normalizes a URL:
    - Resolves relative URLs if base_url is provided
    - Removes common tracking query parameters (utm_*, fbclid, etc.)
    - Removes anchor fragments (#)
    """
    if not url:
        return ""

    url = url.strip()
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    # Filter out tracking query parameters
    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    filtered_params = [
        (k, v) for k, v in query_params if k.lower() not in TRACKING_PARAMS
    ]
    new_query = urlencode(filtered_params)

    # Reconstruct without fragment
    cleaned_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        "",  # drop fragment
    ))

    return cleaned_url


def extract_tags(items: Union[str, List[str]], max_tags: int = 15) -> List[str]:
    """
    Normalizes a list or comma-separated string of tags:
    - lowercases
    - strips non-alphanumeric punctuation
    - deduplicates while preserving order
    """
    if isinstance(items, str):
        candidates = re.split(r"[,;|/]", items)
    elif isinstance(items, list):
        candidates = items
    else:
        return []

    seen = set()
    result = []
    for c in candidates:
        tag = clean_text(c).lower()
        tag = re.sub(r"[^\w\s-]", "", tag)
        tag = tag.strip()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
            if len(result) >= max_tags:
                break

    return result


def estimate_reading_time(text: str, wpm: int = 200) -> int:
    """Calculates estimated reading time in minutes (minimum 1 minute)."""
    words = len(text.split())
    if words == 0:
        return 0
    return max(1, round(words / wpm))
