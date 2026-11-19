"""Copy notices to a Notion database for review.

The repo stays the source of truth; Notion is a window onto it. Only new
and changed notices are sent. The "Checked" box and the "Problem" column
belong to the reviewer and are never written by this code.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests

from . import store

API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
STATE_FILE = Path("data/notion_pages.json")
SECONDS_BETWEEN_REQUESTS = 0.35  # Notion allows about three requests a second
TEXT_LIMIT = 1900

# Column name -> Notion column type. The title column is found by type, whatever it is called.
COLUMNS = {
    "Notice ID": {"rich_text": {}},
    "Source": {"select": {}},
    "Type": {"select": {}},
    "Original type": {"rich_text": {}},
    "Description": {"rich_text": {}},
    "Country": {"select": {}},
    "Country code": {"rich_text": {}},
    "Sector": {"rich_text": {}},
    "Project": {"rich_text": {}},
    "Project ID": {"rich_text": {}},
    "Agency": {"rich_text": {}},
    "Language": {"select": {}},
    "Published": {"date": {}},
    "Deadline": {"date": {}},
    "Deadline time (local)": {"rich_text": {}},
    "Status": {"select": {}},
    "Link": {"url": {}},
    "Documents": {"rich_text": {}},
    "Missing fields": {"multi_select": {}},
    "Notes": {"rich_text": {}},
    "First seen": {"date": {}},
    "Checked": {"checkbox": {}},
    "Problem": {"rich_text": {}},
}
REVIEWER_COLUMNS = ("Checked", "Problem")


def _text(value) -> dict:
    value = "" if value is None else str(value)
    return {"rich_text": [{"text": {"content": value[:TEXT_LIMIT]}}] if value else []}


def _select(value) -> dict:
    # Notion does not allow commas in an option name.
    return {"select": {"name": str(value).replace(",", " ·")[:100]} if value else None}


def _date(value) -> dict:
    return {"date": {"start": value[:10]} if value else None}


def properties_for(record: dict, title_column: str) -> dict:
    deadline = record.get("deadline") or ""
    title = record.get("title") or record["id"]
    return {
        title_column: {"title": [{"text": {"content": title[:TEXT_LIMIT]}}]},
        "Notice ID": _text(record["id"]),
        "Source": _select(record.get("source")),
        "Type": _select(record.get("notice_type")),
        "Original type": _text(record.get("notice_type_original")),
        "Description": _text(record.get("description")),
        "Country": _select(record.get("country_name")),
        "Country code": _text(record.get("country_code")),
        "Sector": _text(record.get("sector")),
        "Project": _text(record.get("project_name")),
        "Project ID": _text(record.get("project_id")),
        "Agency": _text(record.get("borrower_or_implementing_agency")),
        "Language": _select(record.get("language")),
        "Published": _date(record.get("published_date")),
        "Deadline": _date(deadline),
        "Deadline time (local)": _text(deadline[11:16] if len(deadline) > 10 else None),
        "Status": _select(record.get("status")),
        "Link": {"url": record.get("source_url") or None},
        "Documents": _text("\n".join(record.get("document_urls") or [])),
        "Missing fields": {"multi_select": [{"name": name} for name in record.get("missing_fields", [])]},
        "Notes": _text("; ".join(record.get("extraction_notes") or [])),
        "First seen": _date(record.get("first_seen_at")),
    }


class NotionClient:
    def __init__(self, token: str, session=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        self._sleep = sleep

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        for attempt in range(5):
            self._sleep(SECONDS_BETWEEN_REQUESTS)
            response = self.session.request(method, f"{API}{path}", headers=self.headers, json=body, timeout=60)
            if response.status_code == 429 or response.status_code >= 500:
                wait = response.headers.get("Retry-After", "")
                self._sleep(float(wait) if wait.replace(".", "", 1).isdigit() else 2.0 * (attempt + 1))
                continue
            if response.status_code >= 400:
                try:
                    message = response.json().get("message", "")
                except ValueError:
                    message = ""
                raise RuntimeError(f"Notion said no ({response.status_code}): {message}")
            return response.json()
        raise RuntimeError("Notion kept answering 'too busy'; giving up for this run")


def ensure_columns(client: NotionClient, database_id: str) -> str:
    """Add any column the database lacks. Returns the name of its title column."""
    database = client.call("GET", f"/databases/{database_id}")
    existing = database.get("properties", {})
    title_column = next(name for name, spec in existing.items() if spec.get("type") == "title")
    missing = {name: spec for name, spec in COLUMNS.items() if name not in existing}
    if missing:
        client.call("PATCH", f"/databases/{database_id}", {"properties": missing})
    return title_column


def sync(client: NotionClient, database_id: str, notices: dict[str, dict], state: dict, limit: int | None = None) -> dict:
    """Send new and changed notices. Returns counts; `state` is updated in place."""
    title_column = ensure_columns(client, database_id)
    counts = {"created": 0, "updated": 0, "unchanged": 0, "failed": 0}
    errors: list[str] = []
    for notice_id in sorted(notices):
        record = notices[notice_id]
        fingerprint = f"{record.get('content_hash')}:{record.get('status')}"
        known = state.get(notice_id)
        if known and known.get("sent") == fingerprint:
            counts["unchanged"] += 1
            continue
        if limit is not None and counts["created"] + counts["updated"] >= limit:
            break
        properties = properties_for(record, title_column)
        try:
            if known:
                client.call("PATCH", f"/pages/{known['page']}", {"properties": properties})
                counts["updated"] += 1
            else:
                page = client.call("POST", "/pages", {"parent": {"database_id": database_id}, "properties": properties})
                known = {"page": page["id"]}
                state[notice_id] = known
                counts["created"] += 1
            known["sent"] = fingerprint
        except RuntimeError as error:
            counts["failed"] += 1
            errors.append(f"{notice_id}: {error}")
            if counts["failed"] >= 5:
                errors.append("stopping after 5 failures")
                break
    counts["errors"] = errors
    return counts


def main(root: Path = Path(".")) -> int:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    database_id = os.environ.get("NOTION_DATABASE_ID", "").strip()
    if not token or not database_id:
        print("Notion is not set up (NOTION_TOKEN or NOTION_DATABASE_ID is empty). Skipping the copy to Notion.")
        return 0
    limit = os.environ.get("NOTION_LIMIT", "").strip()
    state_file = root / STATE_FILE
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    notices = store.load(root / store.DATA_FILE)
    client = NotionClient(token)
    try:
        counts = sync(client, database_id, notices, state, limit=int(limit) if limit else None)
    except RuntimeError as error:
        print(f"Copy to Notion failed: {error}")
        return 1
    finally:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=0, sort_keys=True) + "\n", encoding="utf-8")
    errors = counts.pop("errors")
    print(f"Notion: {counts}")
    for line in errors:
        print(f"  {line}")
    return 1 if counts["failed"] else 0
