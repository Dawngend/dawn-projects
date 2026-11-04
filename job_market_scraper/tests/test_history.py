from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from history import save_postings


@pytest.fixture
def posting():
    return {
        "title": "Data Scientist",
        "company": "Sample Company",
        "url": "https://example.com/jobs/1",
        "source": "remoteok",
        "location": "Worldwide",
        "published_date": "2026-11-01T08:00:00Z",
        "tags": ["python", "machine-learning"],
        "salary": "USD 100000 - 120000",
        "description": "Build forecasting models.",
    }


@pytest.fixture
def database_path():
    with tempfile.NamedTemporaryFile(
        suffix=".db", dir=Path(__file__).parent, delete=False
    ) as temporary_file:
        path = Path(temporary_file.name)

    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def read_postings(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM postings ORDER BY source, url")
        return [dict(row) for row in rows]


def test_stores_all_fields_and_ineligible_postings(database_path, posting):
    restricted = {**posting, "url": "https://example.com/jobs/2", "location": "USA Only"}
    seen_at = "2026-11-04T10:00:00+00:00"

    save_postings(database_path, [posting, restricted], seen_at=seen_at)

    rows = read_postings(database_path)
    assert len(rows) == 2
    assert rows[0] == {
        **posting,
        "tags": json.dumps(posting["tags"]),
        "first_seen": seen_at,
        "last_seen": seen_at,
        "times_seen": 1,
        "eligible": 1,
    }
    assert rows[1]["location"] == "USA Only"
    assert rows[1]["eligible"] == 0

    with closing(sqlite3.connect(database_path)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tables == [("postings",)]


def test_repeated_runs_update_counts_without_duplicates(database_path, posting):
    first_seen = "2026-11-04T10:00:00+00:00"
    last_seen = "2026-11-05T10:00:00+00:00"

    save_postings(database_path, [posting], seen_at=first_seen)
    save_postings(database_path, [posting], seen_at=last_seen)

    rows = read_postings(database_path)
    assert len(rows) == 1
    assert rows[0]["first_seen"] == first_seen
    assert rows[0]["last_seen"] == last_seen
    assert rows[0]["times_seen"] == 2

    save_postings(database_path, [posting], seen_at=last_seen)

    rows = read_postings(database_path)
    assert len(rows) == 1
    assert rows[0]["first_seen"] == first_seen
    assert rows[0]["times_seen"] == 3


def test_updates_posting_details_and_eligibility(database_path, posting):
    first_seen = "2026-11-04T10:00:00+00:00"
    last_seen = "2026-11-05T10:00:00+00:00"
    updated = {
        **posting,
        "title": "Senior Python Engineer",
        "company": "Updated Company",
        "location": "Europe Only",
        "published_date": "2026-11-03T09:00:00Z",
        "tags": ["python", "backend"],
        "salary": "",
        "description": "Maintain backend services.",
    }

    save_postings(database_path, [posting], seen_at=first_seen)
    save_postings(database_path, [updated], seen_at=last_seen)

    assert read_postings(database_path) == [{
        **updated,
        "tags": json.dumps(updated["tags"]),
        "first_seen": first_seen,
        "last_seen": last_seen,
        "times_seen": 2,
        "eligible": 0,
    }]

    updated["location"] = "Anywhere"
    save_postings(database_path, [updated], seen_at=last_seen)
    assert read_postings(database_path)[0]["eligible"] == 1


def test_absent_postings_are_not_deleted_or_counted(database_path, posting):
    other = {**posting, "url": "https://example.com/jobs/2"}
    first_seen = "2026-11-04T10:00:00+00:00"
    last_seen = "2026-11-05T10:00:00+00:00"

    save_postings(database_path, [posting, other], seen_at=first_seen)
    save_postings(database_path, [posting], seen_at=last_seen)
    before_empty_run = read_postings(database_path)
    save_postings(database_path, [], seen_at=last_seen)

    rows = read_postings(database_path)
    assert rows == before_empty_run
    assert len(rows) == 2
    assert rows[0]["times_seen"] == 2
    assert rows[1]["times_seen"] == 1
    assert rows[1]["first_seen"] == first_seen
    assert rows[1]["last_seen"] == first_seen


def test_identity_uses_source_and_url(database_path, posting):
    other_url = {**posting, "url": "https://example.com/jobs/2"}
    other_source = {**posting, "source": "remotive"}
    postings = [posting, other_url, other_source]

    save_postings(database_path, postings)
    save_postings(database_path, postings)

    rows = read_postings(database_path)
    assert len(rows) == 3
    assert {(row["source"], row["url"]) for row in rows} == {
        (item["source"], item["url"]) for item in postings
    }
    assert all(row["times_seen"] == 2 for row in rows)


def test_default_seen_time_is_current_utc(database_path, posting):
    before = datetime.now(timezone.utc)

    save_postings(database_path, [posting])

    after = datetime.now(timezone.utc)
    row = read_postings(database_path)[0]
    seen_at = datetime.fromisoformat(row["first_seen"])
    assert before <= seen_at <= after
    assert seen_at.utcoffset().total_seconds() == 0
    assert row["first_seen"] == row["last_seen"]
