from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from observation_log import (
    capture_latest_snapshot,
    create_schema,
    migrate_legacy_history,
    record_observation,
    record_source_run,
    store_description,
)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@pytest.fixture
def connection(tmp_path):
    database_path = tmp_path / "observation_log.db"
    with closing(sqlite3.connect(database_path)) as conn:
        create_schema(conn)
        yield conn


def insert_seed_records(conn):
    desc_text = "Synthetic analytics role description v1."
    desc_hash = sha256_text(desc_text)

    conn.execute(
        """
        INSERT INTO source_runs (id, source, run_at, status, returned_count)
        VALUES (1, 'board_alpha', '2026-11-04T10:00:00+00:00', 'ok', 2)
        """
    )
    conn.execute(
        """
        INSERT INTO description_versions (content_hash, description)
        VALUES (?, ?)
        """,
        (desc_hash, desc_text),
    )
    conn.execute(
        """
        INSERT INTO observations (
            source_run_id, source, posting_key, title, company, url,
            location, published_date, tags, salary, description_hash, eligible
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "board_alpha",
            "post-1",
            "Junior Data Analyst",
            "Synthetic Corp",
            "https://synthetic.example/jobs/1",
            "Anywhere",
            "2026-11-04T08:00:00+00:00",
            '["python", "sql"]',
            "USD 70000 - 90000",
            desc_hash,
            1,
        ),
    )
    return desc_hash


def test_create_schema_is_idempotent_and_preserves_rows(tmp_path):
    database_path = tmp_path / "idempotent.db"

    with closing(sqlite3.connect(database_path)) as conn:
        create_schema(conn)
        insert_seed_records(conn)
        conn.commit()

        create_schema(conn)

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        triggers = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            )
        }
        assert tables == {"source_runs", "description_versions", "observations"}
        assert triggers == {
            "prevent_observations_update",
            "prevent_observations_delete",
        }
        assert conn.execute("PRAGMA foreign_keys").fetchone() == (1,)

    with closing(sqlite3.connect(database_path)) as reopened:
        create_schema(reopened)
        count = reopened.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assert count == 1


def test_description_versions_store_once_by_hash_and_track_changes(connection):
    first_text = "Synthetic analytics role description v1."
    second_text = "Synthetic analytics role description v2."
    first_hash = insert_seed_records(connection)
    second_hash = sha256_text(second_text)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        connection.execute(
            "INSERT INTO description_versions (content_hash, description) VALUES (?, ?)",
            (first_hash, first_text),
        )

    connection.execute(
        """
        INSERT OR IGNORE INTO description_versions (content_hash, description)
        VALUES (?, ?)
        """,
        (first_hash, first_text),
    )
    connection.execute(
        """
        INSERT INTO observations (
            source_run_id, source, posting_key, title, description_hash
        ) VALUES (1, 'board_alpha', 'post-2', 'BI Analyst', ?)
        """,
        (first_hash,),
    )

    connection.execute(
        """
        INSERT INTO source_runs (id, source, run_at, status, returned_count)
        VALUES (2, 'board_alpha', '2026-11-05T10:00:00+00:00', 'ok', 1)
        """
    )
    connection.execute(
        "INSERT INTO description_versions (content_hash, description) VALUES (?, ?)",
        (second_hash, second_text),
    )
    connection.execute(
        """
        INSERT INTO observations (
            source_run_id, source, posting_key, title, description_hash
        ) VALUES (2, 'board_alpha', 'post-1', 'Junior Data Analyst', ?)
        """,
        (second_hash,),
    )

    version_count = connection.execute(
        "SELECT COUNT(*) FROM description_versions"
    ).fetchone()[0]
    assert version_count == 2

    history = connection.execute(
        """
        SELECT o.source_run_id, d.description
        FROM observations o
        JOIN description_versions d ON d.content_hash = o.description_hash
        WHERE o.posting_key = 'post-1'
        ORDER BY o.source_run_id
        """
    ).fetchall()
    assert history == [(1, first_text), (2, second_text)]


def test_uniqueness_for_source_runs_and_observations(connection):
    desc_hash = insert_seed_records(connection)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        connection.execute(
            """
            INSERT INTO source_runs (source, run_at)
            VALUES ('board_alpha', '2026-11-04T10:00:00+00:00')
            """
        )

    connection.execute(
        """
        INSERT INTO source_runs (id, source, run_at)
        VALUES (2, 'board_beta', '2026-11-04T10:00:00+00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO source_runs (id, source, run_at)
        VALUES (3, 'board_alpha', '2026-11-05T10:00:00+00:00')
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        connection.execute(
            """
            INSERT INTO observations (
                source_run_id, source, posting_key, title, description_hash
            ) VALUES (1, 'board_alpha', 'post-1', 'Duplicate Row', ?)
            """,
            (desc_hash,),
        )

    connection.execute(
        """
        INSERT INTO observations (
            source_run_id, source, posting_key, title, description_hash
        ) VALUES (3, 'board_alpha', 'post-1', 'Junior Data Analyst', ?)
        """,
        (desc_hash,),
    )
    total = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert total == 2


def test_foreign_keys_reject_missing_or_mismatched_parents(connection):
    desc_hash = insert_seed_records(connection)
    connection.execute(
        """
        INSERT INTO source_runs (id, source, run_at)
        VALUES (2, 'board_beta', '2026-11-04T10:00:00+00:00')
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        connection.execute(
            """
            INSERT INTO observations (
                source_run_id, source, posting_key, title, description_hash
            ) VALUES (99, 'board_alpha', 'post-2', 'Missing Run', ?)
            """,
            (desc_hash,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        connection.execute(
            """
            INSERT INTO observations (
                source_run_id, source, posting_key, title, description_hash
            ) VALUES (1, 'board_beta', 'post-2', 'Wrong Source For Run', ?)
            """,
            (desc_hash,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        connection.execute(
            """
            INSERT INTO observations (
                source_run_id, source, posting_key, title, description_hash
            ) VALUES (1, 'board_alpha', 'post-2', 'Missing Hash', 'missing_hash')
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        connection.execute("DELETE FROM source_runs WHERE id = 1")

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        connection.execute(
            "DELETE FROM description_versions WHERE content_hash = ?",
            (desc_hash,),
        )


def test_observations_prevent_updates_and_deletes(connection):
    desc_hash = insert_seed_records(connection)

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "UPDATE observations SET title = 'Edited Title' WHERE posting_key = 'post-1'"
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("DELETE FROM observations WHERE posting_key = 'post-1'")

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            """
            INSERT INTO observations (
                source_run_id, source, posting_key, title, description_hash
            ) VALUES (1, 'board_alpha', 'post-1', 'Upserted Title', ?)
            ON CONFLICT (source_run_id, source, posting_key)
            DO UPDATE SET title = excluded.title
            """,
            (desc_hash,),
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            """
            INSERT OR REPLACE INTO observations (
                source_run_id, source, posting_key, title, description_hash
            ) VALUES (1, 'board_alpha', 'post-1', 'Replaced Title', ?)
            """,
            (desc_hash,),
        )

    row = connection.execute(
        "SELECT title FROM observations WHERE posting_key = 'post-1'"
    ).fetchone()
    assert row == ("Junior Data Analyst",)


def test_record_source_run_inserts_one_row_and_returns_its_id(connection):
    run_id = record_source_run(
        connection,
        "board_alpha",
        "2026-11-04T10:00:00+00:00",
        status="error",
        returned_count=0,
        error="Synthetic timeout",
    )

    rows = connection.execute(
        "SELECT id, source, run_at, status, returned_count, error FROM source_runs"
    ).fetchall()
    assert rows == [
        (
            run_id,
            "board_alpha",
            "2026-11-04T10:00:00+00:00",
            "error",
            0,
            "Synthetic timeout",
        )
    ]


def test_record_source_run_uses_the_default_values(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")

    row = connection.execute(
        "SELECT status, returned_count, error FROM source_runs WHERE id = ?",
        (run_id,),
    ).fetchone()
    assert row == ("ok", None, "")


def test_record_source_run_returns_a_new_id_for_each_run(connection):
    first_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    second_id = record_source_run(connection, "board_beta", "2026-11-04T10:00:00+00:00")
    third_id = record_source_run(connection, "board_alpha", "2026-11-05T10:00:00+00:00")

    assert len({first_id, second_id, third_id}) == 3
    count = connection.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0]
    assert count == 3


def test_record_source_run_id_can_be_used_by_an_observation(connection):
    desc_text = "Synthetic analytics role description v1."
    desc_hash = sha256_text(desc_text)
    run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00", returned_count=1
    )
    connection.execute(
        "INSERT INTO description_versions (content_hash, description) VALUES (?, ?)",
        (desc_hash, desc_text),
    )
    connection.execute(
        """
        INSERT INTO observations (
            source_run_id, source, posting_key, title, description_hash
        ) VALUES (?, 'board_alpha', 'post-1', 'Junior Data Analyst', ?)
        """,
        (run_id, desc_hash),
    )

    count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 1


def test_record_source_run_rejects_a_repeated_source_and_run_time(connection):
    record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")

    count = connection.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0]
    assert count == 1


