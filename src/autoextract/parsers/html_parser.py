"""
HTML Parser and DOM Tree Engine.
Zero external dependencies, built on Python standard library html.parser.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Union

from autoextract.core.exceptions import ParseError
from autoextract.parsers.base import BaseParser
from autoextract.parsers.cleaner import (
    clean_text,
    estimate_reading_time,
    extract_tags,
    normalize_url,
    parse_datetime,
    parse_price,
)

# HTML5 void elements that do not require closing tags
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr"
}


class DOMNode:
    """Represents a node in the HTML DOM tree."""

    __slots__ = ("tag", "attrs", "children", "parent", "_text_cache")

    def __init__(
        self,
        tag: str,
        attrs: Optional[Dict[str, str]] = None,
        parent: Optional[DOMNode] = None,
    ) -> None:
        self.tag = tag.lower()
        self.attrs: Dict[str, str] = attrs or {}
        self.children: List[Union[DOMNode, str]] = []
        self.parent = parent
        self._text_cache: Optional[str] = None

    def get_attr(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Safely fetch attribute value by name (case-insensitive)."""
        name_lower = name.lower()
        for k, v in self.attrs.items():
            if k.lower() == name_lower:
                return v
        return default

    @property
    def text(self) -> str:
        """Extracts and normalizes all inner text within this node."""
        parts: List[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif isinstance(child, DOMNode):
                # Skip hidden content like script/style
                if child.tag not in ("script", "style", "noscript"):
                    parts.append(child.text)
        return clean_text(" ".join(parts))

    def find(
        self,
        tag: Optional[str] = None,
        attrs: Optional[Dict[str, Union[str, re.Pattern]]] = None,
    ) -> Optional[DOMNode]:
        """Finds the first descendant matching the tag and attributes."""
        for child in self.children:
            if isinstance(child, DOMNode):
                if self._matches(child, tag, attrs):
                    return child
                found = child.find(tag, attrs)
                if found:
                    return found
        return None

    def find_all(
        self,
        tag: Optional[str] = None,
        attrs: Optional[Dict[str, Union[str, re.Pattern]]] = None,
    ) -> List[DOMNode]:
        """Finds all descendants matching the tag and attributes."""
        results: List[DOMNode] = []
        for child in self.children:
            if isinstance(child, DOMNode):
                if self._matches(child, tag, attrs):
                    results.append(child)
                results.extend(child.find_all(tag, attrs))
        return results

    def select(self, selector: str) -> List[DOMNode]:
        """
        Supports CSS selector querying:
        - Tag: 'h1', 'article', 'div'
        - Class: '.card', '.price', 'div.item'
        - ID: '#main', 'article#intro'
        - Attributes: '[data-id]', 'meta[property="og:title"]'
        - Descendants: 'article h1', 'div.products > div.card'
        """
        tokens = selector.strip().split()
        current_candidates = [self]

        for token in tokens:
            if token == ">":
                continue  # next step will match direct children
            next_generation: List[DOMNode] = []
            for candidate in current_candidates:
                next_generation.extend(self._match_single_selector(candidate, token))
            current_candidates = next_generation
            if not current_candidates:
                break

        return current_candidates

    def _match_single_selector(self, parent: DOMNode, token: str) -> List[DOMNode]:
        """Matches a single selector token across all descendants of parent."""
        tag = None
        class_name = None
        elem_id = None
        attr_name = None
        attr_val = None

        # Check for attribute selector: e.g. meta[property="og:title"]
        attr_match = re.search(r"(\w+)?\[([\w:-]+)(?:=(?:[\"'])(.*?)(?:[\"']))?\]", token)
        if attr_match:
            tag = attr_match.group(1)
            attr_name = attr_match.group(2)
            attr_val = attr_match.group(3)
        elif "." in token:
            parts = token.split(".", 1)
            tag = parts[0] or None
            class_name = parts[1]
        elif "#" in token:
            parts = token.split("#", 1)
            tag = parts[0] or None
            elem_id = parts[1]
        else:
            tag = token

        def node_filter(node: DOMNode) -> bool:
            if tag and node.tag != tag.lower():
                return False
            if class_name:
                classes = node.get_attr("class", "").split()
                if class_name not in classes:
                    return False
            if elem_id and node.get_attr("id") != elem_id:
                return False
            if attr_name:
                v = node.get_attr(attr_name)
                if v is None:
                    return False
                if attr_val is not None and v != attr_val:
                    return False
            return True

        matches: List[DOMNode] = []
        for desc in parent.find_all():
            if node_filter(desc):
                matches.append(desc)
        return matches

    @staticmethod
    def _matches(
        node: DOMNode,
        tag: Optional[str],
        attrs: Optional[Dict[str, Union[str, re.Pattern]]],
    ) -> bool:
        if tag and node.tag != tag.lower():
            return False
        if attrs:
            for k, expected in attrs.items():
                val = node.get_attr(k)
                if val is None:
                    return False
                if isinstance(expected, re.Pattern):
                    if not expected.search(val):
                        return False
                elif expected != val:
                    return False
        return True

    def __repr__(self) -> str:
        attrs_str = " ".join(f'{k}="{v}"' for k, v in self.attrs.items())
        return f"<{self.tag} {attrs_str}>".strip() + ">"


class _DOMBuilder(HTMLParser):
    """Internal HTML parser that constructs a DOMNode tree."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = DOMNode(tag="[document]")
        self.current: DOMNode = self.root

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {k: v or "" for k, v in attrs}
        node = DOMNode(tag=tag_lower, attrs=attr_dict, parent=self.current)
        self.current.children.append(node)
        if tag_lower not in VOID_ELEMENTS:
            self.current = node

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in VOID_ELEMENTS:
            return

        # Walk up stack looking for matching open tag to handle malformed HTML
        temp = self.current
        while temp.parent and temp.tag != tag_lower:
            temp = temp.parent

        if temp.parent and temp.tag == tag_lower:
            self.current = temp.parent

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.current.children.append(data)


def parse_html(html_text: str) -> DOMNode:
    """Parses raw HTML text into a queryable DOMNode tree."""
    builder = _DOMBuilder()
    builder.feed(html_text)
    builder.close()
    return builder.root


# =====================================================================
# High-Level Specialized HTML Parsers
# =====================================================================


class MetadataExtractor(BaseParser):
    """Extracts OpenGraph, Twitter Cards, SEO meta, and JSON-LD structured data."""

    @property
    def name(self) -> str:
        return "metadata"

    def can_parse(self, content_type: str, raw_content: str) -> bool:
        return "<html" in raw_content.lower() or "<meta" in raw_content.lower()

    def parse(self, raw_content: str, target_url: str = "") -> Dict[str, Any]:
        root = parse_html(raw_content)

        # Standard Title
        title_node = root.find("title")
        title = clean_text(title_node.text) if title_node else ""

        # OpenGraph
        og_data: Dict[str, str] = {}
        for meta in root.find_all("meta"):
            prop = meta.get_attr("property", "") or meta.get_attr("name", "")
            if prop.startswith("og:"):
                key = prop[3:]
                og_data[key] = clean_text(meta.get_attr("content", ""))

        # Twitter Cards
        twitter_data: Dict[str, str] = {}
        for meta in root.find_all("meta"):
            name = meta.get_attr("name", "")
            if name.startswith("twitter:"):
                key = name[8:]
                twitter_data[key] = clean_text(meta.get_attr("content", ""))

        # Description
        desc_node = root.find("meta", {"name": "description"})
        description = clean_text(desc_node.get_attr("content", "")) if desc_node else ""
        if not description and "description" in og_data:
            description = og_data["description"]

        # Canonical URL
        canon_node = root.find("link", {"rel": "canonical"})
        canonical = canon_node.get_attr("href", "") if canon_node else ""
        if canonical:
            canonical = normalize_url(canonical, target_url)

        # JSON-LD structured blocks
        json_ld_blocks: List[Any] = []
        for script in root.find_all("script", {"type": "application/ld+json"}):
            script_text = script.text
            if script_text:
                try:
                    parsed = json.loads(script_text)
                    json_ld_blocks.append(parsed)
                except (json.JSONDecodeError, ValueError):
                    pass

        return {
            "title": og_data.get("title") or title,
            "description": description,
            "canonical_url": canonical,
            "opengraph": og_data,
            "twitter": twitter_data,
            "json_ld": json_ld_blocks,
        }


class ArticleExtractor(BaseParser):
    """Extracts articles, blog posts, documentation, and news stories."""

    @property
    def name(self) -> str:
        return "article"

    def can_parse(self, content_type: str, raw_content: str) -> bool:
        lower = raw_content.lower()
        return "<article" in lower or "<h1" in lower

    def parse(self, raw_content: str, target_url: str = "") -> Dict[str, Any]:
        root = parse_html(raw_content)

        # Article container detection
        article_node = root.find("article") or root.find("main") or root

        # Title
        h1 = article_node.find("h1") or root.find("h1")
        title = clean_text(h1.text) if h1 else ""
        if not title:
            title_node = root.find("title")
            title = clean_text(title_node.text) if title_node else "Untitled"

        # Author detection
        author = ""
        author_meta = root.find("meta", {"name": "author"})
        if author_meta:
            author = clean_text(author_meta.get_attr("content", ""))
        if not author:
            author_node = root.find(attrs={"rel": "author"}) or root.find(
                attrs={"class": re.compile(r"author|byline", re.I)}
            )
            if author_node:
                author = clean_text(author_node.text)

        # Published date
        published_at: Optional[str] = None
        time_node = root.find("time")
        if time_node:
            published_at = parse_datetime(time_node.get_attr("datetime") or time_node.text)
        if not published_at:
            pub_meta = root.find("meta", {"property": "article:published_time"})
            if pub_meta:
                published_at = parse_datetime(pub_meta.get_attr("content"))

        # Headings
        headings: List[Dict[str, str]] = []
        for h in article_node.find_all():
            if h.tag in ("h2", "h3"):
                headings.append({"level": h.tag, "text": clean_text(h.text)})

        # Body paragraphs
        paragraphs: List[str] = []
        for p in article_node.find_all("p"):
            txt = clean_text(p.text)
            if len(txt) > 20:  # Filter out trivial snippets
                paragraphs.append(txt)

        full_body = "\n\n".join(paragraphs)
        lead_summary = paragraphs[0] if paragraphs else ""

        # Tags / Keywords
        tags: List[str] = []
        tags_meta = root.find("meta", {"name": "keywords"})
        if tags_meta:
            tags = extract_tags(tags_meta.get_attr("content", ""))

        # Reading time estimate
        reading_time = estimate_reading_time(full_body)

        return {
            "title": title,
            "author": author or "Unknown",
            "published_at": published_at,
            "lead_summary": lead_summary,
            "body": full_body,
            "word_count": len(full_body.split()),
            "reading_time_minutes": reading_time,
            "headings": headings,
            "tags": tags,
        }


class CatalogExtractor(BaseParser):
    """Extracts product listings, catalog tables, and e-commerce cards."""

    @property
    def name(self) -> str:
        return "catalog"

    def can_parse(self, content_type: str, raw_content: str) -> bool:
        lower = raw_content.lower()
        return "product" in lower or "price" in lower or "item" in lower

    def parse(self, raw_content: str, target_url: str = "") -> Dict[str, Any]:
        root = parse_html(raw_content)

        # Find potential product container elements
        items: List[Dict[str, Any]] = []

        # Candidate item nodes: looking for cards or product containers
        candidate_nodes = (
            root.select(".product-card")
            or root.select(".product-item")
            or root.select(".product")
            or root.select(".item")
            or root.select("tr.product-row")
        )

        for node in candidate_nodes:
            # Title
            title_node = (
                node.find("h2")
                or node.find("h3")
                or node.find("h4")
                or node.find(attrs={"class": re.compile(r"title|name", re.I)})
            )
            title = clean_text(title_node.text) if title_node else ""
            if not title:
                continue

            # Price
            price_node = node.find(attrs={"class": re.compile(r"price|cost|amount", re.I)})
            price_text = price_node.text if price_node else ""
            amount, currency = parse_price(price_text)

            # Rating
            rating_node = node.find(attrs={"class": re.compile(r"rating|stars", re.I)})
            rating_val = None
            if rating_node:
                match = re.search(r"(\d+(?:\.\d+)?)", rating_node.text)
                if match:
                    try:
                        rating_val = float(match.group(1))
                    except ValueError:
                        pass

            # Link & Image
            link_node = node.find("a")
            product_url = normalize_url(link_node.get_attr("href", ""), target_url) if link_node else ""

            img_node = node.find("img")
            img_url = normalize_url(img_node.get_attr("src", ""), target_url) if img_node else ""

            # Availability
            avail_node = node.find(attrs={"class": re.compile(r"stock|availability", re.I)})
            in_stock = True
            if avail_node:
                txt = clean_text(avail_node.text).lower()
                if "out of stock" in txt or "unavailable" in txt or "sold out" in txt:
                    in_stock = False

            items.append({
                "title": title,
                "price": amount,
                "currency": currency or "USD",
                "rating": rating_val,
                "in_stock": in_stock,
                "url": product_url,
                "image_url": img_url,
            })

        return {
            "item_count": len(items),
            "items": items,
        }
