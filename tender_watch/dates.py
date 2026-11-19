"""Dates as banks write them (English, French, Portuguese, Spanish) -> ISO 8601."""
from __future__ import annotations

import re
import unicodedata
from datetime import date

MONTHS = {}
for number, names in enumerate(
    (
        ("january", "jan", "janvier", "janv", "janeiro", "enero"),
        ("february", "feb", "fevrier", "fevr", "fev", "fevereiro", "febrero"),
        ("march", "mar", "mars", "marco", "marzo"),
        ("april", "apr", "avril", "avr", "abril"),
        ("may", "mai", "maio", "mayo"),
        ("june", "jun", "juin", "junho", "junio"),
        ("july", "jul", "juillet", "juil", "julho", "julio"),
        ("august", "aug", "aout", "agosto"),
        ("september", "sep", "sept", "septembre", "setembro", "septiembre"),
        ("october", "oct", "octobre", "outubro", "octubre"),
        ("november", "nov", "novembre", "novembro", "noviembre"),
        ("december", "dec", "decembre", "dezembro", "diciembre"),
    ),
    start=1,
):
    for name in names:
        MONTHS[name] = number

_MONTH_WORD = r"[A-Za-zÀ-ÿ]{3,10}\.?"
_DAY_MONTH_YEAR = re.compile(rf"\b(\d{{1,2}})(?:\s*(?:st|nd|rd|th|er|ème|eme|º))?[\s,.\-/]+(?:de\s+)?({_MONTH_WORD})[\s,.\-/]+(?:de\s+)?(\d{{4}})\b")
_MONTH_DAY_YEAR = re.compile(rf"\b({_MONTH_WORD})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b")
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_YMD_SLASH = re.compile(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b")
_DMY_NUMERIC = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower().rstrip(".")


def _month(word: str) -> int | None:
    return MONTHS.get(_fold(word))


def _make(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def find_dates(text: str) -> list[tuple[int, str]]:
    """Every date found in the text, as (position, ISO date), in reading order.

    All-number dates such as 03/04/2026 are read day first, the convention in
    the countries these banks lend to; that reading is an assumption and the
    caller should say so in extraction_notes.
    """
    found: dict[int, str] = {}
    for match in _DAY_MONTH_YEAR.finditer(text):
        month = _month(match.group(2))
        if month:
            iso = _make(int(match.group(3)), month, int(match.group(1)))
            if iso:
                found[match.start()] = iso
    for match in _MONTH_DAY_YEAR.finditer(text):
        month = _month(match.group(1))
        if month:
            iso = _make(int(match.group(3)), month, int(match.group(2)))
            if iso:
                found.setdefault(match.start(), iso)
    for match in _ISO.finditer(text):
        iso = _make(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.setdefault(match.start(), iso)
    for match in _YMD_SLASH.finditer(text):
        iso = _make(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.setdefault(match.start(), iso)
    for match in _DMY_NUMERIC.finditer(text):
        iso = _make(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if iso:
            found.setdefault(match.start(), iso)
    return sorted(found.items())


def parse_date(text: str | None) -> str | None:
    """The first date in a short piece of text, or None."""
    if not text:
        return None
    dates = find_dates(text)
    return dates[0][1] if dates else None
