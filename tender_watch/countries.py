"""Country names and codes -> ISO 3166 alpha-2.

Banks use their own lists. The World Bank's codes are mostly ISO but keep a
few old ones (ZR for the DR Congo) and add codes for regions ("3W" Western
and Central Africa). A region or a multi-country label becomes
"multinational"; anything not recognised becomes None, never a guess.
"""
from __future__ import annotations

import re
import unicodedata

import pycountry

from .schema import MULTINATIONAL

# World Bank codes that are not the ISO code for the same place.
WORLD_BANK_CODE_FIXES = {
    "ZR": "CD",  # Congo, Democratic Republic of (old "Zaire" code)
    "GZ": "PS",  # West Bank and Gaza
    "TP": "TL",  # Timor-Leste
    "YF": "RS",  # Serbia
    "KV": "XK",  # Kosovo
    "RO": "RO",
}
# ISO has no code for Kosovo; XK is the code the EU, IMF and World Bank use.
EXTRA_CODES = {"XK": "Kosovo"}

# Names as banks write them (English, French, Portuguese) -> ISO code.
NAME_ALIASES = {
    "congo, democratic republic of": "CD",
    "democratic republic of congo": "CD",
    "democratic republic of the congo": "CD",
    "dr congo": "CD",
    "drc": "CD",
    "republique democratique du congo": "CD",
    "rd congo": "CD",
    "rdc": "CD",
    "congo, republic of": "CG",
    "republic of congo": "CG",
    "congo": "CG",
    "republique du congo": "CG",
    "cote d'ivoire": "CI",
    "ivory coast": "CI",
    "egypt, arab republic of": "EG",
    "egypte": "EG",
    "gambia, the": "GM",
    "the gambia": "GM",
    "gambie": "GM",
    "somalia, federal republic of": "SO",
    "somalie": "SO",
    "turkiye": "TR",
    "turkey": "TR",
    "kyrgyz republic": "KG",
    "lao people's democratic republic": "LA",
    "lao pdr": "LA",
    "west bank and gaza": "PS",
    "yemen, republic of": "YE",
    "iran, islamic republic of": "IR",
    "korea, republic of": "KR",
    "micronesia, federated states of": "FM",
    "venezuela, republica bolivariana de": "VE",
    "bahamas, the": "BS",
    "sao tome and principe": "ST",
    "sao tome et principe": "ST",
    "sao tome e principe": "ST",
    "cabo verde": "CV",
    "cape verde": "CV",
    "cap-vert": "CV",
    "eswatini": "SZ",
    "swaziland": "SZ",
    "tanzania": "TZ",
    "tanzanie": "TZ",
    "kosovo": "XK",
    "moldova": "MD",
    "russia": "RU",
    "syria": "SY",
    "vietnam": "VN",
    "bolivia": "BO",
    # French names of African Development Bank member countries
    "afrique du sud": "ZA",
    "algerie": "DZ",
    "benin": "BJ",
    "burkina faso": "BF",
    "cameroun": "CM",
    "centrafrique": "CF",
    "republique centrafricaine": "CF",
    "comores": "KM",
    "erythree": "ER",
    "ethiopie": "ET",
    "guinee": "GN",
    "guinee-bissau": "GW",
    "guinee equatoriale": "GQ",
    "libye": "LY",
    "maroc": "MA",
    "maurice": "MU",
    "mauritanie": "MR",
    "namibie": "NA",
    "ouganda": "UG",
    "senegal": "SN",
    "soudan": "SD",
    "soudan du sud": "SS",
    "tchad": "TD",
    "tunisie": "TN",
    "zambie": "ZM",
    # Portuguese
    "mocambique": "MZ",
    "guine-bissau": "GW",
}
MULTI_WORDS = ("multinational", "multi-country", "multicountry", "multinationale", "regional", "plusieurs pays")


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'").lower()
    return re.sub(r"\s+", " ", text).strip()


def iso_name(code: str) -> str | None:
    if code in EXTRA_CODES:
        return EXTRA_CODES[code]
    country = pycountry.countries.get(alpha_2=code)
    if country is None:
        return None
    return getattr(country, "common_name", None) or country.name


def is_iso_code(code: str) -> bool:
    return code in EXTRA_CODES or pycountry.countries.get(alpha_2=code) is not None


def from_world_bank(code: str | None, name: str | None) -> tuple[str | None, str | None, str | None]:
    """Return (iso_code, country_name, note) for a World Bank code and name."""
    code = (code or "").strip().upper() or None
    name = (name or "").strip() or None
    if code is None and name is None:
        return None, None, None
    # Region codes always carry a digit: 3W, 3E, 7C, E4, 6L ...
    if code and any(ch.isdigit() for ch in code):
        return None, MULTINATIONAL, None
    if code:
        fixed = WORLD_BANK_CODE_FIXES.get(code, code)
        if is_iso_code(fixed):
            return fixed, name or iso_name(fixed), None
    by_name = from_name(name) if name else (None, None, None)
    if by_name[0] or by_name[1] == MULTINATIONAL:
        return by_name
    return None, name, f"country code {code!r} is not an ISO code and the name was not recognised"


def from_name(name: str | None) -> tuple[str | None, str | None, str | None]:
    """Return (iso_code, country_name, note) for a country written as words."""
    name = (name or "").strip() or None
    if name is None:
        return None, None, None
    folded = _fold(name)
    if any(word in folded for word in MULTI_WORDS):
        return None, MULTINATIONAL, None
    if folded in NAME_ALIASES:
        return NAME_ALIASES[folded], name, None
    for getter in ("name", "common_name", "official_name"):
        try:
            country = pycountry.countries.get(**{getter: name})
        except (KeyError, LookupError):
            country = None
        if country is not None:
            return country.alpha_2, name, None
    for country in pycountry.countries:
        names = {country.name, getattr(country, "common_name", ""), getattr(country, "official_name", "")}
        if folded in {_fold(n) for n in names if n}:
            return country.alpha_2, name, None
    return None, name, f"country {name!r} was not recognised"
