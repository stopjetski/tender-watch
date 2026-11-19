"""The whole daily run, against saved replies, in a temporary folder."""
import json
from datetime import datetime, timezone

from tender_watch import cli
from tender_watch.http import PoliteSession

CONFIG = {"worldbank": {"enabled": True, "lookback_days": 7}, "afdb": {"enabled": False}}
NOW = datetime(2026, 11, 19, 22, 0, tzinfo=timezone.utc)


def session_answering(fake_requests, fake_response, fake_clock, pages):
    def answer(url, kwargs):
        if url.endswith("/robots.txt"):
            return fake_response(status_code=404)
        index = kwargs["params"]["os"] // 500
        return fake_response(payload=pages[index] if index < len(pages) else {"procnotices": []})

    return PoliteSession(session=fake_requests(answer), sleep=fake_clock.sleep, clock=fake_clock.clock)


def test_a_run_writes_data_a_report_and_a_run_log(tmp_path, wb_page, fake_requests, fake_response, fake_clock):
    session = session_answering(fake_requests, fake_response, fake_clock, [wb_page("page_recent")])
    code = cli.run(now=NOW, session=session, config=CONFIG, root=tmp_path)
    assert code == 0
    lines = (tmp_path / "data" / "notices.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 40
    first = json.loads(lines[0])
    assert first["first_seen_at"] == "2026-11-19T22:00:00Z" and first["status"] in ("open", "closed", "awarded", "unknown")
    report_text = (tmp_path / "reports" / "2026-11-20.md").read_text(encoding="utf-8")  # 06:00 in Singapore
    assert "| worldbank | collected | 40 | 40 | 0 |" in report_text
    assert "| afdb | switched off |" in report_text
    runs = json.loads((tmp_path / "data" / "runs.json").read_text(encoding="utf-8"))
    assert runs[0]["sources"]["worldbank"]["seen"] == 40 and runs[0]["alarms"] == []


def test_a_second_run_reports_updates_and_nothing_new(tmp_path, wb_page, fake_requests, fake_response, fake_clock):
    page = wb_page("page_recent")
    cli.run(now=NOW, session=session_answering(fake_requests, fake_response, fake_clock, [page]), config=CONFIG, root=tmp_path)
    for raw in page["procnotices"]:
        if raw["id"] == "OP00482349":
            raw["submission_deadline_date"] = "2026-12-10T00:00:00Z"
    later = datetime(2026, 11, 20, 22, 0, tzinfo=timezone.utc)
    cli.run(now=later, session=session_answering(fake_requests, fake_response, fake_clock, [page]), config=CONFIG, root=tmp_path)
    runs = json.loads((tmp_path / "data" / "runs.json").read_text(encoding="utf-8"))
    assert (runs[1]["sources"]["worldbank"]["new"], runs[1]["sources"]["worldbank"]["updated"]) == (0, 1)
    saved = {json.loads(line)["id"]: json.loads(line) for line in (tmp_path / "data" / "notices.jsonl").read_text(encoding="utf-8").splitlines()}
    changed = saved["worldbank:OP00482349"]
    assert changed["deadline"] == "2026-12-10T12:00:00"
    assert changed["history"][0]["previous"] == {"deadline": "2026-11-26T12:00:00"}


def test_an_empty_source_fails_the_run_but_still_writes_the_report(tmp_path, fake_requests, fake_response, fake_clock):
    session = session_answering(fake_requests, fake_response, fake_clock, [])
    assert cli.run(now=NOW, session=session, config=CONFIG, root=tmp_path) == 1
    assert "worldbank: returned 0 notices" in (tmp_path / "reports" / "2026-11-20.md").read_text(encoding="utf-8")


def test_a_changed_api_shape_fails_the_run(tmp_path, fake_requests, fake_response, fake_clock):
    session = session_answering(fake_requests, fake_response, fake_clock, [{"something": "else"}])
    assert cli.run(now=NOW, session=session, config=CONFIG, root=tmp_path) == 1
    assert "the source failed" in (tmp_path / "reports" / "2026-11-20.md").read_text(encoding="utf-8")


def test_a_blocked_bank_is_reported_as_blocked(tmp_path, fake_requests, fake_response, fake_clock):
    challenge = lambda url, kw: fake_response(status_code=403, text="Just a moment...", headers={"cf-mitigated": "challenge"})  # noqa: E731
    session = PoliteSession(session=fake_requests(challenge), sleep=fake_clock.sleep, clock=fake_clock.clock)
    config = {"worldbank": {"enabled": False}, "afdb": {"enabled": True}}
    assert cli.run(now=NOW, session=session, config=config, root=tmp_path) == 1
    text = (tmp_path / "reports" / "2026-11-20.md").read_text(encoding="utf-8")
    assert "| afdb | blocked by the site |" in text
    assert len(session.session.calls) == 1  # asked for robots.txt once and stopped


def test_the_afdb_access_check_makes_one_request_and_reports_a_challenge(fake_requests, fake_response, fake_clock):
    from tender_watch.sources import afdb

    challenge = lambda url, kw: fake_response(status_code=403, text="Just a moment...", headers={"cf-mitigated": "challenge"})  # noqa: E731
    session = PoliteSession(session=fake_requests(challenge), sleep=fake_clock.sleep, clock=fake_clock.clock)
    result = afdb.access_check(session)
    assert result["let_in"] is False and "challenge" in result["reason"]
    assert [url for url, _ in session.session.calls] == ["https://www.afdb.org/robots.txt"]


def test_the_afdb_access_check_obeys_robots_rules(fake_requests, fake_response, fake_clock):
    from tender_watch.sources import afdb

    for rules, expected in (("User-agent: *\nDisallow: /en/projects-and-operations/\n", False), ("User-agent: *\nDisallow: /admin/\n", True)):
        session = PoliteSession(session=fake_requests(lambda url, kw: fake_response(text=rules)), sleep=fake_clock.sleep, clock=fake_clock.clock)
        result = afdb.access_check(session)
        assert result["let_in"] is expected and result["robots_txt"] == rules
