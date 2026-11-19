"""African Development Bank project procurement notices.

Not collecting yet. afdb.org answered this project's first requests with a
browser challenge, so nothing about its pages could be read (see RECON.md).
What is here: an access check that asks for robots.txt once and reports
honestly what came back. The parsers get written once the Bank lets the bot
in, from real saved pages.
"""
from __future__ import annotations

import urllib.robotparser
from datetime import date

from ..http import USER_AGENT, Blocked, FetchFailed
from .base import SourceResult

NAME = "afdb"
ROBOTS_URL = "https://www.afdb.org/robots.txt"
LISTING_URL = "https://www.afdb.org/en/projects-and-operations/procurement"


def access_check(session) -> dict:
    """Ask for robots.txt once and say plainly what came back. One request, no retry on a refusal."""
    try:
        response = session._raw_get(ROBOTS_URL)
    except Blocked as error:
        return {"let_in": False, "reason": str(error), "robots_txt": None}
    except FetchFailed as error:
        return {"let_in": False, "reason": f"could not reach the site: {error}", "robots_txt": None}
    if response.status_code != 200:
        return {"let_in": False, "reason": f"robots.txt answered HTTP {response.status_code}", "robots_txt": None}
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(response.text.splitlines())
    allowed = parser.can_fetch(USER_AGENT, LISTING_URL)
    reason = "robots.txt allows the procurement pages" if allowed else "robots.txt disallows the procurement pages for this bot"
    return {"let_in": allowed, "reason": reason, "robots_txt": response.text}


def collect(session, today: date, lookback_days: int = 7) -> SourceResult:
    result = SourceResult(source=NAME)
    try:
        allowed = session.robots_allow(LISTING_URL)
    except Blocked as error:
        result.blocked = True
        result.fatal = f"blocked: {error}"
        return result
    except FetchFailed as error:
        result.fatal = f"could not reach the site: {error}"
        return result
    if not allowed:
        result.blocked = True
        result.fatal = "blocked: robots.txt disallows the procurement pages for this bot"
        return result
    result.fatal = "the site let the bot in, but the page parsers are not written yet (see RECON.md)"
    return result
