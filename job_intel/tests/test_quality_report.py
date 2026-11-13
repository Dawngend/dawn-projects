from contextlib import closing
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observation_log import (
    create_schema,
    record_observation,
    record_source_run,
    store_description,
)
from quality_report import build_run_quality_report, write_run_quality_report


@pytest.fixture
def connection(tmp_path):
    database_path = tmp_path / "observation_log.db"
    with closing(sqlite3.connect(database_path)) as conn:
        create_schema(conn)
        yield conn


def add_observation(connection, run_id, posting_key, **fields):
    description_hash = store_description(connection, "Synthetic role description.")
    values = {
        "title": "Junior Data Analyst",
        "published_date": "2026-11-04T08:00:00+00:00",
        "salary": "USD 70000 - 90000",
    }
    values.update(fields)
    record_observation(
        connection,
        run_id,
        "board_alpha",
        posting_key,
        values["title"],
        description_hash,
        published_date=values["published_date"],
        salary=values["salary"],
    )


def test_report_shows_the_run_details_and_contract_counts(connection):
    run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00", returned_count=5
    )
    add_observation(connection, run_id, "post-1")
    add_observation(connection, run_id, "post-2", title="   ")
    add_observation(connection, run_id, "post-3", published_date="not a date")
    add_observation(connection, run_id, "post-4", salary="")

    report = build_run_quality_report(connection, run_id)

    assert report == (
        f"# Run Quality Report: Run {run_id}\n"
        "\n"
        "- Source: board_alpha\n"
        "- Run time: 2026-11-04T10:00:00+00:00\n"
        "- Status: ok\n"
        "- Reported returned count: 5\n"
        "- Observed rows: 4\n"
        "\n"
        "## Contract Checks\n"
        "\n"
        "- Blank or invalid titles: 1\n"
        "- Nonblank invalid published dates: 1\n"
        "- Blank salary text: 1\n"
        "- Nonblank salary with invalid range: 0\n"
        "- Nonblank salary with invalid currency: 0\n"
        "- Nonblank salary with invalid period: 0\n"
    )


def test_report_counts_every_failing_row_for_each_rule(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", title="")
    add_observation(connection, run_id, "post-2", title="\n\t")
    add_observation(connection, run_id, "post-3", published_date="2026-13-45")
    add_observation(connection, run_id, "post-4", published_date="12345")
    add_observation(connection, run_id, "post-5", published_date="yesterday")
    add_observation(connection, run_id, "post-6", salary="   ")
    add_observation(connection, run_id, "post-7", title="", salary="")

    report = build_run_quality_report(connection, run_id)

    assert "- Observed rows: 7\n" in report
    assert "- Blank or invalid titles: 3\n" in report
    assert "- Nonblank invalid published dates: 3\n" in report
    assert "- Blank salary text: 2\n" in report


def test_report_has_zero_counts_when_every_row_passes(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1")
    add_observation(connection, run_id, "post-2", published_date="1793772778")
    add_observation(
        connection, run_id, "post-3", published_date="Wed, 21 Jun 2023 14:22:59 +0000"
    )

    report = build_run_quality_report(connection, run_id)

    assert "- Observed rows: 3\n" in report
    assert "- Blank or invalid titles: 0\n" in report
    assert "- Nonblank invalid published dates: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_blank_published_dates_are_not_counted_as_invalid(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", published_date="")
    add_observation(connection, run_id, "post-2", published_date="   ")

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank invalid published dates: 0\n" in report


def test_free_text_salary_is_not_blank_but_fails_the_range_check(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="DOE")
    add_observation(connection, run_id, "post-2", salary="competitive")

    report = build_run_quality_report(connection, run_id)

    assert "- Blank salary text: 0\n" in report
    assert "- Nonblank salary with invalid range: 2\n" in report
    # "DOE" is three ASCII letters, so it passes the currency format check.
    assert "- Nonblank salary with invalid currency: 1\n" in report
    assert "- Nonblank salary with invalid period: 0\n" in report


def test_valid_salary_text_passes_every_salary_check(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="USD 70000 - 90000")
    add_observation(connection, run_id, "post-2", salary="eur 50000")
    add_observation(connection, run_id, "post-3", salary="USD 80000 - 80000")
    add_observation(connection, run_id, "post-4", salary="USD 30.5 - 45 / hour")
    add_observation(connection, run_id, "post-5", salary="  GBP 400 / Daily  ")

    report = build_run_quality_report(connection, run_id)

    assert "- Blank salary text: 0\n" in report
    assert "- Nonblank salary with invalid range: 0\n" in report
    assert "- Nonblank salary with invalid currency: 0\n" in report
    assert "- Nonblank salary with invalid period: 0\n" in report


def test_report_counts_nonblank_salaries_with_an_invalid_range(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="USD 90000 - 70000")
    add_observation(connection, run_id, "post-2", salary="USD -5 - 90000")
    add_observation(connection, run_id, "post-3", salary="USD 90,000 - 70,000")
    add_observation(connection, run_id, "post-4", salary="USD 70000-90000")
    add_observation(connection, run_id, "post-5", salary="USD")
    add_observation(connection, run_id, "post-6", salary="USD inf")
    add_observation(connection, run_id, "post-7", salary="USD 70000 - 90000")

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank salary with invalid range: 6\n" in report
    assert "- Nonblank salary with invalid currency: 0\n" in report
    assert "- Nonblank salary with invalid period: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_plain_base_ten_amounts_pass_the_range_check(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="USD 70,000 - 90,000")
    add_observation(connection, run_id, "post-2", salary="USD 1,250,000")
    add_observation(connection, run_id, "post-3", salary="USD 70,000.50 - 90,000.75")
    add_observation(connection, run_id, "post-4", salary="USD 30.5 - 45.25 / hour")
    add_observation(connection, run_id, "post-5", salary="USD 70000 - 90,000")
    add_observation(connection, run_id, "post-6", salary="USD 0 - 500")
    add_observation(connection, run_id, "post-7", salary="")

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank salary with invalid range: 0\n" in report
    assert "- Nonblank salary with invalid currency: 0\n" in report
    assert "- Nonblank salary with invalid period: 0\n" in report
    assert "- Blank salary text: 1\n" in report


@pytest.mark.parametrize(
    "salary",
    [
        "USD 1e5 - 2e5",
        "USD 7E4",
        "USD 1.5e3 - 9000",
        "USD 1_000 - 2_000",
        "USD 70_000",
        "USD 70000 - 90_000",
    ],
)
def test_scientific_notation_and_digit_underscores_are_invalid_ranges(
    connection, salary
):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary=salary)
    add_observation(connection, run_id, "post-2", salary="   ")

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank salary with invalid range: 1\n" in report
    assert "- Nonblank salary with invalid currency: 0\n" in report
    assert "- Nonblank salary with invalid period: 0\n" in report
    assert "- Blank salary text: 1\n" in report


