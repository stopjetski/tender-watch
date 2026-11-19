# Recon: how each source works, and the plan

Checked on 19 November 2026 from a cloud development machine, using a bot
that names itself (`tender-watch/0.1 (+https://github.com/stopjetski/tender-watch)`),
one request a second.

## Summary

| | World Bank | African Development Bank |
|---|---|---|
| Automated access allowed? | Yes: robots rules allow it and the Bank offers the API for this | **Not established.** The site refused the bot before any rule could be read |
| How notices are listed | One JSON API, newest first | Not seen |
| Details in PDFs? | No. Everything is in the API reply | Not seen |
| State | Collected end to end | Switched off, waiting for a decision |

## World Bank

### Rules

- `search.worldbank.org/robots.txt` does not exist (404), so nothing is
  disallowed there. `www.worldbank.org/robots.txt` and
  `projects.worldbank.org/robots.txt` both say `Allow` for every bot, with a
  few system paths excluded; none of them are paths we use.
- Terms of use (worldbank.org, "Terms & Conditions", read 19 Nov 2026). Three
  clauses matter:
  1. **Non-commercial only.** "you may make non-commercial uses thereof, but
     you may not make any derivative work or commercial use, including
     without limitation reselling them, charging to access them, charging to
     redistribute them, or charging for derivative works based on them,
     without the prior written consent of the relevant member institution(s)."
     The API section repeats it: "you may not in any event use the APIs to
     facilitate commercial uses of the Materials".
  2. **Attribution.** Use is conditioned on the line "The World Bank Group
     authorizes the use of this material subject to the terms and conditions
     on its website". It is in the README.
  3. **No personal information.** The prohibited uses include "Collect or
     store personal information about anyone". Notices carry a contact
     person's name, e-mail and phone. The collector does not ask the API for
     those fields and they are not in the data or the test files.
- Nothing forbids automated collection. This two-week experiment is
  non-commercial, so it fits. **A website that charges for access would not,
  without written consent from the Bank.** The terms also say some datasets
  carry their own, usually more open, licence; whether procurement notices
  are one of them could not be checked from here and is worth asking the
  Bank directly. This is a business decision for the owner, noted under
  "Open questions".

### How it works

- One endpoint: `https://search.worldbank.org/api/v2/procnotices?format=json`.
  No key, no sign-in.
- 427,594 notices in total on 19 Nov 2026. About 985 fall in any seven days:
  roughly 140 to 210 on a weekday, 45 to 65 on a weekend day.
- What was tested, with the result:

  | Parameter | Result |
  |---|---|
  | `rows` | Page size. 500 works |
  | `os` | Offset. `os=1000` works; `os=300000` is refused (HTTP 400), so the old archive cannot be paged through |
  | default order | Newest notice date first |
  | `strdate` / `enddate` and four similar spellings | **Ignored.** The total does not change. There is no date filter |
  | `notice_type_exact=...` | Works |
  | `fl=a,b,c` | Chooses the fields returned; `fl=*` returns all |

- So each run reads from the top, 500 at a time, until it passes the
  look-back window (seven days): three requests a day.
- There are no detail pages or PDFs to fetch. The public page for a notice,
  `https://projects.worldbank.org/en/projects-operations/procurement-detail/<id>`,
  answers 200 and draws itself from the same API in the reader's browser.

### Where each field comes from

| Our field | API field | Notes |
|---|---|---|
| id | `id` (e.g. `OP00482295`) | Stable; becomes `worldbank:OP00482295` |
| notice_type | `notice_type` | Seven labels exist; mapping is in DECISIONS.md |
| title | `noticetitle` | |
| description | `bid_description` | Missing on general notices |
| country | `project_ctry_code`, `project_ctry_name` | Mostly ISO codes. Exceptions: `ZR` (DR Congo), `GZ` (West Bank and Gaza), and region codes such as `3W` "Western and Central Africa" (15% of notices) |
| sector | `sector[].sector_description` | Missing on 23% |
| project_name, project_id | `project_name`, `project_id` | |
| borrower_or_implementing_agency | `agency_name` | Missing on general notices |
| language | `notice_lang_code` | EN 62%, FR 28%, ES 8%, PT 2% |
| published_date | `noticedate` (`18-Nov-2026`) | |
| deadline | `submission_deadline_date` + `submission_deadline_time` | Present on every invitation and expression of interest seen (285 of 285). Local time, no timezone stated |
| status | none usable (`notice_status` is always "Published") | Worked out from type and deadline |
| document_urls | none | The API lists no attachments |

