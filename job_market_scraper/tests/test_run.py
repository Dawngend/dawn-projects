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
    assert "Unique postings this run: 10" in capsys.readouterr().out


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
@pytest.mark.parametrize(
    "source", ["remoteok", "remotive", "himalayas", "jobicy", "weworkremotely"]
)
def test_main_saves_healthy_sources_and_labels_partial_results(
    workspace, saved_responses, capsys, failure, source
):
    responses = saved_responses.side_effect
    failed_url = getattr(sources, f"{source.upper()}_URL")

    def fetch(url):
        if url == failed_url:
            if failure == "fetch":
                raise URLError("Source unavailable")
            return "not valid JSON or XML"
        return responses(url)

    saved_responses.side_effect = fetch
    output_dir = workspace / "output"

    result = run.main(output_dir)

    assert saved_responses.call_count == 5
    rows = read_history(output_dir)
    assert len(rows) == 8
    assert {row["source"] for row in rows} == {
        "remoteok", "remotive", "himalayas", "jobicy", "weworkremotely"
    } - {source}
    assert all(row["times_seen"] == 1 for row in rows)
    output = capsys.readouterr()
    assert f"Failed source: {source}" in output.err
    assert "Partial results: 8 unique postings this run from 4 of 5 sources." in output.out
    page = result.read_text(encoding="utf-8")
    assert f"Partial results. Failed sources: {source}." in page
    assert "8 postings seen, 4 eligible." in page


def test_partial_results_count_unique_postings_from_current_batch(
    workspace, saved_responses, capsys, monkeypatch
):
    parse_remoteok = sources.parse_remoteok

    def parse_with_duplicate(body):
        parsed = parse_remoteok(body)
        return parsed + [dict(parsed[0])]

    monkeypatch.setattr(sources, "parse_remoteok", parse_with_duplicate)
    responses = saved_responses.side_effect

    def fetch(url):
        if url == sources.JOBICY_URL:
            raise URLError("Source unavailable")
        return responses(url)

    saved_responses.side_effect = fetch
    output_dir = workspace / "output"

    run.main(output_dir)

    rows = read_history(output_dir)
    assert len(rows) == 8
    assert sum(row["source"] == "remoteok" for row in rows) == 2
    output = capsys.readouterr()
    assert "Failed source: jobicy" in output.err
    assert "Partial results: 8 unique postings this run from 4 of 5 sources." in output.out


def test_wrong_json_envelope_is_reported_as_a_parser_failure(
    workspace, saved_responses, capsys
):
    responses = saved_responses.side_effect

    def fetch(url):
        if url == sources.JOBICY_URL:
            return '{"jobs": 42}'
        return responses(url)

    saved_responses.side_effect = fetch
    output_dir = workspace / "output"

    result = run.main(output_dir)

    rows = read_history(output_dir)
    assert len(rows) == 8
    assert {row["source"] for row in rows} == {
        "remoteok", "remotive", "himalayas", "weworkremotely"
    }
    assert sum(row["eligible"] for row in rows) == 4
    output = capsys.readouterr()
    assert "Failed source: jobicy" in output.err
    assert "Partial results: 8 unique postings this run from 4 of 5 sources." in output.out
    page = result.read_text(encoding="utf-8")
    assert "Partial results. Failed sources: jobicy." in page
    assert "8 postings seen, 4 eligible." in page


@pytest.mark.parametrize(
    "source, bad_payload",
    [
        ("remoteok", "{}"),
        ("weworkremotely", "<html></html>"),
    ],
    ids=["remoteok", "weworkremotely"],
)
def test_wrong_source_envelopes_are_reported_as_parser_failures(
    workspace, saved_responses, capsys, source, bad_payload
):
    responses = saved_responses.side_effect
    failed_url = getattr(sources, f"{source.upper()}_URL")

    def fetch(url):
        if url == failed_url:
            return bad_payload
        return responses(url)

    saved_responses.side_effect = fetch
    output_dir = workspace / "output"

    result = run.main(output_dir)

    rows = read_history(output_dir)
    assert len(rows) == 8
    assert {row["source"] for row in rows} == {
        "remoteok", "remotive", "himalayas", "jobicy", "weworkremotely"
    } - {source}
    assert sum(row["eligible"] for row in rows) == 4
    output = capsys.readouterr()
    assert f"Failed source: {source}" in output.err
    assert "Partial results: 8 unique postings this run from 4 of 5 sources." in output.out
    page = result.read_text(encoding="utf-8")
    assert f"Partial results. Failed sources: {source}." in page
    assert "8 postings seen, 4 eligible." in page


