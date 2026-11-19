"""How well does the no-AI deadline finder do on real notice text?

World Bank notices carry both the full text and a structured deadline, so
they can score the finder that African Development Bank PDFs will depend
on. Reads the 500 newest notices (one request) and prints the tally.

    python tools/measure_deadline_finder.py
"""
import collections
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tender_watch.http import PoliteSession  # noqa: E402
from tender_watch.sources.worldbank import API_URL  # noqa: E402
from tender_watch.textfields import find_deadline  # noqa: E402


def plain(text: str) -> str:
    text = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>|</td>|</li>", "\n", text or "")
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"[ \t\xa0]+", " ", re.sub(r"\s*\n\s*", "\n", text)).strip()


def main() -> None:
    fields = "id,notice_lang_code,submission_deadline_date,notice_text"
    reply = PoliteSession().get(API_URL, params={"format": "json", "rows": 500, "fl": fields}).json()
    tally = collections.Counter()
    by_language = collections.defaultdict(collections.Counter)
    for notice in reply["procnotices"]:
        if not notice.get("submission_deadline_date"):
            continue
        truth = notice["submission_deadline_date"][:10]
        found, _ = find_deadline(plain(notice.get("notice_text", "")))
        outcome = "same date" if found == truth else ("nothing found" if found is None else "different date")
        tally[outcome] += 1
        by_language[notice.get("notice_lang_code")][outcome] += 1
    print("All:", dict(tally))
    for language, counts in sorted(by_language.items()):
        print(f"  {language}:", dict(counts))


if __name__ == "__main__":
    main()
