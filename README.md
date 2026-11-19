# tender-watch

A two-week experiment: collect procurement notices from development banks
every day, put them in one clean format, and measure how reliable that is.
It is the groundwork for a website that replaces UN Development Business.

## What it does

Once a day, at 06:00 Singapore time, a job on GitHub:

1. asks each bank for its recent procurement notices;
2. turns every notice into the same record (type, title, country, sector,
   project, deadline, status, link and so on);
3. adds new notices to `data/notices.jsonl`, and where a known notice has
   changed, updates it and keeps the old values in its `history`;
4. writes `reports/YYYY-MM-DD.md`: how many notices were new, updated and
   closed, any errors, and how complete each field is;
5. copies new and changed notices to a Notion database for review;
6. fails on purpose, so GitHub e-mails you, if a bank returned nothing,
   returned fewer than half its usual number, or more than one notice in ten
   could not be read.

It never invents a value. If a bank does not give a field, the field is
empty and its name is listed in the notice's `missing_fields`.

## Sources

| Bank | State |
|---|---|
| World Bank | Collected every day from the Bank's own API |
| African Development Bank | Switched off. Its website turns the bot away, from GitHub as well; see `RECON.md` |

## Where things are

| File | What it is |
|---|---|
| `data/notices.jsonl` | Every notice, one per line. The source of truth |
| `data/runs.json` | A log of every run, used for the alarm's seven-day average |
| `reports/` | One report per day |
| `RECON.md` | How each bank's site works and what its rules allow |
| `DECISIONS.md` | Choices made along the way, with reasons |
| `sources.toml` | Which banks are switched on |
| `tender_watch/` | The code |
| `tests/` | Tests, with saved replies from the banks in `tests/fixtures/` |

## Run it now

On GitHub: **Actions** tab → **daily collection** → **Run workflow** → green
**Run workflow** button. It takes about a minute. The new report appears in
`reports/`.

On a computer with Python 3.11 or newer:

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest
```

```bash
python -m tender_watch run
```

## Notion review database

The job copies notices to Notion when two GitHub secrets exist:
`NOTION_TOKEN` and `NOTION_DATABASE_ID`. Without them that step is skipped.

1. In Notion's **Developer tools**, open the **Developer connections** tab →
   **New connection**. Name it `tender-watch` and keep it to your own
   workspace (an internal connection, not a public one). Not a personal
   access token: that would let the job open everything you can open.
2. In the list, click **•••** beside `tender-watch` and copy its token.
3. Open the review database in Notion as a full page → **•••** (top right) →
   **Connections** → search `tender-watch` → **Confirm**.
4. Still on that page: **•••** → **Copy link**. The link looks like
   `https://www.notion.so/2f1c...9ab?v=...`. The 32 letters and digits before
   the `?` are the database ID.
5. On GitHub: this repo → **Settings** → **Secrets and variables** →
   **Actions** → **New repository secret**. Name `NOTION_TOKEN`, paste the
   token, **Add secret**. Repeat with name `NOTION_DATABASE_ID` and the ID.

The job adds any missing columns itself. **Checked** and **Problem** are
yours: the job never writes to them.

## How to add another bank

1. Recon first. Read the bank's robots.txt and terms, work out how it lists
   notices, and write it up in `RECON.md`.
2. Save a few real pages or replies in `tests/fixtures/<bank>/`. Remove
   contact names, e-mails and phone numbers.
3. Write `tender_watch/sources/<bank>.py` with one function,
   `collect(session, today, lookback_days)`, that returns a `SourceResult`.
   `worldbank.py` is the model: fetch with the shared `session` (it keeps to
   one request a second and obeys robots.txt), build each record, and pass it
   through `finalize()`.
4. Add the bank to `tender_watch/sources/__init__.py` and to `sources.toml`.
5. Write tests against the saved pages, so that a change on the bank's site
   shows up as a failing test rather than as quiet bad data.

Countries go through `countries.py`, dates through `dates.py`; add a spelling
there when a bank uses one that is not recognised.

## Attribution and limits

World Bank data: The World Bank Group authorizes the use of this material
subject to the terms and conditions on its website,
<https://www.worldbank.org/en/about/legal/terms-and-conditions>.

Those terms allow non-commercial use only; see `RECON.md` before building
anything that charges for this data.

The bot identifies itself as
`tender-watch/0.1 (+https://github.com/stopjetski/tender-watch)`. If you run
one of these sites and want it to stop or slow down, open an issue here.
