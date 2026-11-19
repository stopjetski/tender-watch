"""Command line: `python -m tender_watch run` and `python -m tender_watch notion`."""
from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import report, store
from .http import Blocked, FetchFailed, PoliteSession
from .sources import SOURCES
from .sources.base import SourceResult

SINGAPORE = timezone(timedelta(hours=8))
CONFIG_FILE = Path("sources.toml")


def load_config(path: Path = CONFIG_FILE) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def run(now: datetime | None = None, session=None, config: dict | None = None, root: Path = Path(".")) -> int:
    now = now or datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today_utc = now.date()
    report_date = now.astimezone(SINGAPORE).date().isoformat()
    config = config if config is not None else load_config(root / CONFIG_FILE)
    session = session or PoliteSession()
    data_file = root / store.DATA_FILE
    runs_file = root / report.RUNS_FILE

    notices = store.load(data_file)
    runs = report.load_runs(runs_file)
    run_entry = {"date": report_date, "started_at": now_iso, "sources": {}}
    details: dict[str, dict] = {}
    alarms: list[str] = []

    for name, collect in SOURCES.items():
        settings = config.get(name, {})
        if not settings.get("enabled", False):
            run_entry["sources"][name] = {"enabled": False}
            continue
        before = dict(session.request_count)
        try:
            result = collect(session, today_utc, lookback_days=int(settings.get("lookback_days", 7)))
        except Blocked as error:
            result = SourceResult(source=name, fatal=f"blocked: {error}", blocked=True)
        except (FetchFailed, ValueError) as error:
            result = SourceResult(source=name, fatal=str(error))
        requests_made = sum(session.request_count.values()) - sum(before.values())
        outcome = store.merge(notices, result.notices, now_iso)
        gaps: dict[str, list[str]] = {}
        for record in result.notices:
            for field in record["missing_fields"]:
                gaps.setdefault(field, []).append(record["id"])
        details[name] = {"parse_errors": result.parse_errors, "gaps": gaps}
        run_entry["sources"][name] = {
            "enabled": True,
            "seen": result.seen,
            "new": len(outcome["new"]),
            "updated": len(outcome["updated"]),
            "closed": 0,
            "parse_errors": len(result.parse_errors),
            "fatal": result.fatal,
            "blocked": result.blocked,
            "requests": requests_made,
            "completeness": report.completeness(result.notices),
        }

    closed = store.refresh_statuses(notices, today_utc)
    for name, ids in closed.items():
        if name in run_entry["sources"] and run_entry["sources"][name].get("enabled"):
            run_entry["sources"][name]["closed"] = len(ids)

    for name, entry in run_entry["sources"].items():
        alarms += report.alarms_for(name, entry, report.seven_day_average(runs, name, report_date))
    run_entry["alarms"] = alarms

    store.save(notices, data_file)
    runs.append(run_entry)
    report.save_runs(runs, runs_file)
    reports_dir = root / report.REPORTS_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)
    text = report.render(run_entry, alarms, len(notices), details)
    (reports_dir / f"{report_date}.md").write_text(text, encoding="utf-8")
    print(text)
    return 1 if alarms else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tender_watch", description="Collect development-bank procurement notices.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="collect every switched-on source, update the data and write today's report")
    sub.add_parser("notion", help="copy new and changed notices to the Notion review database")
    sub.add_parser("check-afdb", help="ask afdb.org for its robots.txt once and report whether the bot is let in")
    args = parser.parse_args(argv)
    if args.command == "run":
        return run()
    if args.command == "check-afdb":
        from .sources import afdb

        result = afdb.access_check(PoliteSession())
        print("LET IN" if result["let_in"] else "NOT LET IN", "-", result["reason"])
        if result["robots_txt"] is not None:
            print("----- robots.txt -----")
            print(result["robots_txt"][:20000])
        return 0
    from . import notion_sync

    return notion_sync.main()


if __name__ == "__main__":
    sys.exit(main())
