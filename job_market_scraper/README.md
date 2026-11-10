# Job Market Scraper

Collect remote postings from RemoteOK, Remotive, Himalayas, Jobicy, and We Work Remotely.
Keep all postings in SQLite and show eligible jobs in a self-contained HTML dashboard.

## Run

Use Python 3. Run this command from `projects/job_market_scraper`.
No extra packages or API keys are needed to run the scraper.

```bash
python run.py
```

The script uses the existing fetchers, including their User-Agent and one-second request delay.
It writes `output/history.db` and `output/dashboard.html` beside `run.py`.
Open `output/dashboard.html` in a browser to view the dashboard.
The `output/` folder is ignored by Git.

Run the same command again to update the dashboard and history.
Existing postings keep their first-seen time. Each identity is counted once per run.
Identity is `(source, url)` when a URL is present. Without a URL, it uses source, title,
company, location, and publication date. Changing those fallback fields starts a new identity.
If a batch contains duplicates, all posting fields come from the last entry, including empty values.
Keep `output/history.db` to preserve the history. The next save automatically migrates older
databases, preserving stored fields and counts. Previously merged jobs cannot be recovered.

If a source cannot be fetched or parsed, the script names it in stderr and continues with
healthy sources. The console and dashboard mark these results as partial; stored history
from failed sources is retained but not refreshed. Try again later. If all sources fail,
the script exits with code 1 without changing either output file.

## Tests

Install pytest, then run the tests from the same folder.

```bash
python -m pip install pytest
python -m pytest -v tests/test_dashboard.py tests/test_eligibility.py tests/test_history.py tests/test_run.py tests/test_sources.py
```

Tests use saved response fixtures and temporary files. They make no network calls.
