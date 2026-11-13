# Job Intel

Block 8 of Remote Job Intelligence: the observation log and the data contracts.
The code works on SQLite files and does not import the `job_market_scraper` code.
It uses the Python standard library only. The tests need pytest.

## Contract Normalizers

`contracts.py` has six small functions. Five return `""` when the input is rejected, and `normalize_salary_range` returns `None`.

- `normalize_title` keeps a non-blank string and strips the outer whitespace.
- `normalize_published_date` returns a UTC ISO-8601 timestamp for ISO dates, RFC 2822 RSS dates, and 9- or 10-digit Unix epoch seconds. A value with no timezone is read as UTC.
- `normalize_salary` keeps the salary as trimmed text. It does not parse a range.
- `normalize_salary_range` validates structured `minimum` and `maximum` bounds (non-negative finite numbers or `None`, with `minimum <= maximum` and booleans rejected) and returns a two-item tuple of floats or `None`. It checks structured bounds only and does not parse raw salary text.
- `normalize_currency` accepts any three ASCII letters and returns them in uppercase. It does not check that the code is a real currency.
- `normalize_salary_period` maps a short list of labels to `hour`, `day`, `week`, `month` or `year`.

The accepted and rejected cases are listed in `contracts.md`.

## Observation Log

`observation_log.py` stores every run instead of overwriting the last one.

- `create_schema` creates three tables and is safe to call twice.
- `source_runs` has one row per source and run time.
- `description_versions` stores each description once, keyed by the SHA-256 hash of its text.
- `observations` has one row per run, source and posting. Triggers reject updates and deletes, so rows can only be added.
- `record_source_run`, `store_description` and `record_observation` each insert one row and leave the checks to the schema.

`create_schema` turns on foreign keys for the connection it is given, so call it on every new connection. These functions do not commit. The caller commits.

### Legacy Migration Limits

`migrate_legacy_history` copies the scraper's old `postings` table into the observation log. It reads the old table with `SELECT` only and is safe to run twice.

- Each successfully migrated row becomes one observation at its `last_seen` time. Rows are grouped into runs by source and `last_seen`, with the status `legacy`.
- `first_seen` and `times_seen` are not used, so earlier runs are not rebuilt.
- `returned_count` is left empty, because the number of stored rows is not the number the source returned.
- The posting key is the old `url`. If any old row has a blank or whitespace-only `url`, the migration raises a clear `ValueError` before anything is written to the target.
- On a repeat run, only rows that hit the explicit uniqueness conflicts are skipped: the same source and run time in `source_runs`, and the same run, source and posting key in `observations`. Any other constraint failure still raises an error.

### Snapshot Capture

`capture_latest_snapshot` reads the scraper's cumulative `postings` table with `SELECT` only. For each source it takes the rows with that source's latest `last_seen` and records them as one run. Rows with an older `last_seen` were not in the latest scrape, so they are left out.

- Run it after every scrape. The scraper overwrites `last_seen` on each scrape, so a scrape that was not captured before the next one cannot be rebuilt.
- A run that returned no rows cannot be inferred from this table. It leaves no row with that time, so it gets no run in the log, and a failed source looks the same.
- `returned_count` is left empty. This table keeps one row per posting across scrapes, so it cannot tell how many postings the source returned. The quality report shows `not recorded` for it, next to the observed row count.
- The posting key is the `url`. A posting with a blank `url` gets a key hashed from its title, company, location and published date, so it keeps the same key in every capture.
- A source and run time that is already in the log is skipped, so repeated calls add nothing.

Run this command from the `projects` root after every scrape:

```bash
python job_intel/capture_latest.py
```

By default it opens `job_market_scraper/output/history.db` read-only, creates or updates the ignored `job_intel/data/observations.db` (separate from `backfill.db`) and commits. Then it writes the quality report of every run in the log as `run_<id>.md` in a `quality_reports` folder beside the target database, which is the ignored `job_intel/data/quality_reports/` by default. A repeat run writes the same bytes again, and a report that failed to write is written by the next run. The command prints only the inserted row count, the number of reports written and the two paths. Pass `--source` and `--target` to override the database paths in tests.

## Run Quality Report

