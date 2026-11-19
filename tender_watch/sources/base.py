"""What every bank's collector hands back."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceResult:
    source: str
    notices: list[dict] = field(default_factory=list)  # finished records
    seen: int = 0  # notices the source listed inside the look-back window
    parse_errors: list[str] = field(default_factory=list)  # one line per notice that could not be read
    could_not_extract: list[str] = field(default_factory=list)  # fields we looked for and did not find
    fatal: str | None = None  # the whole source failed (blocked, down, changed shape)
    blocked: bool = False
    requests: int = 0
