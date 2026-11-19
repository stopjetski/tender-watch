import pytest

from tender_watch import countries
from tender_watch.dates import find_dates, parse_date


@pytest.mark.parametrize(
    "code,name,expected",
    [
        ("KE", "Kenya", ("KE", "Kenya")),
        ("ZR", "Congo, Democratic Republic of", ("CD", "Congo, Democratic Republic of")),
        ("GZ", "West Bank and Gaza", ("PS", "West Bank and Gaza")),
        ("XK", "Kosovo", ("XK", "Kosovo")),
        ("3W", "Western and Central Africa", (None, "multinational")),
        ("E4", "DRC - Angola", (None, "multinational")),
        (None, None, (None, None)),
    ],
)
def test_world_bank_codes(code, name, expected):
    assert countries.from_world_bank(code, name)[:2] == expected


def test_an_unknown_code_is_left_empty_with_a_note():
    code, name, note = countries.from_world_bank("QQ", "Atlantis")
    assert code is None and name == "Atlantis" and "not" in note


@pytest.mark.parametrize(
    "name,code",
    [
        ("Kenya", "KE"),
        ("Côte d'Ivoire", "CI"),
        ("Cote d’Ivoire", "CI"),
        ("République Démocratique du Congo", "CD"),
        ("Sénégal", "SN"),
        ("Maroc", "MA"),
        ("Moçambique", "MZ"),
        ("Tanzania", "TZ"),
    ],
)
def test_country_names_in_three_languages(name, code):
    assert countries.from_name(name)[0] == code


def test_multinational_and_unknown_names():
    assert countries.from_name("Multinational")[:2] == (None, "multinational")
    assert countries.from_name("Multinationale")[:2] == (None, "multinational")
    code, name, note = countries.from_name("Somewhere Else")
    assert code is None and name == "Somewhere Else" and note


@pytest.mark.parametrize(
    "text,iso",
    [
        ("18-Nov-2026", "2026-11-18"),
        ("15 décembre 2026", "2026-12-15"),
        ("1er novembre 2026", "2026-11-01"),
        ("le 2 août 2026 à 10h00", "2026-08-02"),
        ("December 3, 2026", "2026-12-03"),
        ("Thursday, 29th October, 2026", "2026-10-29"),
        ("15 de dezembro de 2026", "2026-12-15"),
        ("2026/11/12", "2026-11-12"),
        ("03/04/2026", "2026-04-03"),
        ("2026-12-02T00:00:00Z", "2026-12-02"),
    ],
)
def test_dates_in_the_forms_banks_use(text, iso):
    assert parse_date(text) == iso


def test_things_that_are_not_dates():
    assert parse_date("31 février 2026") is None
    assert parse_date("Loan 2100150042") is None
    assert parse_date(None) is None
    assert find_dates("from 1 March 2026 to 5 mars 2027") == [(5, "2026-03-01"), (21, "2027-03-05")]