`build_run_quality_report` in `quality_report.py` returns a Markdown report for one run. It shows the source, run time, status, reported returned count and observed row count, then six counts:

- Blank or invalid titles.
- Nonblank invalid published dates. A blank date is not counted.
- Blank salary text.
- Nonblank salary with invalid range: one count.
- Nonblank salary with invalid currency: one count.
- Nonblank salary with invalid period: one count.

The salary checks recognize the layout of the scraper's `format_salary` fallback, `<currency> <min> - <max>` or `<currency> <value>` (for example `USD 70000 - 90000`). Not every stored salary has this layout. In `job_market_scraper/sources.py`, the Remotive and We Work Remotely parsers store the source's salary text unchanged apart from trimming. The Remote OK, Himalayas and Jobicy parsers do the same when the source sends a `salary` value, and use `format_salary` only when it is empty. So an invalid range or invalid currency count means the text was not recognized by this check. It does not prove the source's salary is wrong. A pay period is read only after a `/`, as in `USD 30 - 45 / hour`, and a salary with no `/` has no period, so it is not flagged. Each amount uses ordinary base-10 digits, with optional comma thousands separators and an optional decimal part (for example `70,000`, `1,250,000` or `30.5`). Scientific notation such as `1e5` and digit underscores such as `1_000` count as an invalid range, and so does text outside this layout, such as `USD 70000-90000` or `competitive`. Blank salaries are counted only as blank, while one nonblank salary can fail more than one check. The first whitespace-separated token is treated as the currency, so a value with no currency token, such as `70000 - 90000`, counts as invalid currency. The range uses only the tokens after that first token, so the same value also counts as invalid range.

The report only reads the database, and the same data gives the same text. A run with no returned count shows `not recorded`. A run id that does not exist raises `ValueError`.

`write_run_quality_report` saves that report as `run_<id>.md` in the output directory you choose and returns the path. Writing the same run again overwrites the same file with the same bytes.

## Backfill

`backfill.py` keeps the older CSV export apart from the observation log, in its own `backfill_postings` table. The table has the 14 export columns and an integer `id`, so identical export rows are all kept. It has no URL or description column.

`load_backfill_csv` loads one CSV file into that table.

- The header must be exactly the 14 columns, in order.
- Every row must have 14 values. The whole file is checked before anything is inserted, so a bad file leaves the table unchanged.
- The table must be empty, which stops the same export being loaded twice.
- Blank cells are stored as `NULL`.
- The load saves itself when no transaction is open on the connection.

The local database is `job_intel/data/backfill.db`. Git ignores it through the `data/` and `*.db` rules in `.gitignore`, so it is not part of a clone. On 2026-11-13 a read-only count of that file showed 10,205 rows.

## Source Salary Audit

`source_salary_audit.py` has two aggregate-only helpers that return integer count dicts and never return, log or store raw salary text:

- `summarize_remoteok_salary(records)` takes parsed Remote OK JSON record dicts and returns `records`, `salary_present`, `salary_nonblank`, `salary_min_present`, `salary_min_nonblank`, `salary_max_present` and `salary_max_nonblank`.
- `summarize_weworkremotely_salary(items)` takes parsed We Work Remotely RSS `item` elements and returns `items`, `salary_present` and `salary_nonblank` for the child `salary` element.

A missing JSON key or missing `salary` XML element is counted in neither `*_present` nor `*_nonblank`. A key or element that is present with a `None`, empty string or whitespace-only string counts as `*_present` and not `*_nonblank`. Numeric `0` and the text `0` are real values, so they count as `*_nonblank`.

This module is fixture-tested utility code only. It does not run against live feeds, read saved raw payloads, or diagnose the saved historical salary values in `history.db`.

## Tests

Run this from the `projects` root.

```bash
python -m pytest job_intel/tests
```

The tests use temporary databases and made-up values. They make no network calls and do not open the real scraper history or the real export.

## Audit Notes

- `source_fields.md`: which upstream keys each of the five parsers maps to the normalized fields.
- `source_terms.md`: what each of the five sources publishes about automated use.
- `history_snapshot.md`: what the saved scraper history holds.
- `salary_source_audit.md`: the missing salary fields for Remote OK and We Work Remotely.
- `visibility_window.md`: published timing rules against actual posting lifetime.
