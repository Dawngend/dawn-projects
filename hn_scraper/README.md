# Hacker News Scraper

## Run

```bash
python run.py --month 2026-11
```

Writes `output/posts.db` and `output/posts.csv` beside `run.py`. Each row stores username, location as written, comment link, contact as written (blank when the post has none), thread month, and posted time.

## Tests

```bash
python -m pytest -v tests
```

Tests are offline. They read saved fixtures and write to temporary files.