"""The one record shape every source is turned into.

Rules that hold for every record:
- nothing is invented: a value the source does not give is None and its
  field name is listed in missing_fields;
- content_hash covers what the source said, not our own bookkeeping, so it
  changes only when the notice itself changes.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

NOTICE_TYPES = (
    "general_procurement_notice",
    "invitation_for_bids",
    "expression_of_interest",
    "request_for_proposals",
    "contract_award",
    "other",
)
LANGUAGES = ("en", "fr", "pt", "other")
STATUSES = ("open", "closed", "awarded", "unknown")
MULTINATIONAL = "multinational"

# What the source told us. Order is the order records are written in.
CONTENT_FIELDS = (
    "notice_type",
    "notice_type_original",
    "title",
    "description",
    "country_code",
    "country_name",
    "country_original",
    "sector",
    "project_name",
    "project_id",
    "borrower_or_implementing_agency",
    "language",
    "published_date",
    "deadline",
    "source_url",
    "document_urls",
)
# Fields a reader would expect a value in; an empty one is reported as missing.
REPORTED_FIELDS = (
    "title",
    "description",
    "country_code",
    "country_name",
    "sector",
    "project_name",
    "project_id",
    "borrower_or_implementing_agency",
    "language",
    "published_date",
    "deadline",
    "source_url",
    "document_urls",
)
ALL_FIELDS = (
    ("id", "source")
    + CONTENT_FIELDS
    + ("status", "first_seen_at", "last_seen_at", "content_hash", "missing_fields", "extraction_notes", "history")
)
# Notice types that ask for a reply by a date, so a deadline is expected.
EXPECTS_DEADLINE = ("invitation_for_bids", "expression_of_interest", "request_for_proposals")


def _is_empty(value) -> bool:
    return value is None or value == "" or value == []


def missing_fields(record: dict) -> list[str]:
    missing = []
    for name in REPORTED_FIELDS:
        if not _is_empty(record.get(name)):
            continue
        # A notice covering several countries has no single code; that is not a gap.
        if name == "country_code" and record.get("country_name") == MULTINATIONAL:
            continue
        missing.append(name)
    return missing


def content_hash(record: dict) -> str:
    payload = {name: record.get(name) for name in CONTENT_FIELDS}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def status_for(record: dict, today: date) -> str:
    """Work out open / closed / awarded / unknown.

    Sources do not publish this directly, so it is derived: an award is
    "awarded"; a notice with a deadline is open until the day after that
    date; anything else is "unknown" rather than a guess.
    """
    if record.get("notice_type") == "contract_award":
        return "awarded"
    deadline = record.get("deadline")
    if deadline:
        try:
            deadline_day = date.fromisoformat(deadline[:10])
        except ValueError:
            return "unknown"
        return "open" if deadline_day >= today else "closed"
    return "unknown"


def finalize(record: dict) -> dict:
    """Fill in the derived fields and return the record in the standard order."""
    for name in CONTENT_FIELDS:
        record.setdefault(name, None)
    if record["document_urls"] is None:
        record["document_urls"] = []
    record.setdefault("extraction_notes", [])
    record["missing_fields"] = missing_fields(record)
    record["content_hash"] = content_hash(record)
    return {name: record.get(name) for name in ALL_FIELDS if name in record}


def validate(record: dict) -> list[str]:
    """Return a list of problems; empty means the record is well formed."""
    problems = []
    if not record.get("id") or ":" not in str(record.get("id")):
        problems.append("id is missing or not in 'source:number' form")
    if record.get("notice_type") not in NOTICE_TYPES:
        problems.append(f"notice_type {record.get('notice_type')!r} is not one of the allowed values")
    if record.get("language") is not None and record.get("language") not in LANGUAGES:
        problems.append(f"language {record.get('language')!r} is not one of the allowed values")
    for name in ("published_date", "deadline"):
        value = record.get(name)
        if value:
            try:
                date.fromisoformat(value[:10])
            except ValueError:
                problems.append(f"{name} {value!r} is not an ISO date")
    code = record.get("country_code")
    if code is not None and not (isinstance(code, str) and len(code) == 2 and code.isupper()):
        problems.append(f"country_code {code!r} is not a two-letter code")
    return problems
