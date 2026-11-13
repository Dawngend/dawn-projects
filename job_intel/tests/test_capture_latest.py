from contextlib import closing
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import capture_latest
from quality_report import build_run_quality_report

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "capture_latest.py"
PROJECTS_ROOT = Path(__file__).resolve().parents[2]

FIRST_SCRAPE = "2026-11-04T10:00:00+00:00"
SECOND_SCRAPE = "2026-11-05T10:00:00+00:00"


def write_scraper_fixture(database_path, rows):
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            """
            CREATE TABLE postings (
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                location TEXT NOT NULL,
                published_date TEXT NOT NULL,
                tags TEXT NOT NULL,
                salary TEXT NOT NULL,
                description TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                times_seen INTEGER NOT NULL,
                eligible INTEGER NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO postings (
                title, company, url, source, location, published_date, tags,
                salary, description, first_seen, last_seen, times_seen, eligible
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()


def synthetic_row(
    url, title="Junior Data Analyst", last_seen=FIRST_SCRAPE, source="board_alpha"
):
    return (
        title,
        "Synthetic Corp",
        url,
        source,
        "Anywhere",
        "2026-11-04T08:00:00+00:00",
        '["python", "sql"]',
        "USD 70000 - 90000",
        "Synthetic role description.",
        FIRST_SCRAPE,
        last_seen,
        1,
        1,
    )


def test_default_paths_use_scraper_history_and_separate_observations_db():
    assert capture_latest.DEFAULT_SOURCE == (
        PROJECTS_ROOT / "job_market_scraper" / "output" / "history.db"
    )
    assert capture_latest.DEFAULT_TARGET == (
        PROJECTS_ROOT / "job_intel" / "data" / "observations.db"
    )
    assert capture_latest.DEFAULT_TARGET.name != "backfill.db"


def test_cli_script_commits_observations_and_prints_only_counts_and_paths(tmp_path):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(
        source_path,
        [
            synthetic_row("https://synthetic.example/jobs/1"),
            synthetic_row("https://synthetic.example/jobs/2", title="BI Analyst"),
        ],
    )
    source_bytes_before = source_path.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(source_path),
            "--target",
            str(target_path),
        ],
        cwd=PROJECTS_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stderr == ""
    assert result.stdout.splitlines() == [
        "Observations inserted: 2",
        f"Observations saved to {target_path}",
        "Quality reports written: 1",
        f"Quality reports saved to {reports_dir}",
    ]
    assert "synthetic.example" not in result.stdout
    assert "Junior Data Analyst" not in result.stdout
    assert "Synthetic role description" not in result.stdout
    assert source_path.read_bytes() == source_bytes_before

    with closing(sqlite3.connect(target_path)) as target:
        run_row = target.execute(
            "SELECT source, run_at, status, returned_count FROM source_runs"
        ).fetchone()
        obs_count = target.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert run_row == ("board_alpha", FIRST_SCRAPE, "ok", None)
    assert obs_count == 2


def test_main_is_idempotent_and_captures_only_latest_scrape_after_update(
    tmp_path, capsys
):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "observations.db"
    write_scraper_fixture(
        source_path,
        [
            synthetic_row("https://synthetic.example/jobs/1"),
            synthetic_row("https://synthetic.example/jobs/2"),
        ],
    )

    first = capture_latest.main(
        ["--source", str(source_path), "--target", str(target_path)]
    )
    second = capture_latest.main(
        ["--source", str(source_path), "--target", str(target_path)]
    )

    assert (first, second) == (2, 0)

    with closing(sqlite3.connect(source_path)) as source:
        source.execute(
            """
            UPDATE postings
            SET last_seen = ?, times_seen = 2
            WHERE url = 'https://synthetic.example/jobs/1'
            """,
            (SECOND_SCRAPE,),
        )
        source.execute(
            """
            INSERT INTO postings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            synthetic_row(
                "https://synthetic.example/jobs/3", last_seen=SECOND_SCRAPE
            ),
        )
        source.commit()

    capsys.readouterr()
    third = capture_latest.main(
        ["--source", str(source_path), "--target", str(target_path)]
    )

    assert third == 2
    assert capsys.readouterr().out.splitlines() == [
        "Observations inserted: 2",
        f"Observations saved to {target_path}",
        "Quality reports written: 2",
        f"Quality reports saved to {tmp_path / 'quality_reports'}",
    ]

    with closing(sqlite3.connect(target_path)) as target:
        second_run_keys = [
            row[0]
            for row in target.execute(
                """
                SELECT o.posting_key
                FROM observations o
                JOIN source_runs r ON r.id = o.source_run_id
                WHERE r.run_at = ?
                ORDER BY o.posting_key
                """,
                (SECOND_SCRAPE,),
            )
        ]
    assert second_run_keys == [
        "https://synthetic.example/jobs/1",
        "https://synthetic.example/jobs/3",
    ]


