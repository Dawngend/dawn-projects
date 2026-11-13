from contextlib import closing
import csv
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backfill import create_backfill_schema, load_backfill_csv


EXPORT_COLUMNS = [
    "source",
    "title",
    "company",
    "location",
    "published_at",
    "tags_json",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
    "eligible",
    "first_seen_at",
    "last_seen_at",
    "times_seen",
]

SYNTHETIC_ROW = (
    "board_alpha",
    "Junior Data Analyst",
    "Synthetic Corp",
    "Anywhere",
    "2026-11-04T08:00:00+00:00",
    '["python", "sql"]',
    70000,
    90000,
    "USD",
    "year",
    1,
    "2026-11-04T10:00:00+00:00",
    "2026-11-05T10:00:00+00:00",
    2,
)


@pytest.fixture
def connection(tmp_path):
    database_path = tmp_path / "backfill.db"
    with closing(sqlite3.connect(database_path)) as conn:
        create_backfill_schema(conn)
        yield conn


def insert_synthetic_row(conn):
    placeholders = ", ".join("?" for _ in EXPORT_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO backfill_postings ({", ".join(EXPORT_COLUMNS)})
        VALUES ({placeholders})
        """,
        SYNTHETIC_ROW,
    )


def test_schema_has_the_id_and_exactly_the_fourteen_export_columns(connection):
    columns = [
        row[1] for row in connection.execute("PRAGMA table_info(backfill_postings)")
    ]

    assert len(EXPORT_COLUMNS) == 14
    assert columns == ["id"] + EXPORT_COLUMNS


def test_schema_has_no_url_or_description_columns(connection):
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(backfill_postings)")
    }

    assert "url" not in columns
    assert "description" not in columns


def test_id_is_the_integer_primary_key(connection):
    primary_key_columns = [
        (row[1], row[2])
        for row in connection.execute("PRAGMA table_info(backfill_postings)")
        if row[5]
    ]

    assert primary_key_columns == [("id", "INTEGER")]


def test_schema_creates_only_the_backfill_table(connection):
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    ]

    assert tables == ["backfill_postings"]


def test_create_backfill_schema_is_safe_to_call_twice(tmp_path):
    database_path = tmp_path / "idempotent.db"

    with closing(sqlite3.connect(database_path)) as conn:
        create_backfill_schema(conn)
        insert_synthetic_row(conn)
        conn.commit()

        create_backfill_schema(conn)

        rows = conn.execute(
            f"SELECT {', '.join(EXPORT_COLUMNS)} FROM backfill_postings"
        ).fetchall()
        assert rows == [SYNTHETIC_ROW]

    with closing(sqlite3.connect(database_path)) as reopened:
        create_backfill_schema(reopened)

        columns = [
            row[1] for row in reopened.execute("PRAGMA table_info(backfill_postings)")
        ]
        count = reopened.execute("SELECT COUNT(*) FROM backfill_postings").fetchone()[0]
        assert columns == ["id"] + EXPORT_COLUMNS
        assert count == 1


def test_duplicate_export_rows_are_kept_as_separate_rows(connection):
    insert_synthetic_row(connection)
    insert_synthetic_row(connection)

    rows = connection.execute(
        f"SELECT id, {', '.join(EXPORT_COLUMNS)} FROM backfill_postings ORDER BY id"
    ).fetchall()

    assert len(rows) == 2
    assert rows[0][0] != rows[1][0]
    assert rows[0][1:] == SYNTHETIC_ROW
    assert rows[1][1:] == SYNTHETIC_ROW


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def stored_rows(conn):
    return conn.execute(
        f"SELECT {', '.join(EXPORT_COLUMNS)} FROM backfill_postings ORDER BY id"
    ).fetchall()


def test_load_backfill_csv_loads_rows_and_keeps_identical_duplicates(
    connection, tmp_path
):
    csv_path = write_csv(
        tmp_path / "backfill.csv", EXPORT_COLUMNS, [SYNTHETIC_ROW, SYNTHETIC_ROW]
    )

    loaded = load_backfill_csv(connection, csv_path)

    assert loaded == 2
    assert stored_rows(connection) == [SYNTHETIC_ROW, SYNTHETIC_ROW]


def test_load_backfill_csv_keeps_different_rows_in_file_order(connection, tmp_path):
    other_row = list(SYNTHETIC_ROW)
    other_row[0] = "board_beta"
    other_row[1] = "BI Analyst"
    csv_path = write_csv(
        tmp_path / "backfill.csv", EXPORT_COLUMNS, [other_row, SYNTHETIC_ROW]
    )

    load_backfill_csv(connection, csv_path)

    rows = stored_rows(connection)
    assert [row[0:2] for row in rows] == [
        ("board_beta", "BI Analyst"),
        ("board_alpha", "Junior Data Analyst"),
    ]


def test_load_backfill_csv_stores_blank_values_as_null(connection, tmp_path):
    row = [
        "board_alpha",
        "Junior Data Analyst",
        "Synthetic Corp",
        "",
        "2026-11-04T08:00:00+00:00",
        "[]",
        "",
        "",
        "",
        "",
        "0",
        "2026-11-04T10:00:00+00:00",
        "2026-11-04T10:00:00+00:00",
        "1",
    ]
    csv_path = write_csv(tmp_path / "backfill.csv", EXPORT_COLUMNS, [row])

    load_backfill_csv(connection, csv_path)

    stored = connection.execute(
        "SELECT location, salary_min, salary_max, salary_currency, salary_period "
        "FROM backfill_postings"
    ).fetchone()
    assert stored == (None, None, None, None, None)


@pytest.mark.parametrize(
    "header",
    [
        EXPORT_COLUMNS[:-1],
        EXPORT_COLUMNS + ["extra_column"],
        list(reversed(EXPORT_COLUMNS)),
        ["id"] + EXPORT_COLUMNS,
    ],
)
def test_load_backfill_csv_rejects_a_wrong_header(connection, tmp_path, header):
    csv_path = write_csv(tmp_path / "backfill.csv", header, [SYNTHETIC_ROW])

    with pytest.raises(ValueError, match="expected header"):
        load_backfill_csv(connection, csv_path)

    assert stored_rows(connection) == []


def test_load_backfill_csv_rejects_an_empty_file(connection, tmp_path):
    csv_path = tmp_path / "backfill.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="expected header"):
        load_backfill_csv(connection, csv_path)

    assert stored_rows(connection) == []


@pytest.mark.parametrize(
    "rows",
    [
        [SYNTHETIC_ROW[:-1]],
        [SYNTHETIC_ROW + ("extra",)],
    ],
)
def test_load_backfill_csv_rejects_malformed_row_widths(connection, tmp_path, rows):
    csv_path = write_csv(tmp_path / "backfill.csv", EXPORT_COLUMNS, rows)

    with pytest.raises(ValueError, match="has .* values, expected 14"):
        load_backfill_csv(connection, csv_path)

    assert stored_rows(connection) == []


def test_load_backfill_csv_rejects_a_bad_row_after_a_valid_row(connection, tmp_path):
    csv_path = write_csv(
        tmp_path / "backfill.csv", EXPORT_COLUMNS, [SYNTHETIC_ROW, SYNTHETIC_ROW[:-2]]
    )

    with pytest.raises(ValueError, match="line 3 has 12 values, expected 14"):
        load_backfill_csv(connection, csv_path)

    assert stored_rows(connection) == []

    # The table is still empty, so fixing the file and retrying works.
    fixed_path = write_csv(
        tmp_path / "fixed.csv", EXPORT_COLUMNS, [SYNTHETIC_ROW]
    )
    assert load_backfill_csv(connection, fixed_path) == 1
    assert stored_rows(connection) == [SYNTHETIC_ROW]


def test_load_backfill_csv_rejects_a_table_that_already_has_rows(connection, tmp_path):
    insert_synthetic_row(connection)
    csv_path = write_csv(tmp_path / "backfill.csv", EXPORT_COLUMNS, [SYNTHETIC_ROW])

    with pytest.raises(ValueError, match="is not empty"):
        load_backfill_csv(connection, csv_path)

    assert stored_rows(connection) == [SYNTHETIC_ROW]
