"""The notices file: one record per line, sorted by id, kept in the repo.

Merging rules: a notice is matched by id. A new id is "new". A known id
whose content changed is "updated", and the old values of the changed
fields go into its history list. Rows are never dropped.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .schema import ALL_FIELDS, CONTENT_FIELDS, missing_fields, status_for

DATA_FILE = Path("data/notices.jsonl")


def load(path: Path = DATA_FILE) -> dict[str, dict]:
    if not path.exists():
        return {}
    notices = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                notices[record["id"]] = record
    return notices


def save(notices: dict[str, dict], path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for key in sorted(notices):
            record = notices[key]
            ordered = {name: record[name] for name in ALL_FIELDS if name in record}
            handle.write(json.dumps(ordered, ensure_ascii=False) + "\n")


def merge(notices: dict[str, dict], fresh: list[dict], now_iso: str) -> dict[str, list[str]]:
    """Fold freshly collected records into the store. Returns ids by outcome."""
    outcome = {"new": [], "updated": [], "unchanged": []}
    for record in fresh:
        known = notices.get(record["id"])
        if known is None:
            record = dict(record)
            record["first_seen_at"] = now_iso
            record["last_seen_at"] = now_iso
            record["history"] = []
            record.setdefault("status", "unknown")
            notices[record["id"]] = record
            outcome["new"].append(record["id"])
            continue
        known["last_seen_at"] = now_iso
        if known.get("content_hash") == record["content_hash"]:
            outcome["unchanged"].append(record["id"])
            continue
        changed = {name: known.get(name) for name in CONTENT_FIELDS if known.get(name) != record.get(name)}
        known.setdefault("history", []).append({"changed_at": now_iso, "previous": changed})
        for name in CONTENT_FIELDS:
            known[name] = record.get(name)
        known["extraction_notes"] = record.get("extraction_notes", [])
        known["missing_fields"] = missing_fields(known)
        known["content_hash"] = record["content_hash"]
        outcome["updated"].append(record["id"])
    return outcome


def refresh_statuses(notices: dict[str, dict], today: date) -> dict[str, list[str]]:
    """Recompute every status (deadlines pass with time). Returns ids that just closed, by source."""
    closed: dict[str, list[str]] = {}
    for record in notices.values():
        before = record.get("status")
        after = status_for(record, today)
        record["status"] = after
        if after == "closed" and before == "open":
            closed.setdefault(record["source"], []).append(record["id"])
    return closed
