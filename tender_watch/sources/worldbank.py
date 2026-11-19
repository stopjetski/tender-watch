"""World Bank procurement notices, from the Bank's own search API.

The API lists newest first and ignores date filters, so each run reads
pages from the top until it passes the look-back window.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .. import countries
from ..schema import finalize, validate
from .base import SourceResult

NAME = "worldbank"
API_URL = "https://search.worldbank.org/api/v2/procnotices"
DETAIL_URL = "https://projects.worldbank.org/en/projects-operations/procurement-detail/{id}"
PAGE_SIZE = 500
MAX_PAGES = 20  # safety stop: 10,000 notices is far beyond a week's worth
# Only the fields we use. Contact names, e-mails and phone numbers are left
# out on purpose: the Bank's terms forbid collecting personal information.
FIELDS = (
    "id,notice_type,noticedate,notice_lang_code,notice_lang_name,notice_status,notice_version_no,"
    "noticetitle,bid_description,bid_reference_no,project_ctry_code,project_ctry_name,project_id,"
    "project_name,sector,procurement_major_sector_name,agency_name,procurement_method_name,"
    "submission_deadline_date,submission_deadline_time"
)

NOTICE_TYPES = {
    "general procurement notice": "general_procurement_notice",
    "invitation for bids": "invitation_for_bids",
    "request for expression of interest": "expression_of_interest",
    "request for proposals": "request_for_proposals",
    "contract award": "contract_award",
    "goods and works award": "contract_award",
    "small contracts award": "contract_award",
}
LANGUAGES = {"EN": "en", "FR": "fr", "PT": "pt"}


def _text(value) -> str | None:
    if value is None:
        return None
    value = " ".join(str(value).split())
    return value or None


def parse_notice_date(value: str | None) -> str | None:
    """'18-Nov-2026' -> '2026-11-18'."""
    if not value:
        return None
    return datetime.strptime(value.strip(), "%d-%b-%Y").date().isoformat()


def parse_deadline(day: str | None, clock: str | None) -> tuple[str | None, list[str]]:
    """The API gives the day as '2026-12-02T00:00:00Z' and the hour apart, as '16:00'.

    The 'Z' is how the API writes every date, not a statement that the
    deadline is in UTC: the hour is local to the buyer and no timezone is
    given. So the result carries no timezone, and a note says so.
    """
    if not day:
        return None, []
    day_part = date.fromisoformat(day[:10]).isoformat()
    clock = (clock or "").strip()
    if clock:
        hour, minute = clock.split(":")[:2]
        notes = ["deadline time is local to the buyer; the source states no timezone"]
        if int(hour) == 0 and int(minute) == 0:
            notes.append("source gives the time as 00:00, which may mean no time was entered")
        return f"{day_part}T{int(hour):02d}:{int(minute):02d}:00", notes
    return day_part, ["deadline has a date but no time in the source"]


def parse_notice(raw: dict) -> dict:
    """One API record -> one record in our format. Raises on a record it cannot read."""
    notice_id = _text(raw.get("id"))
    if not notice_id:
        raise ValueError("record has no id")
    notes: list[str] = []
    label = _text(raw.get("notice_type"))
    notice_type = NOTICE_TYPES.get((label or "").lower())
    if notice_type is None:
        notice_type = "other"
        if label is None:
            notes.append("source gives no notice type")
    code, country_name, country_note = countries.from_world_bank(raw.get("project_ctry_code"), raw.get("project_ctry_name"))
    if country_note:
        notes.append(country_note)
    sectors = raw.get("sector") or []
    sector_names = [_text(item.get("sector_description")) for item in sectors if isinstance(item, dict)]
    sector = "; ".join(name for name in sector_names if name) or _text(raw.get("procurement_major_sector_name"))
    lang_code = (_text(raw.get("notice_lang_code")) or "").upper()
    language = LANGUAGES.get(lang_code, "other") if lang_code else None
    if language == "other":
        notes.append(f"source language: {_text(raw.get('notice_lang_name')) or lang_code}")
    deadline, deadline_notes = parse_deadline(raw.get("submission_deadline_date"), raw.get("submission_deadline_time"))
    notes.extend(deadline_notes)
    record = {
        "id": f"{NAME}:{notice_id}",
        "source": NAME,
        "notice_type": notice_type,
        "notice_type_original": label,
        "title": _text(raw.get("noticetitle")) or _text(raw.get("bid_description")),
        "description": _text(raw.get("bid_description")),
        "country_code": code,
        "country_name": country_name,
        "country_original": _text(raw.get("project_ctry_name")),
        "sector": sector,
        "project_name": _text(raw.get("project_name")),
        "project_id": _text(raw.get("project_id")),
        "borrower_or_implementing_agency": _text(raw.get("agency_name")),
        "language": language,
        "published_date": parse_notice_date(raw.get("noticedate")),
        "deadline": deadline,
        "source_url": DETAIL_URL.format(id=notice_id),
        # The API carries the notice text itself and lists no attached files.
        "document_urls": [],
        "extraction_notes": notes,
    }
    record = finalize(record)
    problems = validate(record)
    if problems:
        raise ValueError("; ".join(problems))
    return record


def parse_page(payload: dict) -> tuple[list[dict], list[str]]:
    """One API page -> (records, error lines). Raises if the page has the wrong shape."""
    if not isinstance(payload, dict) or not isinstance(payload.get("procnotices"), list):
        raise ValueError("reply has no 'procnotices' list; the API may have changed")
    records, errors = [], []
    for raw in payload["procnotices"]:
        try:
            records.append(parse_notice(raw))
        except Exception as error:  # noqa: BLE001 - one bad notice must not sink the page
            errors.append(f"{raw.get('id', '?') if isinstance(raw, dict) else '?'}: {error}")
    return records, errors


def collect(session, today: date, lookback_days: int = 7) -> SourceResult:
    result = SourceResult(source=NAME)
    cutoff = (today - timedelta(days=lookback_days)).isoformat()
    seen_ids: set[str] = set()
    for page in range(MAX_PAGES):
        params = {"format": "json", "rows": PAGE_SIZE, "os": page * PAGE_SIZE, "fl": FIELDS}
        response = session.get(API_URL, params=params)
        records, errors = parse_page(response.json())
        result.parse_errors.extend(errors)
        if not records and not errors:
            break
        in_window = [r for r in records if r["published_date"] is None or r["published_date"] >= cutoff]
        for record in in_window:
            if record["id"] not in seen_ids:
                seen_ids.add(record["id"])
                result.notices.append(record)
        dated = [r["published_date"] for r in records if r["published_date"]]
        if dated and min(dated) < cutoff:
            break
    result.seen = len(result.notices) + len(result.parse_errors)
    return result