@pytest.mark.parametrize(
    "salary",
    [
        "USD 70,00 - 90,000",
        "USD 7,0000",
        "USD ,500",
        "USD 70,000,",
        "USD 1,,000",
        "USD 70000.",
        "USD .5",
        "USD 70.000.5",
        "USD +70000",
        "USD nan",
        "USD 0x10",
        "USD ７００００",
    ],
)
def test_amounts_that_are_not_plain_base_ten_are_invalid_ranges(connection, salary):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary=salary)

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank salary with invalid range: 1\n" in report
    assert "- Nonblank salary with invalid currency: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_report_counts_nonblank_salaries_with_an_invalid_currency(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="US 70000 - 90000")
    add_observation(connection, run_id, "post-2", salary="USDT 70000 - 90000")
    add_observation(connection, run_id, "post-3", salary="$ 70000 - 90000")
    add_observation(connection, run_id, "post-4", salary="USD 70000 - 90000")

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank salary with invalid currency: 3\n" in report
    assert "- Nonblank salary with invalid range: 0\n" in report
    assert "- Nonblank salary with invalid period: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_report_counts_nonblank_salaries_with_an_invalid_period(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="USD 30 - 45 / fortnight")
    add_observation(connection, run_id, "post-2", salary="USD 30 - 45 / per year")
    add_observation(connection, run_id, "post-3", salary="USD 30 - 45 /")
    add_observation(connection, run_id, "post-4", salary="USD 30 - 45 / hour")
    add_observation(connection, run_id, "post-5", salary="USD 30 - 45")

    report = build_run_quality_report(connection, run_id)

    assert "- Nonblank salary with invalid period: 3\n" in report
    assert "- Nonblank salary with invalid range: 0\n" in report
    assert "- Nonblank salary with invalid currency: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_blank_salaries_are_counted_apart_from_invalid_salaries(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", salary="")
    add_observation(connection, run_id, "post-2", salary="   ")
    add_observation(connection, run_id, "post-3", salary="N/A")

    report = build_run_quality_report(connection, run_id)

    assert "- Blank salary text: 2\n" in report
    # "N/A" fails all three checks, and the two blank rows fail none of them.
    assert "- Nonblank salary with invalid range: 1\n" in report
    assert "- Nonblank salary with invalid currency: 1\n" in report
    assert "- Nonblank salary with invalid period: 1\n" in report


def test_report_shows_when_the_returned_count_was_not_recorded(connection):
    run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00", status="legacy"
    )
    add_observation(connection, run_id, "post-1")

    report = build_run_quality_report(connection, run_id)

    assert "- Status: legacy\n" in report
    assert "- Reported returned count: not recorded\n" in report
    assert "- Observed rows: 1\n" in report