@pytest.mark.parametrize(
    "arguments",
    [
        {"source": "   ", "run_at": "2026-11-04T10:00:00+00:00"},
        {"source": "board_alpha", "run_at": ""},
        {"source": "board_alpha", "run_at": "2026-11-04T10:00:00+00:00", "status": " "},
        {
            "source": "board_alpha",
            "run_at": "2026-11-04T10:00:00+00:00",
            "returned_count": -1,
        },
    ],
)
def test_record_source_run_lets_the_schema_reject_bad_values(connection, arguments):
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        record_source_run(connection, **arguments)

    count = connection.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0]
    assert count == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {"source": None, "run_at": "2026-11-04T10:00:00+00:00"},
        {"source": "board_alpha", "run_at": None},
        {"source": "board_alpha", "run_at": "2026-11-04T10:00:00+00:00", "error": None},
    ],
)
def test_record_source_run_lets_the_schema_reject_missing_values(connection, arguments):
    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed"):
        record_source_run(connection, **arguments)


def test_store_description_hashes_the_utf8_bytes_and_keeps_the_text(connection):
    description = "Café résumé synthetic role."
    digest = store_description(connection, description)

    assert digest == hashlib.sha256(description.encode("utf-8")).hexdigest()
    rows = connection.execute(
        "SELECT content_hash, description FROM description_versions"
    ).fetchall()
    assert rows == [(digest, description)]


