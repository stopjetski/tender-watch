"""The daily report, the run log and the breakage alarm."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import EXPECTS_DEADLINE, MULTINATIONAL, REPORTED_FIELDS

RUNS_FILE = Path("data/runs.json")
REPORTS_DIR = Path("reports")
MAX_PARSE_ERROR_SHARE = 0.10
ERROR_LINES_SHOWN = 20


def completeness(records: list[dict]) -> dict:
    """Share of records with a value, per field, as whole percentages."""
    total = len(records)
    if total == 0:
        return {"notices": 0, "fields": {}, "deadline_where_expected": None, "multinational": 0}
    fields = {}
    for name in REPORTED_FIELDS:
        filled = sum(1 for r in records if name not in r.get("missing_fields", []))
        fields[name] = round(100 * filled / total)
    expecting = [r for r in records if r.get("notice_type") in EXPECTS_DEADLINE]
    with_deadline = sum(1 for r in expecting if r.get("deadline"))
    return {
        "notices": total,
        "fields": fields,
        "deadline_where_expected": round(100 * with_deadline / len(expecting)) if expecting else None,
        "deadline_expected_on": len(expecting),
        "multinational": sum(1 for r in records if r.get("country_name") == MULTINATIONAL),
    }


def load_runs(path: Path = RUNS_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_runs(runs: list[dict], path: Path = RUNS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(runs, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def seven_day_average(runs: list[dict], source: str, before_date: str) -> float | None:
    """Average 'seen' over the last seven earlier days that have a good run."""
    by_date: dict[str, int] = {}
    for run in runs:
        entry = run.get("sources", {}).get(source)
        if run["date"] >= before_date or not entry or not entry.get("enabled") or entry.get("fatal"):
            continue
        by_date[run["date"]] = entry.get("seen", 0)  # the last run of a day wins
    recent = [by_date[day] for day in sorted(by_date)[-7:]]
    return sum(recent) / len(recent) if recent else None


def alarms_for(source: str, entry: dict, average: float | None) -> list[str]:
    """Reasons this source should fail the run. Empty means healthy."""
    if not entry.get("enabled"):
        return []
    reasons = []
    if entry.get("fatal"):
        reasons.append(f"{source}: the source failed: {entry['fatal']}")
        return reasons
    seen = entry.get("seen", 0)
    if seen == 0:
        reasons.append(f"{source}: returned 0 notices")
    elif average is not None and seen < average / 2:
        reasons.append(f"{source}: returned {seen} notices, fewer than half its 7-day average of {average:.0f}")
    errors = entry.get("parse_errors", 0)
    if seen and errors / seen > MAX_PARSE_ERROR_SHARE:
        reasons.append(f"{source}: {errors} of {seen} notices could not be read ({100 * errors / seen:.0f}%, limit 10%)")
    return reasons


def _status_words(entry: dict) -> str:
    if not entry.get("enabled"):
        return "switched off"
    if entry.get("blocked"):
        return "blocked by the site"
    if entry.get("fatal"):
        return "failed"
    return "collected"


def render(run: dict, alarms: list[str], total_on_file: int, details: dict) -> str:
    lines = [
        f"# Daily report: {run['date']}",
        "",
        f"Run started {run['started_at']} (the date above is the Singapore date). Notices on file: {total_on_file}.",
        "",
        "## Alarm",
        "",
    ]
    lines += [f"- {reason}" for reason in alarms] if alarms else ["None. Every switched-on source looks healthy."]
    lines += [
        "",
        "## Counts",
        "",
        "\"Seen\" is every notice the source listed inside the look-back window, so it stays level across weekends.",
        "",
        "| Source | State | Seen | New | Updated | Closed | Could not be read | Requests made |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, entry in run["sources"].items():
        lines.append(
            f"| {name} | {_status_words(entry)} | {entry.get('seen', 0)} | {entry.get('new', 0)} | {entry.get('updated', 0)} "
            f"| {entry.get('closed', 0)} | {entry.get('parse_errors', 0)} | {entry.get('requests', 0)} |"
        )
    names = [n for n, e in run["sources"].items() if e.get("completeness", {}).get("notices")]
    lines += ["", "## Field completeness", ""]
    if names:
        lines += [
            "Share of the notices seen this run that have a value.",
            "",
            "| Field | " + " | ".join(names) + " |",
            "|---|" + "---:|" * len(names),
        ]
        for field in REPORTED_FIELDS:
            cells = [f"{run['sources'][n]['completeness']['fields'][field]}%" for n in names]
            lines.append(f"| {field} | " + " | ".join(cells) + " |")
        cells = []
        for n in names:
            comp = run["sources"][n]["completeness"]
            share = comp.get("deadline_where_expected")
            cells.append("n/a" if share is None else f"{share}% of {comp.get('deadline_expected_on')}")
        lines.append("| deadline, on notices that ask for a reply | " + " | ".join(cells) + " |")
        cells = [str(run["sources"][n]["completeness"].get("multinational", 0)) for n in names]
        lines.append("| notices covering several countries (count) | " + " | ".join(cells) + " |")
        lines += [
            "",
            "Awards and general notices have no deadline, so the plain deadline row is low by nature; "
            "the row under it is the one to watch.",
        ]
    else:
        lines.append("No notices were collected, so there is nothing to measure.")
    lines += ["", "## Errors", ""]
    any_error = False
    for name, entry in run["sources"].items():
        if entry.get("fatal") and entry.get("enabled"):
            any_error = True
            lines.append(f"- {name}: {entry['fatal']}")
        errors = details.get(name, {}).get("parse_errors", [])
        for line in errors[:ERROR_LINES_SHOWN]:
            any_error = True
            lines.append(f"- {name}: could not read notice {line}")
        if len(errors) > ERROR_LINES_SHOWN:
            lines.append(f"- {name}: and {len(errors) - ERROR_LINES_SHOWN} more")
    if not any_error:
        lines.append("None.")
    lines += ["", "## What could not be extracted", ""]
    any_gap = False
    for name in names:
        gaps = details.get(name, {}).get("gaps", {})
        for field, ids in gaps.items():
            any_gap = True
            examples = ", ".join(ids[:3])
            lines.append(f"- {name}: `{field}` missing on {len(ids)} notices (for example {examples})")
    if not any_gap:
        lines.append("Nothing missing." if names else "Nothing collected.")
    switched_off = [n for n, e in run["sources"].items() if not e.get("enabled")]
    if switched_off:
        lines += ["", "## Switched off", ""]
        lines += [f"- {n}: not collected (see RECON.md)" for n in switched_off]
    return "\n".join(lines) + "\n"
