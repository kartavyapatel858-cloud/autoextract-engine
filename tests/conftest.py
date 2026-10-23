"""Pytest configuration and shared fixtures."""

import sys
from pathlib import Path
import pytest

# Ensure src is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

FIXTURES_DIR = PROJECT_ROOT / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_article_html(fixtures_dir: Path) -> str:
    path = fixtures_dir / "sample_article.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def sample_catalog_html(fixtures_dir: Path) -> str:
    path = fixtures_dir / "sample_catalog.html"
    return path.read_text(encoding="utf-8")


@pytest.fixture
def sample_api_json(fixtures_dir: Path) -> str:
    path = fixtures_dir / "sample_api.json"
    return path.read_text(encoding="utf-8")