def test_report_keeps_a_reported_count_of_zero(connection):
    run_id = record_source_run(
        connection,
        "board_alpha",
        "2026-11-04T10:00:00+00:00",
        status="error",
        returned_count=0,
    )

    report = build_run_quality_report(connection, run_id)

    assert "- Status: error\n" in report
    assert "- Reported returned count: 0\n" in report
    assert "- Observed rows: 0\n" in report
    assert "- Blank or invalid titles: 0\n" in report
    assert "- Nonblank invalid published dates: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_report_only_counts_rows_from_the_requested_run(connection):
    first_run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00"
    )
    second_run_id = record_source_run(
        connection, "board_alpha", "2026-11-05T10:00:00+00:00"
    )
    add_observation(connection, first_run_id, "post-1")
    add_observation(connection, second_run_id, "post-1", title="", salary="")
    add_observation(connection, second_run_id, "post-2", published_date="not a date")

    report = build_run_quality_report(connection, first_run_id)

    assert "- Run time: 2026-11-04T10:00:00+00:00\n" in report
    assert "- Observed rows: 1\n" in report
    assert "- Blank or invalid titles: 0\n" in report
    assert "- Nonblank invalid published dates: 0\n" in report
    assert "- Blank salary text: 0\n" in report


def test_report_is_the_same_each_time_and_does_not_change_the_database(connection):
    run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00", returned_count=2
    )
    add_observation(connection, run_id, "post-1", title="")
    add_observation(connection, run_id, "post-2", salary="")
    connection.commit()
    changes_before = connection.total_changes

    first_report = build_run_quality_report(connection, run_id)
    second_report = build_run_quality_report(connection, run_id)

    assert first_report == second_report
    assert connection.total_changes == changes_before


def test_report_rejects_a_run_that_does_not_exist(connection):
    with pytest.raises(ValueError, match="source run 99 was not found"):
        build_run_quality_report(connection, 99)


def test_write_report_saves_the_built_report_and_returns_its_path(connection, tmp_path):
    run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00", returned_count=2
    )
    add_observation(connection, run_id, "post-1", title="")
    add_observation(connection, run_id, "post-2", salary="")
    output_dir = tmp_path / "reports"
    output_dir.mkdir()

    report_path = write_run_quality_report(connection, run_id, output_dir)

    assert report_path == output_dir / f"run_{run_id}.md"
    assert report_path.read_text(encoding="utf-8") == build_run_quality_report(
        connection, run_id
    )
    assert [path.name for path in output_dir.iterdir()] == [f"run_{run_id}.md"]


def test_write_report_uses_plain_newlines(connection, tmp_path):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1")

    report_path = write_run_quality_report(connection, run_id, tmp_path)

    expected = build_run_quality_report(connection, run_id).encode("utf-8")
    assert report_path.read_bytes() == expected
    assert b"\r" not in report_path.read_bytes()


def test_write_report_twice_gives_the_same_single_file(connection, tmp_path):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1", published_date="not a date")

    first_path = write_run_quality_report(connection, run_id, tmp_path / "reports")
    first_bytes = first_path.read_bytes()
    second_path = write_run_quality_report(connection, run_id, tmp_path / "reports")

    assert second_path == first_path
    assert second_path.read_bytes() == first_bytes
    assert len(list((tmp_path / "reports").iterdir())) == 1


def test_write_report_keeps_one_file_per_run(connection, tmp_path):
    first_run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00"
    )
    second_run_id = record_source_run(
        connection, "board_alpha", "2026-11-05T10:00:00+00:00"
    )
    add_observation(connection, first_run_id, "post-1")
    add_observation(connection, second_run_id, "post-1", salary="")

    first_path = write_run_quality_report(connection, first_run_id, tmp_path)
    second_path = write_run_quality_report(connection, second_run_id, tmp_path)

    assert first_path != second_path
    assert "- Run time: 2026-11-04T10:00:00+00:00\n" in first_path.read_text(
        encoding="utf-8"
    )
    assert "- Blank salary text: 1\n" in second_path.read_text(encoding="utf-8")


def test_write_report_creates_a_missing_directory_and_accepts_a_text_path(
    connection, tmp_path
):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    output_dir = tmp_path / "quality" / "reports"

    report_path = write_run_quality_report(connection, run_id, str(output_dir))

    assert report_path == output_dir / f"run_{run_id}.md"
    assert report_path.is_file()


def test_write_report_writes_nothing_for_a_run_that_does_not_exist(
    connection, tmp_path
):
    output_dir = tmp_path / "reports"

    with pytest.raises(ValueError, match="source run 99 was not found"):
        write_run_quality_report(connection, 99, output_dir)

    assert not output_dir.exists()


def test_write_report_does_not_change_the_database(connection, tmp_path):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    add_observation(connection, run_id, "post-1")
    connection.commit()
    changes_before = connection.total_changes

    write_run_quality_report(connection, run_id, tmp_path)

    assert connection.total_changes == changes_before
