"""Polite fetching: one named bot, one request a second per site, patient retries.

A refusal aimed at bots (a "prove you are a browser" challenge, or a
robots.txt rule) is never retried or worked around: it raises Blocked and
the source is reported as blocked.
"""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

from . import __version__

REPO_URL = "https://github.com/stopjetski/tender-watch"
USER_AGENT = f"tender-watch/{__version__} (+{REPO_URL})"
MIN_SECONDS_BETWEEN_REQUESTS = 1.0
RETRY_STATUSES = {429, 500, 502, 503, 504}


class Blocked(Exception):
    """The site refused automated access. Stop; do not retry."""


class FetchFailed(Exception):
    """The request kept failing after all retries."""


def looks_like_challenge(response) -> bool:
    if response.headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    if response.status_code in (403, 503):
        start = response.text[:2000].lower() if response.content else ""
        return "just a moment" in start or "enable javascript and cookies" in start
    return False


class PoliteSession:
    def __init__(self, session=None, sleep=time.sleep, clock=time.monotonic, retries: int = 4, timeout: int = 60):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
        self._sleep = sleep
        self._clock = clock
        self._retries = retries
        self._timeout = timeout
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.request_count: dict[str, int] = {}

    def _wait_turn(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            remaining = MIN_SECONDS_BETWEEN_REQUESTS - (self._clock() - last)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._clock()
        self.request_count[host] = self.request_count.get(host, 0) + 1

    def _raw_get(self, url: str, **kwargs):
        host = urlsplit(url).netloc
        delay = 2.0
        last_error = None
        for attempt in range(self._retries + 1):
            self._wait_turn(host)
            try:
                response = self.session.get(url, timeout=self._timeout, **kwargs)
            except requests.RequestException as error:
                last_error = repr(error)
            else:
                if looks_like_challenge(response):
                    raise Blocked(f"{host} answered with a browser challenge (HTTP {response.status_code})")
                if response.status_code not in RETRY_STATUSES:
                    return response
                last_error = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, min(float(retry_after), 120.0))
            if attempt < self._retries:
                self._sleep(delay)
                delay = min(delay * 2, 60.0)
        raise FetchFailed(f"{url}: {last_error} after {self._retries + 1} attempts")

    def robots_allow(self, url: str) -> bool:
        parts = urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            response = self._raw_get(f"{parts.scheme}://{host}/robots.txt")
            if response.status_code == 200:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(response.text.splitlines())
                self._robots[host] = parser
            elif response.status_code in (401, 403):
                # A site that will not show its rules is treated as saying no.
                raise Blocked(f"{host} refused to show robots.txt (HTTP {response.status_code})")
            else:
                self._robots[host] = None  # no robots.txt: nothing is disallowed
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)

    def get(self, url: str, **kwargs):
        if not self.robots_allow(url):
            raise Blocked(f"robots.txt on {urlsplit(url).netloc} disallows {url}")
        response = self._raw_get(url, **kwargs)
        if response.status_code in (401, 403):
            raise Blocked(f"{url} answered HTTP {response.status_code}")
        if response.status_code >= 400:
            raise FetchFailed(f"{url}: HTTP {response.status_code}")
        return response