def test_main_uses_defaults_when_called_with_no_arguments(
    tmp_path, monkeypatch, capsys
):
    source_path = tmp_path / "default_history.db"
    target_path = tmp_path / "data" / "observations.db"
    write_scraper_fixture(
        source_path, [synthetic_row("https://synthetic.example/jobs/1")]
    )
    monkeypatch.setattr(capture_latest, "DEFAULT_SOURCE", source_path)
    monkeypatch.setattr(capture_latest, "DEFAULT_TARGET", target_path)

    inserted = capture_latest.main([])

    assert inserted == 1
    assert target_path.is_file()
    assert (tmp_path / "data" / "quality_reports" / "run_1.md").is_file()
    assert capsys.readouterr().out.splitlines() == [
        "Observations inserted: 1",
        f"Observations saved to {target_path}",
        "Quality reports written: 1",
        f"Quality reports saved to {tmp_path / 'data' / 'quality_reports'}",
    ]


def test_source_connection_is_read_only_and_missing_source_creates_nothing(
    tmp_path, monkeypatch
):
    missing_source = tmp_path / "missing_history.db"
    target_path = tmp_path / "data" / "observations.db"

    with pytest.raises(sqlite3.OperationalError):
        capture_latest.main(
            ["--source", str(missing_source), "--target", str(target_path)]
        )

    assert not missing_source.exists()
    assert not target_path.exists()
    assert not (tmp_path / "data").exists()

    source_path = tmp_path / "fixture_history.db"
    write_scraper_fixture(
        source_path, [synthetic_row("https://synthetic.example/jobs/1")]
    )

    def attempt_source_write(source_conn, target_conn):
        source_conn.execute("DELETE FROM postings")
        return 0

    monkeypatch.setattr(
        capture_latest, "capture_latest_snapshot", attempt_source_write
    )
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        capture_latest.main(
            ["--source", str(source_path), "--target", str(target_path)]
        )


# In a SQLite "file:" URI, "#" starts a fragment and "%41" is read as "A",
# so these paths open the wrong file unless they are percent-encoded.
SPECIAL_SOURCE_PATHS = [
    "folder with spaces/history copy.db",
    "run#1/history#1.db",
    "100% done/history%41.db",
]


@pytest.mark.parametrize("relative_path", SPECIAL_SOURCE_PATHS)
def test_main_reads_a_source_path_with_special_characters(tmp_path, relative_path):
    source_dir = tmp_path / "source"
    source_path = source_dir / relative_path
    source_path.parent.mkdir(parents=True)
    target_path = tmp_path / "data" / "observations.db"
    write_scraper_fixture(
        source_path, [synthetic_row("https://synthetic.example/jobs/1")]
    )
    source_bytes_before = source_path.read_bytes()

    inserted = capture_latest.main(
        ["--source", str(source_path), "--target", str(target_path)]
    )

    assert inserted == 1
    assert source_path.read_bytes() == source_bytes_before
    source_files = [path for path in source_dir.rglob("*") if path.is_file()]
    assert source_files == [source_path]


