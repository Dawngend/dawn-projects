# Visibility Window

Built only from facts already recorded in `job_intel/source_terms.md` and `job_intel/history_snapshot.md` (both checked 2026-11-13). No source was fetched for this file and no new research was added. It records what each source publishes and what one saved snapshot can show, and does not claim that this project complies with any source's terms.

## Two Different Things

- A documented API or feed timing rule is a published statement about refresh, delay, polling or window length. It says when data arrives or how often it may be requested.
- A posting lifetime is how long an individual posting stays in the source's response. It is not the same as a refresh, delay or polling rule, and it is not measured by one.
- Observed visibility is how long a posting was actually present in the responses this project saw. It needs repeated runs.

| Source | Exact duration the existing audit supports | What that duration describes |
|---|---|---|
| Himalayas | 24 hours | Feed cache refresh, not a posting lifetime |
| Remote OK | None published | FAQ states no polling, caching or retention rule |
| Remotive | 24 hours | Publication delay into the API, not a lifetime |
| We Work Remotely | None published | RSS page states no polling, retention or removal rule |
| Jobicy | 7 days (and 3 hours) | Rolling feed window and publication delay for `/api/jobs` only |

## Himalayas

- **Documented API/feed timing rule:** The API reference says `/jobs/api` refreshes its cached feed every 24 hours, so polling more than once per day adds no new data ([API reference](https://himalayas.app/docs/remote-jobs-api)). Clause 113(d) requires caching where possible, and the API reference instructs callers to re-read the feed daily to drop closed or expired listings. These are refresh and polling statements, not lifetime statements.
- **Documented posting lifetime:** No exact duration. Each job object carries `expiryDate` (Unix timestamp in seconds), which is a per-job value rather than a fixed window, and the API reference notes that jobs can close before `expiryDate` ([API reference](https://himalayas.app/docs/remote-jobs-api)).
- **Observed visibility:** Not measurable here. The history holds 20 Himalayas rows, all stored at one save time (`history_snapshot.md`).

## Remote OK

- **Documented API/feed timing rule:** None to record. The FAQ feed answer specifies no numeric request-rate limit, polling interval, caching rule, or retention/removal rule for the JSON and RSS feeds ([FAQ](https://remoteok.com/faq#is-there-an-api-or-rssjson-feed-of-remote-jobs)).
- **Documented posting lifetime:** Not stated on the checked pages.
- **Observed visibility:** Not measurable here. 99 rows, all stored at one save. The oldest stored `published_date` (2026-08-05T01:57:42+00:00) is the oldest row in that save, not a window.

## Remotive

- **Documented API/feed timing rule:** The [Public API page](https://remotive.com/remote-jobs/api) and [API documentation](https://github.com/remotive-com/remote-jobs-api) state that jobs in the public API are delayed by 24 hours. That is a publication delay, not how long a job stays listed. The documentation also advises polling at most 4 times per day and blocks requests above 2 per minute, which are rate rules, not visibility rules.
- **Documented posting lifetime:** No exact duration. The documentation notes the endpoint returns active listings only, but neither official page states a retention limit, caching TTL, or deadline for deleting closed jobs.
- **Observed visibility:** Not measurable here. 11 rows, all stored at one save, and their stored dates have no offset, so they were read as UTC (an assumption flagged in `history_snapshot.md`).

## We Work Remotely (WWR)

- **Documented API/feed timing rule:** None to record. The [Public RSS Feed page](https://weworkremotely.com/remote-job-rss-feed) states no numeric request-rate limit, polling interval, caching rule, storage/retention limit, or expired-job removal rule.
- **Documented posting lifetime:** Not stated on the checked pages.
- **Observed visibility:** Not measurable here. 100 rows, all stored at one save. The oldest stored date (2023-06-21T14:22:59+00:00) is older than the other sources, but `history_snapshot.md` states that the oldest dates come from one save and show the oldest posting stored at that time, not a visibility window.

## Jobicy

- **Documented API/feed timing rule (for `/api/jobs`):** The [API/RSS page](https://jobicy.com/jobs-rss-feed) and [OpenAPI specification](https://jobicy.com/api/openapi.json) document a rolling 7-day publication window, a 3-hour upper publication delay, sync and RSS passes that start no more than once per hour, and public responses that may be cached up to 3,600 seconds.
- **Documented posting lifetime:** The 7-day rolling window is the only exact duration in this audit that describes how long a posting stays in a response, and it is documented for `/api/jobs` only. The same pages say that dropping out of the 7-day feed alone does not mean closure and that closed positions must be confirmed through `GET /api/jobs/status`, so the window describes feed presence rather than proof that a posting has ended.
- **Legacy-endpoint gap:** `job_market_scraper/sources.py` requests `https://jobicy.com/api/v2/remote-jobs`. No checked official page mentions that path, states whether it remains supported, or specifies rate limits, window behavior, deprecation status, or reuse and attribution terms for it (`source_terms.md`). The 7-day window and the 3-hour delay therefore cannot be applied to the endpoint this scraper uses, and the permissions published for `/api/jobs` cannot be transferred to it either.
- **Observed visibility:** Not measurable here. 100 rows, all stored at one save (oldest stored `published_date` 2026-11-03T17:31:17+00:00).

## Why One Snapshot Cannot Show Observed Visibility

- Every one of the 330 rows has the same `first_seen` and `last_seen` value (`2026-11-04T08:55:14.891833+00:00`) and `times_seen = 1`, so the file holds rows from a single save (`history_snapshot.md`).
- The file has no table of runs. A run that stored no rows leaves no trace, and the stored row counts are not the counts each source returned.
- Whether a posting appeared in an earlier or a later response is unknown, so its first appearance, last appearance and time in the feed cannot be computed from this file.
- The oldest `published_date` per source is the oldest row stored at that one save, not the oldest posting the source still serves.
- Any date-based window reasoning would additionally rest on two assumptions the database cannot confirm: remotive dates without an offset were read as UTC, and himalayas plain-digit dates were read as Unix epoch seconds.