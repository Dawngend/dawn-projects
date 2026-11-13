# History Snapshot

Read-only look at `job_market_scraper/output/history.db`, checked on 2026-11-13.
Only the database file was read. No source was fetched and nothing was written to the scraper folder.

## What Is Stored

The file has one table, `postings`, with 330 rows.
Its primary key is `(source, url)`, so there is one row per posting per source.

The columns are `title`, `company`, `url`, `source`, `location`, `published_date`, `tags`, `salary`, `description`, `first_seen`, `last_seen`, `times_seen` and `eligible`.

Every one of the 330 rows has the same `first_seen` and `last_seen` value (`2026-11-04T08:55:14.891833+00:00`) and `times_seen = 1`.

## Rows and Oldest Published Date by Source

`published_date` is stored as text in four different formats. Each value was converted to UTC before taking the oldest one. All 330 values could be parsed.

| Source | Stored rows | Parseable dates | Stored format | Oldest published date (UTC) |
|---|---|---|---|---|
| himalayas | 20 | 20 | Unix epoch seconds | 2026-11-04T06:12:58+00:00 |
| jobicy | 100 | 100 | ISO 8601 with offset | 2026-11-03T17:31:17+00:00 |
| remoteok | 99 | 99 | ISO 8601 with offset | 2026-08-05T01:57:42+00:00 |
| remotive | 11 | 11 | ISO 8601 without offset | 2026-10-04T16:53:34+00:00 |
| weworkremotely | 100 | 100 | RFC 2822 | 2023-06-21T14:22:59+00:00 |

Two of these conversions rest on an assumption that the database cannot confirm:

- The remotive values have no timezone offset. They were read as UTC.
- The himalayas values are plain digits. They were read as Unix epoch seconds.

## What the Schema Can Prove About Run Counts

This part reads `first_seen`, `last_seen` and `times_seen` by their column names. How the scraper fills them was not checked in this slice.

- The file holds rows from one save time only (2026-11-04T08:55:14.891833+00:00), because no row has a different `first_seen` or `last_seen` and no row has `times_seen` above 1.
- For that one save, the stored rows per source are the counts in the table above.
- All five sources have at least one row from that save.

## What the Schema Cannot Prove

- How many runs have happened. There is no table of runs, so a run that stored no rows leaves no trace, and an earlier file that was deleted or replaced would not show here.
- How many items each source returned in its response. The counts above are stored rows, one per `(source, url)`. Items that were skipped or merged before saving are not counted anywhere.
- Whether a source failed or returned nothing in a given run. Neither case is recorded.
- Per-run counts once more runs are saved. Each posting keeps only its first time, its last time and a total. Counting rows by `first_seen` gives the postings that were new at each save, and counting by `last_seen` gives the postings last stored at each save, but the postings present in a run between those two times cannot be listed.
- Which runs a posting was missing from. `times_seen` is a total with no dates attached.
- Whether a posting's `published_date` ever changed. Only one value is kept per row.
- How long a posting stays in a source's response. The oldest dates above come from one save, so they show the oldest posting stored that time and not a visibility window.
