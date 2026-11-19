# Decisions

Choices made while building, with the reason. Newest at the bottom.

## 19 November 2026

**Data lives in `data/notices.jsonl`: one notice per line, sorted by id.**
Not SQLite, because a database file shows up in GitHub as an unreadable
blob; with one line per notice, each day's change can be read line by line
and any past day can be recovered. Not one big JSON array, because a single
changed notice would then rewrite the whole file. Any website can read it
directly. Revisit if the file passes about 50 MB.

**The record has three fields beyond the brief:** `notice_type_original`
(the brief asked for the original label), `country_original` (the source's
own wording, kept because regions are turned into "multinational"), and
`history`. Country is two flat fields, `country_code` and `country_name`.

**"Multinational".** A notice for a region or several countries gets
`country_name: "multinational"` and no code. That empty code is not counted
as missing.

**Nothing is guessed.** A country code that is not a real ISO code and whose
name is not recognised stays empty, with a note. Kosovo uses `XK`: ISO has
no code for it, and XK is what the World Bank, IMF and EU use.

**World Bank notice types.**

| World Bank label | Ours |
|---|---|
| General Procurement Notice | general_procurement_notice |
| Invitation for Bids | invitation_for_bids |
| Request for Expression of Interest | expression_of_interest |
| Contract Award, Goods and Works Award, Small Contracts Award | contract_award |
| Invitation for Prequalification | other |

The World Bank has no "Request for Proposals" label; such tenders are
published as invitations or expressions of interest. The type follows the
Bank's label, not our reading of the text.

**Deadlines carry no timezone.** The World Bank gives a date and a local
hour and never says which timezone. The record holds `2026-12-02T16:00:00`
with a note; adding a timezone would be inventing one. The `Z` in the API's
date is how it writes every date, not a statement about UTC.

**Status is worked out, not copied.** The World Bank's own status field
always says "Published". So: an award is `awarded`; a notice with a deadline
is `open` through the deadline day and `closed` from the next day (by the
UTC calendar); anything else is `unknown`. A status change alone does not
count as "updated", because the notice itself did not change.

**"Closed" in the daily report** means notices that went from open to
closed since the last run, not every closed notice on file.

**An empty list of documents counts as missing.** The World Bank API lists
no attachments, so `document_urls` is 0% complete there, by design.

**Each run re-reads the last seven days**, not just today. The World Bank
API has no date filter and reads newest first, so this costs three requests,
and it catches notices published late or corrected. Limit: a notice changed
more than seven days after it was published is not re-read. Revisit after
the experiment (re-checking every open notice is the fix).

**The breakage alarm counts notices seen in the seven-day window**, not
notices new today. New-today drops to a third every weekend and would trip
the "fewer than half the average" rule every Saturday. The window count
stays level, so a real drop stands out. The average is taken over the last
seven earlier days that had a good run; on the very first run there is
nothing to compare with and that rule is skipped.

**Reports are dated by the Singapore calendar**, since the run is at 06:00
there. A second run on the same day replaces that day's report; every run is
still logged in `data/runs.json`.

**The run saves its data before it fails.** When the alarm trips, the
report and the data are committed first and the job fails afterwards, so
the evidence is in the repo when the e-mail from GitHub arrives.

**Personal details are not collected.** World Bank notices include a contact
person's name, e-mail and phone number. The collector does not request those
fields. Reason: the Bank's terms forbid collecting personal information, and
this repo is public.

**The full text of a notice is not stored**, only its title, short
description and facts, with a link back. Reason: the Bank's terms restrict
derivative works and redistribution; the link gives the reader the full
notice at the source.

**A bot challenge is a stop sign.** If a site answers with a "prove you are
a browser" page, or will not show its robots.txt, the collector reports the
source as blocked and makes no further request. It is never retried and
never worked around.

**AfDB is switched off** in `sources.toml` until the owner decides how to
approach the Bank. See RECON.md.

**PDF library: pypdf.** Pure Python, nothing extra to install on GitHub's
machines, reads accented French text correctly in the test. PDFs are cached
under `cache/pdf/` (kept between daily runs by GitHub's cache, not committed).
A scanned PDF yields almost no text; that is detected and noted.

**Notion is a copy, not the master.** Only new and changed notices are sent
(about 200 a day). "Checked" and "Problem" are never written by the code.
The deadline column holds the date only, with the local hour in its own
column, because Notion would otherwise assume a timezone. Which row belongs
to which notice is remembered in `data/notion_pages.json`.

**Python 3.13**, with three libraries: requests, pypdf, pycountry.
