from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import sys
from uuid import uuid4
from unittest.mock import Mock, call
from urllib.error import URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run
import sources

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def workspace():
    directory = Path(__file__).parent / f"run-test-{uuid4().hex}"
    directory.mkdir()
    try:
        yield directory
    finally:
        shutil.rmtree(directory)


@pytest.fixture(autouse=True)
def saved_responses(monkeypatch):
    responses = {
        sources.REMOTEOK_URL: "remoteok.json",
        sources.REMOTIVE_URL: "remotive.json",
        sources.HIMALAYAS_URL: "himalayas.json",
        sources.JOBICY_URL: "jobicy.json",
        sources.WEWORKREMOTELY_URL: "weworkremotely.xml",
    }
    responses = {
        url: (FIXTURES_DIR / name).read_text(encoding="utf-8")
        for url, name in responses.items()
    }
    fetch = Mock(side_effect=responses.__getitem__)
    monkeypatch.setattr(sources, "fetch_url", fetch)
    monkeypatch.setattr(
        sources,
        "urlopen",
        Mock(side_effect=AssertionError("Network calls are not allowed in tests.")),
    )
    return fetch


def read_history(output_dir):
    with closing(sqlite3.connect(output_dir / "history.db")) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM postings ORDER BY source, url")
        return [dict(row) for row in rows]


def test_main_fetches_all_sources_and_writes_history_and_dashboard(
    workspace, saved_responses, capsys
):
    output_dir = workspace / "output"

    result = run.main(output_dir)

    assert saved_responses.call_args_list == [
        call(sources.REMOTEOK_URL),
        call(sources.REMOTIVE_URL),
        call(sources.HIMALAYAS_URL),
        call(sources.JOBICY_URL),
        call(sources.WEWORKREMOTELY_URL),
    ]
    assert result == output_dir / "dashboard.html"
    assert {path.name for path in output_dir.iterdir()} == {
        "history.db", "dashboard.html"
    }
    rows = read_history(output_dir)
    assert len(rows) == 10
    assert {row["source"] for row in rows} == {
        "remoteok", "remotive", "himalayas", "jobicy", "weworkremotely"
    }
    assert all(row["times_seen"] == 1 for row in rows)
    assert sum(row["eligible"] for row in rows) == 5

    page = result.read_text(encoding="utf-8")
    assert "10 postings seen, 5 eligible." in page
    assert page.count('class="job-row"') == 5
    for row in rows:
        if row["eligible"]:
            assert row["url"] in page
        else:
            assert row["url"] not in page
    assert "Postings fetched: 10" in capsys.readouterr().out


def test_main_reuses_history_on_later_runs(workspace):
    output_dir = workspace / "output"
    run.main(output_dir)
    first_rows = read_history(output_dir)

    run.main(output_dir)

    rows = read_history(output_dir)
    assert len(rows) == 10
    assert all(row["times_seen"] == 2 for row in rows)
    for first, current in zip(first_rows, rows):
        assert current["first_seen"] == first["first_seen"]
        assert current["last_seen"] >= first["last_seen"]
    page = (output_dir / "dashboard.html").read_text(encoding="utf-8")
    assert "10 postings seen, 5 eligible." in page


def test_main_handles_empty_source_responses(workspace, saved_responses):
    saved_responses.side_effect = [
        "[]",
        '{"jobs": []}',
        '{"jobs": []}',
        '{"jobs": []}',
        "<rss><channel></channel></rss>",
    ]
    output_dir = workspace / "output"

    result = run.main(output_dir)

    assert read_history(output_dir) == []
    assert "0 postings seen, 0 eligible." in result.read_text(encoding="utf-8")


def test_main_defaults_to_output_beside_script(workspace, monkeypatch):
    script_dir = workspace / "project"
    script_dir.mkdir()
    other_dir = workspace / "elsewhere"
    other_dir.mkdir()
    with monkeypatch.context() as patch:
        patch.setattr(run, "__file__", str(script_dir / "run.py"))
        patch.chdir(other_dir)
        result = run.main()

    assert result == script_dir / "output" / "dashboard.html"
    assert len(read_history(script_dir / "output")) == 10
    assert not (other_dir / "output").exists()


@pytest.mark.parametrize("failure", ["fetch", "parse"])
def test_source_failure_does_not_change_existing_output(
    workspace, saved_responses, failure
):
    output_dir = workspace / "output"
    dashboard_path = run.main(output_dir)
    first_rows = read_history(output_dir)
    first_page = dashboard_path.read_text(encoding="utf-8")
    if failure == "fetch":
        saved_responses.side_effect = URLError("Source unavailable")
        error = URLError
    else:
        saved_responses.side_effect = None
        saved_responses.return_value = "not json"
        error = ValueError

    with pytest.raises(error):
        run.main(output_dir)

    assert read_history(output_dir) == first_rows
    assert dashboard_path.read_text(encoding="utf-8") == first_page
