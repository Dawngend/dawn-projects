# Survival Rules

The event and censoring rules for Block 9, written before any lifetime model.
Built only from `job_intel/history_snapshot.md`, `job_intel/visibility_window.md`, `job_intel/observation_log.py` and `job_intel/capture_latest.py` (checked 2026-11-13). No source was fetched and no data was analysed for this file.

## The Event

The event is a posting disappearing from the captured observations for its source. The posting has an observation in one run and none in the next successful run. These observations come from the scraper's stored `postings` table (through `capture_latest.py`), not from a verified raw source response. So the event shows that the posting stopped appearing in the scraper's stored output. It does not prove the source removed the posting, and it is not proof the job closed. A posting can drop out of a feed without the job ending, and Jobicy's own pages say that dropping out of its 7-day feed alone does not mean closure (`visibility_window.md`).

A posting is identified by its `posting_key` within a source, which is the `url`, or a hash of the title, company, location and published date when the `url` is blank.

## Observation Times

Observation times come only from the observation log's runs, one run per source and `run_at`.

- Visible in a run means the run stored an observation for that posting.
- Only successful runs count. A failed, missing or empty run is not evidence that a posting disappeared.
- The publication date is not an observation time. It says when the source says the job was posted, so it cannot be used as the first time the posting was seen.

**`ok` runs and `legacy` runs.** A run with status `ok` comes from `capture_latest.py` reading the scraper's cumulative `postings` table, so it records the latest stored observations, not a verified raw response or raw returned count (`returned_count` stays `NULL`). A run with status `legacy` was rebuilt from `history.db` by the migration. A `legacy` row proves presence at its recorded time for the postings that were stored. It does not prove a complete source response, and it does not prove absence for a posting that was not stored (`history_snapshot.md` records one save with no table of runs). So a `legacy` run cannot set a `first_missed` bound by itself. It can serve as `last_seen`, and a later `ok` run can provide the comparison that closes the interval.

## Censoring Rules

**Right-censored.** The posting still has an observation in the last successful snapshot run for that source. All that is known is that it had not disappeared from the captured observations by that run. When it disappears, or whether it does, is unknown.

**Interval-censored.** The posting had an observation in a run, then none in the next successful run for that source. Its event interval is `(last_seen, first_missed]`, where `last_seen` is the run time it was last visible and `first_missed` is the run time of the next successful run that did not include it. The posting disappeared from the captured observations after `last_seen` and at or before `first_missed`. The interval bounds when it stopped appearing in the scraper's stored output. It does not show that the source removed it in that interval.

The interval is left-open because the posting had an observation at `last_seen`. It is right-closed because the posting had none at `first_missed`, so it could have disappeared at that moment.

**Skipped runs.** When runs for a source are missing, `first_missed` is the next successful run, not the next intended one. The interval then covers the skipped time and is wider, but it is still a valid bound.

## What These Rules Cannot Say

- **The first snapshot cannot establish a posting's start.** A posting already present in the first successful run for its source has an unknown left edge, so its age at that run is unknown. A posting that first appears in a later run is only known to have started between the previous successful run and that one. In both cases the start is a bound, not a date.
- **Failed, missing and empty runs are not disappearances.** Treating them as disappearances would invent events. They are gaps in observation.
- **One snapshot gives no lifetime estimates.** `history_snapshot.md` records one save time with `times_seen = 1` for all 330 rows. That file can say a posting was present at that one time, and nothing about how long it stayed. Lifetimes need at least two successful runs per source.
- **The bound is an interval, not a duration.** Reporting a single lifetime per posting would pick a point inside the interval without evidence for it.

**Local snapshot checked 2026-11-13:** a read-only count of `job_intel/data/observations.db` shows one `ok` run per source, five runs in total, all on 2026-11-04. With only one captured run per source, this log cannot yet support posting lifetime estimates or fitted survival curves.

## Related Limits

`visibility_window.md` already separates a documented refresh or delay rule from a posting lifetime. No source in that audit publishes a lifetime that these rules could use as a check, and the Jobicy 7-day window is documented for `/api/jobs` only, not the legacy endpoint this scraper calls. So the rules above stand on repeated observations alone.