def test_store_description_keeps_repeated_content_once(connection):
    description = "Synthetic analytics role description v1."

    first_digest = store_description(connection, description)
    second_digest = store_description(connection, description)

    assert first_digest == second_digest
    rows = connection.execute(
        "SELECT content_hash, description FROM description_versions"
    ).fetchall()
    assert rows == [(first_digest, description)]


def test_store_description_adds_a_version_for_changed_content(connection):
    first_text = "Synthetic analytics role description v1."
    second_text = "Synthetic analytics role description v2."

    first_digest = store_description(connection, first_text)
    second_digest = store_description(connection, second_text)

    assert first_digest != second_digest
    rows = connection.execute(
        "SELECT content_hash, description FROM description_versions ORDER BY content_hash"
    ).fetchall()
    assert rows == sorted(
        [(first_digest, first_text), (second_digest, second_text)]
    )


@pytest.mark.parametrize(
    "description", [None, 123, 4.5, True, b"Synthetic bytes", ["text"], {"text": "x"}]
)
def test_store_description_rejects_non_strings(connection, description):
    with pytest.raises(TypeError, match="description must be a string"):
        store_description(connection, description)

    count = connection.execute("SELECT COUNT(*) FROM description_versions").fetchone()[0]
    assert count == 0


def test_record_observation_inserts_one_row_and_returns_its_id(connection):
    run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00", returned_count=1
    )
    desc_hash = store_description(
        connection, "Synthetic analytics role description v1."
    )

    observation_id = record_observation(
        connection,
        run_id,
        "board_alpha",
        "post-1",
        "Junior Data Analyst",
        desc_hash,
        company="Synthetic Corp",
        url="https://synthetic.example/jobs/1",
        location="Anywhere",
        published_date="2026-11-04T08:00:00+00:00",
        tags='["python", "sql"]',
        salary="USD 70000 - 90000",
        eligible=1,
    )

    rows = connection.execute(
        """
        SELECT id, source_run_id, source, posting_key, title, company, url,
               location, published_date, tags, salary, description_hash, eligible
        FROM observations
        """
    ).fetchall()
    assert rows == [
        (
            observation_id,
            run_id,
            "board_alpha",
            "post-1",
            "Junior Data Analyst",
            "Synthetic Corp",
            "https://synthetic.example/jobs/1",
            "Anywhere",
            "2026-11-04T08:00:00+00:00",
            '["python", "sql"]',
            "USD 70000 - 90000",
            desc_hash,
            1,
        )
    ]


