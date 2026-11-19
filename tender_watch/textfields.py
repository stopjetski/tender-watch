"""Finding a deadline in free text (the body of a notice or a PDF).

No AI: a list of the phrases banks use before a closing date, in English,
French, Portuguese and Spanish, then the first date that follows one of
them. When nothing matches the answer is None, never a guess.
"""
from __future__ import annotations

import re
import unicodedata

from .dates import find_dates

# Strongest phrases first. Matched against text with accents removed.
CUES = (
    r"date limite",
    r"date de cloture",
    r"date et heure limites?",
    r"au plus tard",
    r"closing date",
    r"deadline",
    r"no later than",
    r"not later than",
    r"on or before",
    r"data limite",
    r"prazo",
    r"o mais tardar",
    r"fecha limite",
    r"a mas tardar",
    r"must be (?:delivered|submitted|received)",
    r"doivent etre (?:deposees|soumises|remises|envoyees|recues)",
    r"avant le",
    r"\bate (?:as|ao|o dia)",
)
REACH = 220  # how far after the phrase a date may sit
_TIME = re.compile(r"\b(\d{1,2})\s*(?:[:hH]|heures?)\s*(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?", re.IGNORECASE)


def _fold(text: str) -> str:
    """Lower-case, accents removed, same length as the input so positions line up."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in base if not unicodedata.combining(c)) or " "
        out.append(base[0].lower())
    return "".join(out)


def find_deadline(text: str | None) -> tuple[str | None, str | None]:
    """Return (ISO date, the phrase that led to it), or (None, None)."""
    if not text:
        return None, None
    dates = find_dates(text)
    if not dates:
        return None, None
    folded = _fold(text)
    best = None
    for rank, cue in enumerate(CUES):
        for match in re.finditer(cue, folded):
            for position, iso in dates:
                if match.start() <= position <= match.end() + REACH:
                    candidate = (rank, match.start(), iso, match.group(0))
                    if best is None or candidate < best:
                        best = candidate
                    break
        if best is not None and best[0] == rank:
            break
    if best is None:
        return None, None
    return best[2], best[3]