@pytest.mark.parametrize("relative_path", SPECIAL_SOURCE_PATHS)
def test_source_path_with_special_characters_still_opens_read_only(
    tmp_path, monkeypatch, relative_path
):
    source_path = tmp_path / "source" / relative_path
    source_path.parent.mkdir(parents=True)
    target_path = tmp_path / "data" / "observations.db"
    write_scraper_fixture(
        source_path, [synthetic_row("https://synthetic.example/jobs/1")]
    )
    source_bytes_before = source_path.read_bytes()

    def attempt_source_write(source_conn, target_conn):
        source_conn.execute("DELETE FROM postings")
        return 0

    monkeypatch.setattr(
        capture_latest, "capture_latest_snapshot", attempt_source_write
    )
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        capture_latest.main(
            ["--source", str(source_path), "--target", str(target_path)]
        )

    assert source_path.read_bytes() == source_bytes_before


def test_missing_source_with_a_hash_in_its_name_creates_nothing(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    target_path = tmp_path / "data" / "observations.db"

    with pytest.raises(sqlite3.OperationalError, match="unable to open"):
        capture_latest.main(
            [
                "--source",
                str(source_dir / "history#1.db"),
                "--target",
                str(target_path),
            ]
        )

    assert list(source_dir.iterdir()) == []
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("filename", ["backfill.db", "BACKFILL.DB"])
def test_main_refuses_to_write_into_backfill_db(tmp_path, filename):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / filename
    write_scraper_fixture(
        source_path, [synthetic_row("https://synthetic.example/jobs/1")]
    )

    with pytest.raises(ValueError, match="backfill.db"):
        capture_latest.main(
            ["--source", str(source_path), "--target", str(target_path)]
        )

    assert not target_path.exists()
    assert not (tmp_path / "quality_reports").exists()


def read_report_bytes(reports_dir):
    return {path.name: path.read_bytes() for path in sorted(reports_dir.iterdir())}


def test_cli_script_writes_one_quality_report_for_each_captured_run(tmp_path):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(
        source_path,
        [
            synthetic_row("https://synthetic.example/jobs/1"),
            synthetic_row("https://synthetic.example/jobs/2", title="BI Analyst"),
            synthetic_row("https://synthetic.example/jobs/3", source="board_beta"),
        ],
    )
    source_bytes_before = source_path.read_bytes()

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--source",
            str(source_path),
            "--target",
            str(target_path),
        ],
        cwd=PROJECTS_ROOT,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
    )

    reports = read_report_bytes(reports_dir)
    assert sorted(reports) == ["run_1.md", "run_2.md"]
    with closing(sqlite3.connect(target_path)) as target:
        for run_id in (1, 2):
            expected = build_run_quality_report(target, run_id)
            assert reports[f"run_{run_id}.md"] == expected.encode("utf-8")

    alpha_report = reports["run_1.md"].decode("utf-8")
    assert "- Source: board_alpha\n" in alpha_report
    assert f"- Run time: {FIRST_SCRAPE}\n" in alpha_report
    assert "- Reported returned count: not recorded\n" in alpha_report
    assert "- Observed rows: 2\n" in alpha_report
    beta_report = reports["run_2.md"].decode("utf-8")
    assert "- Source: board_beta\n" in beta_report
    assert "- Observed rows: 1\n" in beta_report

    for report in (alpha_report, beta_report):
        assert "\r" not in report
        assert "synthetic.example" not in report
        assert "Analyst" not in report
        assert "Synthetic role description" not in report
    assert source_path.read_bytes() == source_bytes_before


