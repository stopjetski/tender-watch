from datetime import date

from tender_watch import report, store
from tender_watch.schema import finalize, status_for


def notice(number="1", **changes):
    record = {
        "id": f"worldbank:OP{number}",
        "source": "worldbank",
        "notice_type": "invitation_for_bids",
        "notice_type_original": "Invitation for Bids",
        "title": "Supply of pumps",
        "description": "Pumps",
        "country_code": "KE",
        "country_name": "Kenya",
        "country_original": "Kenya",
        "sector": "Water",
        "project_name": "Water project",
        "project_id": "P1",
        "borrower_or_implementing_agency": "Ministry of Water",
        "language": "en",
        "published_date": "2026-11-10",
        "deadline": "2026-11-20T10:00:00",
        "source_url": "https://example.org/1",
        "document_urls": [],
    }
    record.update(changes)
    return finalize(record)


def test_a_new_notice_then_the_same_notice_again():
    notices = {}
    first = store.merge(notices, [notice()], "2026-11-19T22:00:00Z")
    again = store.merge(notices, [notice()], "2026-11-20T22:00:00Z")
    assert first["new"] == ["worldbank:OP1"] and again["unchanged"] == ["worldbank:OP1"]
    saved = notices["worldbank:OP1"]
    assert saved["first_seen_at"] == "2026-11-19T22:00:00Z"
    assert saved["last_seen_at"] == "2026-11-20T22:00:00Z"
    assert saved["history"] == []


def test_an_extended_deadline_is_an_update_and_the_old_value_is_kept():
    notices = {}
    store.merge(notices, [notice()], "2026-11-19T22:00:00Z")
    outcome = store.merge(notices, [notice(deadline="2026-12-05T10:00:00")], "2026-11-20T22:00:00Z")
    saved = notices["worldbank:OP1"]
    assert outcome["updated"] == ["worldbank:OP1"]
    assert saved["deadline"] == "2026-12-05T10:00:00"
    assert saved["history"] == [{"changed_at": "2026-11-20T22:00:00Z", "previous": {"deadline": "2026-11-20T10:00:00"}}]
    assert saved["first_seen_at"] == "2026-11-19T22:00:00Z"


def test_missing_fields_are_listed_never_filled_in():
    record = notice(deadline=None, sector=None)
    assert record["missing_fields"] == ["sector", "deadline", "document_urls"]
    assert record["deadline"] is None and record["sector"] is None


def test_status_rules():
    today = date(2026, 11, 20)
    assert status_for(notice(), today) == "open"  # due today is still open
    assert status_for(notice(deadline="2026-11-19"), today) == "closed"
    assert status_for(notice(notice_type="contract_award", deadline=None), today) == "awarded"
    assert status_for(notice(deadline=None), today) == "unknown"


def test_a_passed_deadline_counts_as_closed_once():
    notices = {}
    store.merge(notices, [notice()], "2026-11-19T22:00:00Z")
    assert store.refresh_statuses(notices, date(2026, 11, 20)) == {}
    assert store.refresh_statuses(notices, date(2026, 11, 21)) == {"worldbank": ["worldbank:OP1"]}
    assert store.refresh_statuses(notices, date(2026, 11, 22)) == {}


def test_the_file_round_trips_sorted_one_notice_per_line(tmp_path):
    notices = {}
    store.merge(notices, [notice("2", title="Écoles à Thiès"), notice("1")], "2026-11-19T22:00:00Z")
    path = tmp_path / "data" / "notices.jsonl"
    store.save(notices, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[0].startswith('{"id": "worldbank:OP1"')
    assert "Écoles à Thiès" in lines[1]
    assert store.load(path) == notices


def test_completeness_counts_deadline_only_where_one_is_expected():
    records = [notice("1"), notice("2", deadline=None), notice("3", notice_type="contract_award", deadline=None)]
    result = report.completeness(records)
    assert result["fields"]["deadline"] == 33
    assert result["deadline_where_expected"] == 50 and result["deadline_expected_on"] == 2
    assert result["fields"]["title"] == 100 and result["fields"]["document_urls"] == 0


def entry(**values):
    base = {"enabled": True, "seen": 1000, "parse_errors": 0, "fatal": None}
    base.update(values)
    return base


def test_alarm_on_zero_notices():
    assert "returned 0 notices" in report.alarms_for("worldbank", entry(seen=0), 1000)[0]


def test_alarm_when_fewer_than_half_the_seven_day_average():
    assert report.alarms_for("worldbank", entry(seen=499), 1000)
    assert report.alarms_for("worldbank", entry(seen=500), 1000) == []
    assert report.alarms_for("worldbank", entry(seen=10), None) == []  # first ever run: nothing to compare with


def test_alarm_when_more_than_a_tenth_cannot_be_read():
    assert report.alarms_for("worldbank", entry(seen=100, parse_errors=11), 100)
    assert report.alarms_for("worldbank", entry(seen=100, parse_errors=10), 100) == []


def test_alarm_when_a_switched_on_source_fails_but_not_when_it_is_off():
    assert report.alarms_for("afdb", entry(seen=0, fatal="blocked: challenge"), None)
    assert report.alarms_for("afdb", {"enabled": False}, None) == []


def test_seven_day_average_uses_earlier_good_days_only():
    runs = [
        {"date": f"2026-11-{day:02d}", "sources": {"worldbank": entry(seen=seen)}}
        for day, seen in [(10, 100), (11, 900), (12, 1000), (13, 1100), (14, 1000), (15, 1000), (16, 1000), (17, 1000)]
    ]
    runs.append({"date": "2026-11-17", "sources": {"worldbank": entry(seen=0, fatal="down")}})
    runs.append({"date": "2026-11-18", "sources": {"worldbank": entry(seen=5)}})
    assert report.seven_day_average(runs, "worldbank", "2026-11-18") == 1000
    assert report.seven_day_average([], "worldbank", "2026-11-18") is None
