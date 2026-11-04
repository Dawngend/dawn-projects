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
Existing postings keep their first-seen time, and their seen counts increase.
Keep `output/history.db` to preserve the history.

If a source cannot be fetched or parsed, the script stops before changing either output file.
Check the reported error before trying again.

## Tests

Install pytest, then run the tests from the same folder.

```bash
python -m pip install pytest
python -m pytest -v tests/test_dashboard.py tests/test_eligibility.py tests/test_history.py tests/test_run.py tests/test_sources.py
```

Tests use saved response fixtures and temporary files. They make no network calls.
