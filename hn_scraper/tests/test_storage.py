from contextlib import closing
import csv
from pathlib import Path
import socket
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage
from storage import export_csv, save_posts


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Network calls are not allowed in tests.")

    monkeypatch.setattr(socket, "socket", fail)


@pytest.fixture
def posts():
    return [
        {
            "username": "sample_dev",
            "location": "Austin, TX",
            "url": "https://news.ycombinator.com/item?id=45679010",
            "contact": "sample at example dot com",
            "thread_month": "2026-11",
            "posted_time": "2026-11-02T18:15:00.000Z",
        },
        {
            "username": "data_person",
            "location": "Remote (US)",
            "url": "https://news.ycombinator.com/item?id=45679020",
            "contact": "",
            "thread_month": "2026-11",
            "posted_time": "2026-11-02T20:30:00.000Z",
        },
    ]


def read_posts(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM posts ORDER BY posted_time")
        return [dict(row) for row in rows]


def read_csv(csv_path):
    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        return list(csv.reader(csv_file))


def test_saves_posts_as_written(tmp_path, posts):
    database_path = tmp_path / "posts.db"

    save_posts(posts, database_path)

    assert read_posts(database_path) == posts


def test_running_twice_keeps_the_same_rows(tmp_path, posts):
    database_path = tmp_path / "posts.db"

    save_posts(posts, database_path)
    first_run = read_posts(database_path)
    save_posts(posts, database_path)

    assert read_posts(database_path) == first_run
    assert len(first_run) == 2


def test_same_post_twice_in_one_run_is_saved_once(tmp_path, posts):
    database_path = tmp_path / "posts.db"

    save_posts([posts[0], posts[0]], database_path)

    assert read_posts(database_path) == [posts[0]]


def test_edited_post_replaces_the_old_row(tmp_path, posts):
    database_path = tmp_path / "posts.db"
    edited = {**posts[0], "location": "Dallas, TX", "contact": "new at example dot com"}

    save_posts(posts, database_path)
    save_posts([edited], database_path)

    assert read_posts(database_path) == [edited, posts[1]]


def test_csv_export_has_one_row_per_post(tmp_path, posts):
    database_path = tmp_path / "posts.db"
    csv_path = tmp_path / "output" / "posts.csv"

    save_posts(posts, database_path)
    save_posts(posts, database_path)
    written_path = export_csv(database_path, csv_path)

    assert written_path == csv_path
    assert read_csv(csv_path) == [
        storage.COLUMNS,
        [
            "sample_dev",
            "Austin, TX",
            "https://news.ycombinator.com/item?id=45679010",
            "sample at example dot com",
            "2026-11",
            "2026-11-02T18:15:00.000Z",
        ],
        [
            "data_person",
            "Remote (US)",
            "https://news.ycombinator.com/item?id=45679020",
            "",
            "2026-11",
            "2026-11-02T20:30:00.000Z",
        ],
    ]


def test_default_files_go_in_output_folder():
    hn_scraper_dir = Path(storage.__file__).resolve().parent

    assert storage.DATABASE_PATH == hn_scraper_dir / "output" / "posts.db"
    assert storage.CSV_PATH == hn_scraper_dir / "output" / "posts.csv"