@pytest.mark.parametrize("failure", ["fetch", "parse"])
def test_all_sources_failing_does_not_change_existing_output(
    workspace, saved_responses, capsys, failure
):
    output_dir = workspace / "output"
    dashboard_path = run.main(output_dir)
    first_rows = read_history(output_dir)
    first_page = dashboard_path.read_bytes()
    first_database = (output_dir / "history.db").read_bytes()
    capsys.readouterr()
    saved_responses.reset_mock()
    if failure == "fetch":
        saved_responses.side_effect = URLError("Source unavailable")
    else:
        saved_responses.side_effect = None
        saved_responses.return_value = "not json"

    with pytest.raises(SystemExit) as error:
        run.main(output_dir)

    assert error.value.code == 1
    assert saved_responses.call_count == 5
    output = capsys.readouterr()
    assert output.out == ""
    assert "No sources succeeded. Output files were not changed." in output.err
    for name in ["remoteok", "remotive", "himalayas", "jobicy", "weworkremotely"]:
        assert f"Failed source: {name}" in output.err
    assert read_history(output_dir) == first_rows
    assert dashboard_path.read_bytes() == first_page
    assert (output_dir / "history.db").read_bytes() == first_database


def test_all_sources_failing_does_not_create_output(workspace, saved_responses):
    saved_responses.side_effect = URLError("Source unavailable")
    output_dir = workspace / "output"

    with pytest.raises(SystemExit) as error:
        run.main(output_dir)

    assert error.value.code == 1
    assert saved_responses.call_count == 5
    assert not output_dir.exists()


def test_partial_run_preserves_failed_source_history_and_recovers(
    workspace, saved_responses, capsys
):
    output_dir = workspace / "output"
    run.main(output_dir)
    first_rows = read_history(output_dir)
    responses = saved_responses.side_effect

    def fetch(url):
        if url in {sources.REMOTIVE_URL, sources.JOBICY_URL}:
            raise URLError("Source unavailable")
        return responses(url)

    saved_responses.side_effect = fetch
    capsys.readouterr()
    result = run.main(output_dir)

    for first, current in zip(first_rows, read_history(output_dir)):
        if current["source"] in {"remotive", "jobicy"}:
            assert current == first
        else:
            assert current["times_seen"] == 2
            assert current["first_seen"] == first["first_seen"]
    page = result.read_text(encoding="utf-8")
    assert "Partial results. Failed sources: remotive, jobicy." in page
    assert "Stored history may include older postings from these sources." in page
    output = capsys.readouterr()
    assert "Partial results: 6 unique postings this run from 3 of 5 sources." in output.out
    assert "Failed source: remotive" in output.err
    assert "Failed source: jobicy" in output.err

    saved_responses.side_effect = responses
    run.main(output_dir)

    for row in read_history(output_dir):
        assert row["times_seen"] == (2 if row["source"] in {"remotive", "jobicy"} else 3)
    assert "Partial results" not in result.read_text(encoding="utf-8")
    output = capsys.readouterr()
    assert output.err == ""
    assert "Unique postings this run: 10" in output.out


def test_empty_healthy_source_is_not_an_all_source_failure(
    workspace, saved_responses, capsys
):
    saved_responses.side_effect = ["[]"] + [URLError("Unavailable")] * 4

    result = run.main(workspace / "output")

    assert read_history(workspace / "output") == []
    assert "Partial results" in result.read_text(encoding="utf-8")
    assert "Partial results: 0 unique postings this run from 1 of 5 sources." in capsys.readouterr().out


def test_output_errors_are_not_swallowed_as_source_failures(workspace, monkeypatch):
    save = Mock(side_effect=OSError("Cannot write history"))
    monkeypatch.setattr(run, "save_postings", save)

    with pytest.raises(OSError, match="Cannot write history"):
        run.main(workspace / "output")
