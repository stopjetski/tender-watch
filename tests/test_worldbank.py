"""World Bank parser, checked against replies saved from the real API.

If the Bank changes its API these fail, instead of bad data going in quietly.
"""
from datetime import date

import pytest

from tender_watch.http import PoliteSession
from tender_watch.schema import validate
from tender_watch.sources import worldbank as wb


def by_id(records):
    return {r["id"]: r for r in records}


def test_every_notice_on_the_saved_page_is_read(wb_page):
    records, errors = wb.parse_page(wb_page("page_recent"))
    assert errors == []
    assert len(records) == 40
    assert all(validate(r) == [] for r in records)
    assert len({r["id"] for r in records}) == 40


def test_a_contract_award_in_full(wb_page):
    record = by_id(wb.parse_page(wb_page("page_recent"))[0])["worldbank:OP00482295"]
    assert record == {
        "id": "worldbank:OP00482295",
        "source": "worldbank",
        "notice_type": "contract_award",
        "notice_type_original": "Contract Award",
        "title": "OVERHAUL AND LLP REPLACEMENT OF THE PW127 ENGINE, ESN EB0238 FOR MADAGASCAR AIRLINES",
        "description": "Réparation et révision générale du moteur ESN EB0238 - Avion 5R-MJF",
        "country_code": "MG",
        "country_name": "Madagascar",
        "country_original": "Madagascar",
        "sector": "Public Administration - Industry, Trade and Services; Tourism; Agricultural markets, "
        "commercialization and agri-business; Sub-National Government; Central Government (Central Agencies)",
        "project_name": "Economic Transformation for Inclusive Growth Project",
        "project_id": "P174684",
        "borrower_or_implementing_agency": "PIC MADAGASCAR AIRLINES",
        "language": "fr",
        "published_date": "2026-11-18",
        "deadline": None,
        "source_url": "https://projects.worldbank.org/en/projects-operations/procurement-detail/OP00482295",
        "document_urls": [],
        "content_hash": record["content_hash"],
        "missing_fields": ["deadline", "document_urls"],
        "extraction_notes": [],
    }
    assert len(record["content_hash"]) == 64


def test_deadline_keeps_the_local_time_and_claims_no_timezone(wb_page):
    record = by_id(wb.parse_page(wb_page("page_recent"))[0])["worldbank:OP00482349"]
    assert record["notice_type"] == "invitation_for_bids"
    assert record["deadline"] == "2026-11-26T12:00:00"
    assert "deadline" not in record["missing_fields"]
    assert any("no timezone" in note for note in record["extraction_notes"])


def test_a_midnight_deadline_is_flagged_as_possibly_empty(wb_page):
    record = by_id(wb.parse_page(wb_page("page_recent"))[0])["worldbank:OP00482420"]
    assert record["deadline"] == "2026-12-04T00:00:00"
    assert any("00:00" in note for note in record["extraction_notes"])


def test_a_region_becomes_multinational_and_keeps_the_original_label(wb_page):
    record = by_id(wb.parse_page(wb_page("page_recent"))[0])["worldbank:OP00482446"]
    assert record["country_code"] is None
    assert record["country_name"] == "multinational"
    assert record["country_original"] == "Western and Central Africa"
    assert "country_code" not in record["missing_fields"]


def test_the_old_world_bank_code_for_dr_congo_becomes_the_iso_code(wb_page):
    record = by_id(wb.parse_page(wb_page("page_recent"))[0])["worldbank:OP00482485"]
    assert record["country_code"] == "CD"
    assert record["country_original"] == "Congo, Democratic Republic of"
    assert record["notice_type"] == "expression_of_interest"
    assert record["language"] == "fr"


def test_spanish_is_other_and_the_note_names_it(wb_page):
    record = by_id(wb.parse_page(wb_page("page_recent"))[0])["worldbank:OP00482264"]
    assert record["language"] == "other"
    assert any("Spanish" in note for note in record["extraction_notes"])


def test_general_notices_list_what_the_source_does_not_give(wb_page):
    records, errors = wb.parse_page(wb_page("page_general_notices"))
    assert errors == [] and len(records) == 6
    first = records[0]
    assert first["notice_type"] == "general_procurement_notice"
    assert first["deadline"] is None and first["description"] is None
    assert {"description", "sector", "borrower_or_implementing_agency", "deadline"} <= set(first["missing_fields"])


def test_prequalification_is_other_with_its_own_label_kept(wb_page):
    records, errors = wb.parse_page(wb_page("page_prequalification"))
    assert errors == [] and len(records) == 6
    assert {r["notice_type"] for r in records} == {"other"}
    assert {r["notice_type_original"] for r in records} == {"Invitation for Prequalification"}
    assert records[0]["deadline"] == "2027-01-19T12:00:00"


def test_one_bad_notice_is_reported_and_the_rest_still_read(wb_page):
    page = wb_page("page_recent")
    page["procnotices"][3]["noticedate"] = "not a date"
    del page["procnotices"][5]["id"]
    records, errors = wb.parse_page(page)
    assert len(records) == 38
    assert len(errors) == 2


def test_a_changed_reply_shape_is_an_error_not_an_empty_result():
    with pytest.raises(ValueError):
        wb.parse_page({"rows": 0, "notices": []})


def test_no_personal_contact_fields_are_requested():
    assert "contact" not in wb.FIELDS


def test_notice_date_and_deadline_helpers():
    assert wb.parse_notice_date("18-Nov-2026") == "2026-11-18"
    assert wb.parse_notice_date(None) is None
    assert wb.parse_deadline("2026-12-02T00:00:00Z", "16:00")[0] == "2026-12-02T16:00:00"
    assert wb.parse_deadline("2026-12-02T00:00:00Z", None)[0] == "2026-12-02"
    assert wb.parse_deadline(None, "16:00") == (None, [])


def test_collect_reads_pages_until_it_passes_the_window(wb_page, fake_requests, fake_response, fake_clock):
    recent = wb_page("page_recent")  # all dated 2026-11-18
    old = wb_page("page_prequalification")  # dated 11 Nov and earlier
    pages = [recent, old]

    def answer(url, kwargs):
        if url.endswith("/robots.txt"):
            return fake_response(status_code=404)
        offset = kwargs["params"]["os"]
        return fake_response(payload=pages[offset // wb.PAGE_SIZE])

    http = fake_requests(answer)
    session = PoliteSession(session=http, sleep=fake_clock.sleep, clock=fake_clock.clock)
    result = wb.collect(session, date(2026, 11, 18), lookback_days=7)
    api_calls = [c for c in http.calls if "procnotices" in c[0]]
    assert len(api_calls) == 2  # stopped once a page reached past the window
    assert result.seen == 40 + 1  # only the 11 Nov prequalification notice is inside 7 days
    assert all(r["published_date"] >= "2026-11-11" for r in result.notices)
    assert result.parse_errors == []


def test_collect_does_not_count_a_notice_twice(wb_page, fake_requests, fake_response, fake_clock):
    recent = wb_page("page_recent")

    def answer(url, kwargs):
        if url.endswith("/robots.txt"):
            return fake_response(status_code=404)
        if kwargs["params"]["os"] >= 2 * wb.PAGE_SIZE:
            return fake_response(payload={"procnotices": []})
        return fake_response(payload=recent)

    session = PoliteSession(session=fake_requests(answer), sleep=fake_clock.sleep, clock=fake_clock.clock)
    result = wb.collect(session, date(2026, 11, 19))
    assert len(result.notices) == 40