Mix over seven days: 71% contract awards, 15% expressions of interest, 14%
invitations for bids, under 1% general notices.

## African Development Bank

### What happened

Every request to `www.afdb.org` from the development machine, **including
the request for `robots.txt`**, was answered with HTTP 403 and a Cloudflare
"Just a moment... Enable JavaScript and cookies to continue" page (the reply
carries the header `cf-mitigated: challenge`). That is the site asking for
proof of a human with a browser.

Nothing was done to get past it. Pretending to be a browser would mean
defeating a control the Bank chose to put there, and would contradict this
project's rule of an honest bot name.

### What that means

- The robots rules and terms of use could not be read.
- The inspection of 20 recent notices (which fields are on the listing, the
  detail page, or only in the PDF) **has not been done**. No AfDB parser
  exists, because writing one without real pages would be guesswork.
- A web search found no official feed or API for AfDB project procurement
  notices.
- One thing is **not known**: the challenge may depend on where the request
  comes from. GitHub's machines, where the daily job runs, might be let
  through, or might not. This has not been tried: a safety check stopped
  the first attempt to probe the site from GitHub, and it is right that
  the owner says yes first, since the site has already said no once.

### Options, in the order I would try them

1. **Ask the Bank.** An e-mail to AfDB's procurement or web team saying what
   the project is and asking either to let the named bot through or to point
   to a feed. This is the only route that ends in permission rather than
   tolerance.
2. **One honest check from GitHub.** Switch AfDB on (`sources.toml`); the
   collector asks for `robots.txt` once, obeys what it says, and stops if it
   is challenged. If the site answers normally, the 20-notice inspection and
   the parsers follow.
3. **Swap the hard case.** If AfDB stays closed, use another bank whose
   notices live in PDFs (from the candidate list) to answer the PDF question
   during the two weeks.

### What is ready for when it opens

- The access check (`tender_watch/sources/afdb.py`): one request, honest
  answer in the daily report.
- PDF text extraction with a download-once cache (`pdftext.py`), tested on a
  French sample. The sample is made up for the test; it is not a Bank
  document.
- A no-AI deadline finder for free text in English, French, Portuguese and
  Spanish (`textfields.py`).

### An early number on the "do we need an LLM" question

World Bank notices carry both the full text and a structured deadline, so
they can score the deadline finder that AfDB PDFs would depend on
(`tools/measure_deadline_finder.py`, 149 notices, 19 Nov 2026):

| | Notices | Share |
|---|---:|---:|
| Finder gave the same date as the Bank's own field | 103 | 69% |
| Finder found nothing | 19 | 13% |
| Finder gave a different date | 27 | 18% |

Read with care: in some of the "different" cases the notice text and the
Bank's own field really do disagree, so the finder is not always the one in
the wrong. Even so, a method that returns a wrong-looking date about one
time in six is not good enough to publish deadlines from. Expect AfDB
deadlines to need either an LLM step or a human check.

## Plan

1. World Bank: built and tested (done).
2. AfDB: wait for the decision above.
3. Daily job at 06:00 Singapore time, report in `reports/`, alarm rules as
   specified.
4. Notion mirror for review.

## Open questions for the owner

- May the collector make its one `robots.txt` request to AfDB from GitHub?
- Will the website charge money? If so, World Bank data needs the Bank's
  written consent, or confirmation that procurement notices fall under an
  open dataset licence.
