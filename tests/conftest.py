import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def wb_page():
    def load(name: str) -> dict:
        return json.loads((FIXTURES / "worldbank" / f"{name}.json").read_text(encoding="utf-8"))

    return load


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None, payload=None, content=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload
        self.text = text if payload is None else json.dumps(payload)
        self.content = content if content is not None else self.text.encode("utf-8")

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


class FakeRequestsSession:
    """Stands in for requests.Session: answers from a list or a function, records every call."""

    def __init__(self, answer):
        self.headers = {}
        self.calls = []
        self._answer = answer

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._answer(url, kwargs) if callable(self._answer) else self._answer.pop(0)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def fake_response():
    return FakeResponse


@pytest.fixture
def fake_requests():
    return FakeRequestsSession


@pytest.fixture
def fake_clock():
    return FakeClock()
