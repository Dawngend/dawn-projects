from contextlib import closing
import csv
from pathlib import Path
import socket
import sqlite3
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run
import storage
from threads import parse_top_level_comments

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Network calls are not allowed in tests.")

    monkeypatch.setattr(socket, "socket", fail)


@pytest.fixture
def saved_comments(monkeypatch):
    text = (FIXTURES_DIR / "sample_thread.json").read_text(encoding="utf-8")
    comments = parse_top_level_comments(text)

    outside_us = dict(comments[0])
    outside_us["username"] = "elsewhere_dev"
    outside_us["text"] = outside_us["text"].replace("Austin, TX", "London, UK")
    outside_us["url"] = "https://news.ycombinator.com/item?id=45679099"
    comments.append(outside_us)

    fetch = Mock(return_value=comments)
    monkeypatch.setattr(run, "fetch_top_level_comments", fetch)
    return fetch


def read_posts(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM posts ORDER BY posted_time")
        return [dict(row) for row in rows]


@pytest.mark.parametrize(
    "month",
    [
        "2026-1",
        "2026-13",
        "2026-00",
        "26-01",
        "2026/01",
        "2026-11 ",
        "2026-11-01",
        "0000-01",
        "9999-12",
    ],
)
def test_malformed_month_fails_before_network_or_output(
    tmp_path, monkeypatch, capsys, month
):
    fetch = Mock(side_effect=AssertionError("Network must not be called."))
    monkeypatch.setattr(run, "fetch_top_level_comments", fetch)
    output_dir = tmp_path / "output"

    with pytest.raises(SystemExit) as error:
        run.main(month, output_dir)

    assert error.value.code == 2
    assert capsys.readouterr().err == (
        "error: Invalid month. Use YYYY-MM from 0001-01 to 9999-11, "
        "for example --month 2026-11.\n"
    )
    fetch.assert_not_called()
    assert not output_dir.exists()


@pytest.mark.parametrize("month", ["0001-01", "2026-01", "2026-12", "9999-11"])
def test_valid_month_boundaries_are_accepted(monkeypatch, month):
    requested = []

    def fake_fetch(requested_month):
        requested.append(requested_month)
        return []

    monkeypatch.setattr(run, "fetch_top_level_comments", fake_fetch)
    monkeypatch.setattr(run, "save_posts", Mock())
    monkeypatch.setattr(run, "export_csv", Mock())

    run.main(month, "output")

    assert requested == [month]


def test_main_saves_us_posts_for_the_month(tmp_path, saved_comments, capsys):
    output_dir = tmp_path / "output"

    result = run.main("2026-11", output_dir)

    saved_comments.assert_called_once_with("2026-11")
    assert result == output_dir / "posts.db"
    assert read_posts(output_dir / "posts.db") == [
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

    with open(output_dir / "posts.csv", newline="", encoding="utf-8") as csv_file:
        csv_rows = list(csv.reader(csv_file))
    assert csv_rows[0] == storage.COLUMNS
    assert [row[0] for row in csv_rows[1:]] == ["sample_dev", "data_person"]

    printed = capsys.readouterr().out
    assert "Comments read: 3" in printed
    assert "US posts saved: 2" in printed