def test_record_observation_uses_the_default_values(connection):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    desc_hash = store_description(
        connection, "Synthetic analytics role description v1."
    )

    observation_id = record_observation(
        connection, run_id, "board_alpha", "post-1", "Junior Data Analyst", desc_hash
    )

    row = connection.execute(
        """
        SELECT company, url, location, published_date, tags, salary, eligible
        FROM observations
        WHERE id = ?
        """,
        (observation_id,),
    ).fetchone()
    assert row == ("", "", "", "", "[]", "", None)


def test_record_observation_appends_across_runs_and_rejects_same_run_duplicates(
    connection,
):
    first_run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00"
    )
    second_run_id = record_source_run(
        connection, "board_alpha", "2026-11-05T10:00:00+00:00"
    )
    desc_hash = store_description(
        connection, "Synthetic analytics role description v1."
    )

    first_id = record_observation(
        connection,
        first_run_id,
        "board_alpha",
        "post-1",
        "Junior Data Analyst",
        desc_hash,
        eligible=1,
    )
    second_id = record_observation(
        connection,
        first_run_id,
        "board_alpha",
        "post-2",
        "BI Analyst",
        desc_hash,
        eligible=0,
    )
    third_id = record_observation(
        connection,
        second_run_id,
        "board_alpha",
        "post-1",
        "Junior Data Analyst",
        desc_hash,
        eligible=1,
    )

    assert len({first_id, second_id, third_id}) == 3

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        record_observation(
            connection,
            first_run_id,
            "board_alpha",
            "post-1",
            "Duplicate Entry",
            desc_hash,
        )

    count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 3


def test_record_observation_lets_the_schema_reject_bad_foreign_keys(connection):
    alpha_run_id = record_source_run(
        connection, "board_alpha", "2026-11-04T10:00:00+00:00"
    )
    record_source_run(connection, "board_beta", "2026-11-04T10:00:00+00:00")
    desc_hash = store_description(
        connection, "Synthetic analytics role description v1."
    )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        record_observation(
            connection, 999, "board_alpha", "post-1", "Missing Run", desc_hash
        )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        record_observation(
            connection,
            alpha_run_id,
            "board_beta",
            "post-1",
            "Mismatched Source",
            desc_hash,
        )

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        record_observation(
            connection,
            alpha_run_id,
            "board_alpha",
            "post-1",
            "Missing Description",
            "missing_hash",
        )

    count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"source": "   "},
        {"posting_key": ""},
        {"posting_key": "   "},
        {"eligible": 2},
        {"eligible": -1},
    ],
)
def test_record_observation_lets_the_schema_reject_invalid_values(
    connection, overrides
):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    desc_hash = store_description(
        connection, "Synthetic analytics role description v1."
    )
    arguments = {
        "source_run_id": run_id,
        "source": "board_alpha",
        "posting_key": "post-1",
        "title": "Junior Data Analyst",
        "description_hash": desc_hash,
    }
    arguments.update(overrides)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        record_observation(connection, **arguments)

    count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 0


@pytest.mark.parametrize(
    "missing_field",
    [
        "source_run_id",
        "source",
        "posting_key",
        "title",
        "description_hash",
        "company",
        "url",
        "location",
        "published_date",
        "tags",
        "salary",
    ],
)
def test_record_observation_lets_the_schema_reject_missing_values(
    connection, missing_field
):
    run_id = record_source_run(connection, "board_alpha", "2026-11-04T10:00:00+00:00")
    desc_hash = store_description(
        connection, "Synthetic analytics role description v1."
    )
    arguments = {
        "source_run_id": run_id,
        "source": "board_alpha",
        "posting_key": "post-1",
        "title": "Junior Data Analyst",
        "description_hash": desc_hash,
    }
    arguments[missing_field] = None

    with pytest.raises(sqlite3.IntegrityError, match="NOT NULL constraint failed"):
        record_observation(connection, **arguments)

    count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 0


