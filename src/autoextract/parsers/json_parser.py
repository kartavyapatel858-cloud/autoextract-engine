"""
JSON and API Payload Extraction Engine.
Supports dot-notation path navigation and structured flattening.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from autoextract.core.exceptions import ParseError
from autoextract.parsers.base import BaseParser


def query_json_path(data: Any, path: str) -> Any:
    """
    Evaluates dot-notation queries against arbitrary JSON structures.
    Examples:
      - 'items' -> data['items']
      - 'items[0]' -> data['items'][0]
      - 'items.*.id' -> [item['id'] for item in data['items']]
      - 'data.profile.email' -> data['data']['profile']['email']
    """
    if not path or path == ".":
        return data

    parts = path.strip().split(".")
    curr = data

    for part in parts:
        if curr is None:
            return None

        # Wildcard list expansion: e.g. '*'
        if part == "*":
            curr = curr if isinstance(curr, list) else [curr]
            continue

        # Array indexing: e.g. 'users[0]'
        if "[" in part and part.endswith("]"):
            base_key, index_str = part[:-1].split("[", 1)
            try:
                idx = int(index_str)
            except ValueError:
                return None

            if base_key:
                if not isinstance(curr, dict) or base_key not in curr:
                    return None
                curr = curr[base_key]

            if isinstance(curr, list) and 0 <= idx < len(curr):
                curr = curr[idx]
            else:
                return None
        elif isinstance(curr, dict):
            curr = curr.get(part)
        elif isinstance(curr, list):
            # If current is list and we have a key, map over list items
            res = []
            for item in curr:
                if isinstance(item, dict) and part in item:
                    res.append(item[part])
            curr = res
        else:
            return None

    return curr


class JSONParser(BaseParser):
    """Parses JSON responses, structured API payloads, and local JSON files."""

    def __init__(self, target_path: Optional[str] = None) -> None:
        self.target_path = target_path

    @property
    def name(self) -> str:
        return "json"

    def can_parse(self, content_type: str, raw_content: str) -> bool:
        ct = content_type.lower()
        if "json" in ct:
            return True
        stripped = raw_content.strip()
        return (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        )

    def parse(self, raw_content: str, target_url: str = "") -> Dict[str, Any]:
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ParseError(
                f"Invalid JSON payload: {exc}", parser_name=self.name
            ) from exc

        if self.target_path:
            extracted = query_json_path(payload, self.target_path)
        else:
            extracted = payload

        # Calculate metadata
        is_list = isinstance(extracted, list)
        count = len(extracted) if is_list else 1

        return {
            "is_collection": is_list,
            "item_count": count,
            "payload": extracted,
        }
