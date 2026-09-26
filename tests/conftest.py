"""Shared pytest fixtures."""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakeResponse:
    def __init__(self, text: str = "", status_code: int = 200, headers: dict | None = None):
        self.text, self.status_code, self.headers = text, status_code, headers or {}

    @property
    def ok(self) -> bool:
        return self.status_code < 400


class FakeSession:
    """Stands in for requests.Session: serves fixture pages by the `page` query param.

    `responses` may map page -> FakeResponse or list of FakeResponses (consumed in
    order), to simulate 429s/5xx before success.
    """

    def __init__(self, responses: dict | None = None):
        self.headers: dict = {}
        self.urls: list[str] = []
        self.responses = responses

    def get(self, url, timeout=None):
        self.urls.append(url)
        page = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query)).get("page", "1")
        if self.responses is not None:
            resp = self.responses[int(page)]
            return resp.pop(0) if isinstance(resp, list) else resp
        path = FIXTURES / f"blocket_search_p{page}.json"
        if not path.exists():
            return FakeResponse('{"docs": [], "metadata": {"is_end_of_paging": true}}')
        return FakeResponse(path.read_text(encoding="utf-8"))


@pytest.fixture
def fake_session():
    return FakeSession()


@pytest.fixture
def fixtures_dir():
    return FIXTURES