LEGACY_COLUMNS = (
    "title",
    "company",
    "url",
    "source",
    "location",
    "published_date",
    "tags",
    "salary",
    "description",
    "first_seen",
    "last_seen",
    "times_seen",
    "eligible",
)


@pytest.fixture
def legacy_connection():
    with closing(sqlite3.connect(":memory:")) as conn:
        create_legacy_table(conn)
        yield conn


def create_legacy_table(connection):
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


def insert_legacy_posting(connection, **overrides):
    posting = {
        "title": "Junior Data Analyst",
        "company": "Synthetic Corp",
        "url": "https://synthetic.example/jobs/1",
        "source": "board_alpha",
        "location": "Anywhere",
        "published_date": "2026-11-04T08:00:00+00:00",
        "tags": '["python", "sql"]',
        "salary": "USD 70000 - 90000",
        "description": "Synthetic analytics role description v1.",
        "first_seen": "2026-11-04T10:00:00+00:00",
        "last_seen": "2026-11-04T10:00:00+00:00",
        "times_seen": 1,
        "eligible": 1,
    }
    posting.update(overrides)
    connection.execute(
        """
        INSERT INTO postings (
            title, company, url, source, location, published_date, tags,
            salary, description, first_seen, last_seen, times_seen, eligible
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(posting[column] for column in LEGACY_COLUMNS),
    )


def test_migrate_legacy_history_groups_rows_into_one_run_per_source_and_last_seen(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection)
    insert_legacy_posting(
        legacy_connection,
        url="https://synthetic.example/jobs/2",
        title="BI Analyst",
    )
    insert_legacy_posting(
        legacy_connection,
        last_seen="2026-11-05T10:00:00+00:00",
        times_seen=2,
    )
    insert_legacy_posting(
        legacy_connection,
        source="board_beta",
        url="https://synthetic.example/jobs/3",
    )

    inserted = migrate_legacy_history(legacy_connection, connection)

    assert inserted == 4
    runs = connection.execute(
        """
        SELECT source, run_at, status, returned_count
        FROM source_runs
        ORDER BY source, run_at
        """
    ).fetchall()
    assert runs == [
        ("board_alpha", "2026-11-04T10:00:00+00:00", "legacy", None),
        ("board_alpha", "2026-11-05T10:00:00+00:00", "legacy", None),
        ("board_beta", "2026-11-04T10:00:00+00:00", "legacy", None),
    ]
    count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 4


def test_migrate_legacy_history_maps_fields_at_last_seen_only(
    legacy_connection, connection
):
    insert_legacy_posting(
        legacy_connection,
        first_seen="2026-10-01T10:00:00+00:00",
        times_seen=9,
    )

    migrate_legacy_history(legacy_connection, connection)

    row = connection.execute(
        """
        SELECT o.posting_key, o.url, o.title, o.company, o.location,
               o.published_date, o.tags, o.salary, o.eligible,
               r.source, r.run_at, d.description
        FROM observations o
        JOIN source_runs r ON r.id = o.source_run_id
        JOIN description_versions d ON d.content_hash = o.description_hash
        """
    ).fetchone()
    assert row == (
        "https://synthetic.example/jobs/1",
        "https://synthetic.example/jobs/1",
        "Junior Data Analyst",
        "Synthetic Corp",
        "Anywhere",
        "2026-11-04T08:00:00+00:00",
        '["python", "sql"]',
        "USD 70000 - 90000",
        1,
        "board_alpha",
        "2026-11-04T10:00:00+00:00",
        "Synthetic analytics role description v1.",
    )

    run_count = connection.execute("SELECT COUNT(*) FROM source_runs").fetchone()[0]
    assert run_count == 1


def test_migrate_legacy_history_keeps_changed_descriptions_as_new_versions(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection)
    insert_legacy_posting(
        legacy_connection,
        url="https://synthetic.example/jobs/2",
        description="Synthetic analytics role description v2.",
    )
    insert_legacy_posting(
        legacy_connection,
        url="https://synthetic.example/jobs/3",
    )

    migrate_legacy_history(legacy_connection, connection)

    versions = connection.execute(
        "SELECT description FROM description_versions ORDER BY description"
    ).fetchall()
    assert versions == [
        ("Synthetic analytics role description v1.",),
        ("Synthetic analytics role description v2.",),
    ]

    hashes = connection.execute(
        "SELECT DISTINCT description_hash FROM observations"
    ).fetchall()
    assert len(hashes) == 2


def test_migrate_legacy_history_is_safe_to_run_twice(legacy_connection, connection):
    insert_legacy_posting(legacy_connection)
    insert_legacy_posting(
        legacy_connection,
        last_seen="2026-11-05T10:00:00+00:00",
        times_seen=2,
    )

    first_inserted = migrate_legacy_history(legacy_connection, connection)
    second_inserted = migrate_legacy_history(legacy_connection, connection)

    assert first_inserted == 2
    assert second_inserted == 0

    counts = [
        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("source_runs", "description_versions", "observations")
    ]
    assert counts == [2, 1, 2]


def test_migrate_legacy_history_migrates_a_backup_copy_of_a_file(tmp_path):
    source_path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(source_path)) as source:
        create_legacy_table(source)
        insert_legacy_posting(source)
        insert_legacy_posting(
            source, url="https://synthetic.example/jobs/2", title="BI Analyst"
        )
        insert_legacy_posting(
            source,
            url="https://synthetic.example/jobs/1",
            last_seen="2026-11-05T10:00:00+00:00",
            times_seen=2,
        )
        source.commit()

    copy_path = tmp_path / "legacy_copy.db"
    with closing(sqlite3.connect(source_path)) as source:
        with closing(sqlite3.connect(copy_path)) as copy:
            source.backup(copy)

    target_path = tmp_path / "observation_log.db"
    with closing(sqlite3.connect(copy_path)) as legacy:
        with closing(sqlite3.connect(target_path)) as target:
            create_schema(target)
            first_inserted = migrate_legacy_history(legacy, target)
            second_inserted = migrate_legacy_history(legacy, target)
            target.commit()

            counts = [
                target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("source_runs", "description_versions", "observations")
            ]

    assert (first_inserted, second_inserted) == (3, 0)
    assert counts == [2, 1, 3]

    # The original file is read only through the copy and keeps its own rows.
    with closing(sqlite3.connect(source_path)) as source:
        source_rows = source.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
        source_tables = [
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        ]
    assert source_rows == 3
    assert source_tables == ["postings"]


@pytest.mark.parametrize("blank_url", ["", "   ", "\n\t"])
def test_migrate_legacy_history_rejects_blank_urls(
    legacy_connection, connection, blank_url
):
    insert_legacy_posting(
        legacy_connection,
        url="https://synthetic.example/jobs/1",
        last_seen="2026-11-04T10:00:00+00:00",
    )
    insert_legacy_posting(
        legacy_connection,
        url=blank_url,
        last_seen="2026-11-05T10:00:00+00:00",
    )

    with pytest.raises(ValueError, match="legacy posting url must not be blank"):
        migrate_legacy_history(legacy_connection, connection)

    counts = [
        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("source_runs", "description_versions", "observations")
    ]
    assert counts == [0, 0, 0]


FIRST_SCRAPE = "2026-11-04T10:00:00+00:00"
SECOND_SCRAPE = "2026-11-05T10:00:00+00:00"
JOB_1 = "https://synthetic.example/jobs/1"
JOB_2 = "https://synthetic.example/jobs/2"
JOB_3 = "https://synthetic.example/jobs/3"
JOB_4 = "https://synthetic.example/jobs/4"


def mark_seen_again(connection, seen_at, urls):
    # The scraper keeps one row per posting and overwrites last_seen when a
    # later scrape returns the posting again.
    for url in urls:
        connection.execute(
            """
            UPDATE postings
            SET last_seen = ?, times_seen = times_seen + 1
            WHERE url = ?
            """,
            (seen_at, url),
        )


def run_posting_keys(connection, source, run_at):
    rows = connection.execute(
        """
        SELECT o.posting_key
        FROM observations o
        JOIN source_runs r ON r.id = o.source_run_id
        WHERE r.source = ? AND r.run_at = ?
        ORDER BY o.posting_key
        """,
        (source, run_at),
    ).fetchall()
    return [row[0] for row in rows]


def stored_runs(connection):
    return connection.execute(
        """
        SELECT source, run_at, status, returned_count
        FROM source_runs
        ORDER BY source, run_at
        """
    ).fetchall()


def test_capture_records_the_latest_rows_of_each_source_as_one_run(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    insert_legacy_posting(legacy_connection, url=JOB_2, title="BI Analyst")
    insert_legacy_posting(
        legacy_connection,
        source="board_beta",
        url=JOB_3,
        first_seen=SECOND_SCRAPE,
        last_seen=SECOND_SCRAPE,
    )
    changes_before = legacy_connection.total_changes

    inserted = capture_latest_snapshot(legacy_connection, connection)

    assert inserted == 3
    assert stored_runs(connection) == [
        ("board_alpha", FIRST_SCRAPE, "ok", None),
        ("board_beta", SECOND_SCRAPE, "ok", None),
    ]
    assert run_posting_keys(connection, "board_alpha", FIRST_SCRAPE) == [JOB_1, JOB_2]
    assert run_posting_keys(connection, "board_beta", SECOND_SCRAPE) == [JOB_3]
    assert legacy_connection.total_changes == changes_before


def test_capture_copies_the_fields_and_stores_the_description_by_hash(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection)

    capture_latest_snapshot(legacy_connection, connection)

    row = connection.execute(
        """
        SELECT o.posting_key, o.url, o.title, o.company, o.location,
               o.published_date, o.tags, o.salary, o.eligible,
               o.description_hash, d.description
        FROM observations o
        JOIN description_versions d ON d.content_hash = o.description_hash
        """
    ).fetchone()
    assert row == (
        JOB_1,
        JOB_1,
        "Junior Data Analyst",
        "Synthetic Corp",
        "Anywhere",
        "2026-11-04T08:00:00+00:00",
        '["python", "sql"]',
        "USD 70000 - 90000",
        1,
        sha256_text("Synthetic analytics role description v1."),
        "Synthetic analytics role description v1.",
    )


def test_capture_after_a_newer_scrape_leaves_out_postings_that_were_not_seen_again(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    insert_legacy_posting(legacy_connection, url=JOB_2)
    insert_legacy_posting(legacy_connection, url=JOB_3)
    first_inserted = capture_latest_snapshot(legacy_connection, connection)

    # The second scrape returns jobs 1 and 3 again plus a new job 4.
    # Job 2 is not returned, so its row keeps the older last_seen.
    mark_seen_again(legacy_connection, SECOND_SCRAPE, [JOB_1, JOB_3])
    insert_legacy_posting(
        legacy_connection, url=JOB_4, first_seen=SECOND_SCRAPE, last_seen=SECOND_SCRAPE
    )
    second_inserted = capture_latest_snapshot(legacy_connection, connection)

    assert (first_inserted, second_inserted) == (3, 3)
    assert stored_runs(connection) == [
        ("board_alpha", FIRST_SCRAPE, "ok", None),
        ("board_alpha", SECOND_SCRAPE, "ok", None),
    ]
    assert run_posting_keys(connection, "board_alpha", FIRST_SCRAPE) == [
        JOB_1,
        JOB_2,
        JOB_3,
    ]
    newer_keys = run_posting_keys(connection, "board_alpha", SECOND_SCRAPE)
    assert newer_keys == [JOB_1, JOB_3, JOB_4]
    assert JOB_2 not in newer_keys


def test_capture_adds_no_run_for_a_source_that_was_not_scraped_again(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    insert_legacy_posting(legacy_connection, source="board_beta", url=JOB_2)
    capture_latest_snapshot(legacy_connection, connection)

    mark_seen_again(legacy_connection, SECOND_SCRAPE, [JOB_1])
    inserted = capture_latest_snapshot(legacy_connection, connection)

    assert inserted == 1
    assert stored_runs(connection) == [
        ("board_alpha", FIRST_SCRAPE, "ok", None),
        ("board_alpha", SECOND_SCRAPE, "ok", None),
        ("board_beta", FIRST_SCRAPE, "ok", None),
    ]


def test_capture_is_safe_to_repeat(legacy_connection, connection):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    insert_legacy_posting(legacy_connection, url=JOB_2)

    first_inserted = capture_latest_snapshot(legacy_connection, connection)
    second_inserted = capture_latest_snapshot(legacy_connection, connection)

    assert (first_inserted, second_inserted) == (2, 0)
    counts = [
        connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("source_runs", "description_versions", "observations")
    ]
    assert counts == [1, 1, 2]


def test_capture_keeps_a_changed_description_as_a_new_version(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    capture_latest_snapshot(legacy_connection, connection)

    mark_seen_again(legacy_connection, SECOND_SCRAPE, [JOB_1])
    legacy_connection.execute(
        "UPDATE postings SET description = ? WHERE url = ?",
        ("Synthetic analytics role description v2.", JOB_1),
    )
    capture_latest_snapshot(legacy_connection, connection)

    history = connection.execute(
        """
        SELECT r.run_at, d.description
        FROM observations o
        JOIN source_runs r ON r.id = o.source_run_id
        JOIN description_versions d ON d.content_hash = o.description_hash
        ORDER BY r.run_at
        """
    ).fetchall()
    assert history == [
        (FIRST_SCRAPE, "Synthetic analytics role description v1."),
        (SECOND_SCRAPE, "Synthetic analytics role description v2."),
    ]


def test_capture_gives_blank_urls_the_same_fallback_key_in_every_run(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url="", title="Data Analyst")
    insert_legacy_posting(legacy_connection, url="   ", title="Data Engineer")
    capture_latest_snapshot(legacy_connection, connection)

    legacy_connection.execute(
        "UPDATE postings SET last_seen = ? WHERE title = 'Data Analyst'",
        (SECOND_SCRAPE,),
    )
    capture_latest_snapshot(legacy_connection, connection)

    analyst_fields = json.dumps(
        ["Data Analyst", "Synthetic Corp", "Anywhere", "2026-11-04T08:00:00+00:00"]
    )
    engineer_fields = json.dumps(
        ["Data Engineer", "Synthetic Corp", "Anywhere", "2026-11-04T08:00:00+00:00"]
    )
    analyst_key = "no-url:" + sha256_text(analyst_fields)
    engineer_key = "no-url:" + sha256_text(engineer_fields)

    assert analyst_key != engineer_key
    assert run_posting_keys(connection, "board_alpha", FIRST_SCRAPE) == sorted(
        [analyst_key, engineer_key]
    )
    assert run_posting_keys(connection, "board_alpha", SECOND_SCRAPE) == [analyst_key]


def test_capture_reads_a_scraper_table_that_has_the_identity_column(
    legacy_connection, connection
):
    legacy_connection.execute(
        "ALTER TABLE postings ADD COLUMN identity TEXT NOT NULL DEFAULT ''"
    )
    insert_legacy_posting(legacy_connection, url=JOB_1)

    inserted = capture_latest_snapshot(legacy_connection, connection)

    assert inserted == 1
    assert run_posting_keys(connection, "board_alpha", FIRST_SCRAPE) == [JOB_1]


def test_capture_skips_a_run_that_the_legacy_migration_already_stored(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    migrate_legacy_history(legacy_connection, connection)

    inserted = capture_latest_snapshot(legacy_connection, connection)

    assert inserted == 0
    assert stored_runs(connection) == [("board_alpha", FIRST_SCRAPE, "legacy", None)]


def test_capture_raises_instead_of_dropping_a_row_with_a_repeated_key(
    legacy_connection, connection
):
    insert_legacy_posting(legacy_connection, url=JOB_1)
    insert_legacy_posting(legacy_connection, url=JOB_1, title="BI Analyst")

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        capture_latest_snapshot(legacy_connection, connection)


def test_capture_of_an_empty_scraper_table_adds_nothing(legacy_connection, connection):
    inserted = capture_latest_snapshot(legacy_connection, connection)

    assert inserted == 0
    assert stored_runs(connection) == []