def test_captured_run_report_says_not_recorded_and_shows_the_observed_rows(
    tmp_path,
):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(
        source_path,
        [
            synthetic_row("https://synthetic.example/jobs/1"),
            synthetic_row("https://synthetic.example/jobs/2"),
            synthetic_row("https://synthetic.example/jobs/3"),
        ],
    )

    capture_latest.main(["--source", str(source_path), "--target", str(target_path)])

    with closing(sqlite3.connect(target_path)) as target:
        returned_count = target.execute(
            "SELECT returned_count FROM source_runs"
        ).fetchone()[0]
    report = (reports_dir / "run_1.md").read_text(encoding="utf-8")

    assert returned_count is None
    assert "- Reported returned count: not recorded\n" in report
    assert "- Observed rows: 3\n" in report


def test_repeat_run_leaves_the_quality_report_bytes_unchanged(tmp_path):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(
        source_path,
        [
            synthetic_row("https://synthetic.example/jobs/1"),
            synthetic_row("https://synthetic.example/jobs/2", source="board_beta"),
        ],
    )
    arguments = ["--source", str(source_path), "--target", str(target_path)]

    first = capture_latest.main(arguments)
    reports_after_first = read_report_bytes(reports_dir)
    second = capture_latest.main(arguments)
    reports_after_second = read_report_bytes(reports_dir)

    assert (first, second) == (2, 0)
    assert sorted(reports_after_first) == ["run_1.md", "run_2.md"]
    assert reports_after_second == reports_after_first


def test_newer_scrape_adds_a_report_and_keeps_the_older_report_bytes(tmp_path):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(
        source_path,
        [
            synthetic_row("https://synthetic.example/jobs/1"),
            synthetic_row("https://synthetic.example/jobs/2"),
        ],
    )
    arguments = ["--source", str(source_path), "--target", str(target_path)]
    capture_latest.main(arguments)
    reports_after_first = read_report_bytes(reports_dir)

    # The second scrape returns only job 1 again.
    with closing(sqlite3.connect(source_path)) as source:
        source.execute(
            """
            UPDATE postings
            SET last_seen = ?, times_seen = 2
            WHERE url = 'https://synthetic.example/jobs/1'
            """,
            (SECOND_SCRAPE,),
        )
        source.commit()
    capture_latest.main(arguments)
    reports_after_second = read_report_bytes(reports_dir)

    assert sorted(reports_after_second) == ["run_1.md", "run_2.md"]
    assert reports_after_second["run_1.md"] == reports_after_first["run_1.md"]
    newer_report = reports_after_second["run_2.md"].decode("utf-8")
    assert f"- Run time: {SECOND_SCRAPE}\n" in newer_report
    assert "- Observed rows: 1\n" in newer_report


def test_failed_report_write_keeps_the_capture_and_the_next_run_writes_the_report(
    tmp_path, monkeypatch
):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(
        source_path, [synthetic_row("https://synthetic.example/jobs/1")]
    )
    arguments = ["--source", str(source_path), "--target", str(target_path)]

    def fail_to_write(connection, source_run_id, output_dir):
        raise OSError("synthetic write failure")

    with monkeypatch.context() as patch:
        patch.setattr(capture_latest, "write_run_quality_report", fail_to_write)
        with pytest.raises(OSError, match="synthetic write failure"):
            capture_latest.main(arguments)

    with closing(sqlite3.connect(target_path)) as target:
        saved_rows = target.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert saved_rows == 1
    assert not reports_dir.exists()

    inserted = capture_latest.main(arguments)

    assert inserted == 0
    assert sorted(read_report_bytes(reports_dir)) == ["run_1.md"]


def test_empty_scraper_table_writes_no_reports(tmp_path, capsys):
    source_path = tmp_path / "fixture_history.db"
    target_path = tmp_path / "data" / "observations.db"
    reports_dir = tmp_path / "data" / "quality_reports"
    write_scraper_fixture(source_path, [])

    inserted = capture_latest.main(
        ["--source", str(source_path), "--target", str(target_path)]
    )

    assert inserted == 0
    assert not reports_dir.exists()
    assert capsys.readouterr().out.splitlines() == [
        "Observations inserted: 0",
        f"Observations saved to {target_path}",
        "Quality reports written: 0",
        f"Quality reports saved to {reports_dir}",
    ]
