"""African Development Bank project procurement notices.

Not collecting yet. afdb.org answered this project's first requests with a
browser challenge, so nothing about its pages could be read (see RECON.md).
What is here: an access check that asks for robots.txt once and reports
honestly what came back. The parsers get written once the Bank lets the bot
in, from real saved pages.
"""
from __future__ import annotations

from datetime import date

from ..http import Blocked, FetchFailed
from .base import SourceResult

NAME = "afdb"
ROBOTS_URL = "https://www.afdb.org/robots.txt"
LISTING_URL = "https://www.afdb.org/en/projects-and-operations/procurement"


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
