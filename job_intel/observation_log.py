import hashlib
import json


def create_schema(connection):
    # SQLite keeps foreign keys and recursive DELETE triggers (needed so
    # INSERT OR REPLACE also hits the append-only trigger) off per connection.
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS source_runs (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            run_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ok',
            returned_count INTEGER,
            error TEXT NOT NULL DEFAULT '',
            CHECK (trim(source) <> ''),
            CHECK (trim(run_at) <> ''),
            CHECK (trim(status) <> ''),
            CHECK (returned_count IS NULL OR returned_count >= 0),
            UNIQUE (source, run_at),
            UNIQUE (id, source)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS description_versions (
            content_hash TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            CHECK (trim(content_hash) <> '')
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY,
            source_run_id INTEGER NOT NULL,
            source TEXT NOT NULL,
            posting_key TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            location TEXT NOT NULL DEFAULT '',
            published_date TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT '[]',
            salary TEXT NOT NULL DEFAULT '',
            description_hash TEXT NOT NULL,
            eligible INTEGER CHECK (eligible IN (0, 1)),
            CHECK (trim(source) <> ''),
            CHECK (trim(posting_key) <> ''),
            UNIQUE (source_run_id, source, posting_key),
            FOREIGN KEY (source_run_id, source) REFERENCES source_runs (id, source),
            FOREIGN KEY (description_hash) REFERENCES description_versions (content_hash)
        )
        """
    )

    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS prevent_observations_update
        BEFORE UPDATE ON observations
        BEGIN
            SELECT RAISE(ABORT, 'observations is append-only: updates are not allowed');
        END
        """
    )

    connection.execute(
        """
        CREATE TRIGGER IF NOT EXISTS prevent_observations_delete
        BEFORE DELETE ON observations
        BEGIN
            SELECT RAISE(ABORT, 'observations is append-only: deletes are not allowed');
        END
        """
    )


def record_source_run(
    connection, source, run_at, status="ok", returned_count=None, error=""
):
    cursor = connection.execute(
        """
        INSERT INTO source_runs (source, run_at, status, returned_count, error)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source, run_at, status, returned_count, error),
    )
    return cursor.lastrowid


def store_description(connection, description):
    if not isinstance(description, str):
        raise TypeError("description must be a string")
    content_hash = hashlib.sha256(description.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT OR IGNORE INTO description_versions (content_hash, description)
        VALUES (?, ?)
        """,
        (content_hash, description),
    )
    return content_hash


def record_observation(
    connection,
    source_run_id,
    source,
    posting_key,
    title,
    description_hash,
    company="",
    url="",
    location="",
    published_date="",
    tags="[]",
    salary="",
    eligible=None,
):
    cursor = connection.execute(
        """
        INSERT INTO observations (
            source_run_id,
            source,
            posting_key,
            title,
            company,
            url,
            location,
            published_date,
            tags,
            salary,
            description_hash,
            eligible
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_run_id,
            source,
            posting_key,
            title,
            company,
            url,
            location,
            published_date,
            tags,
            salary,
            description_hash,
            eligible,
        ),
    )
    return cursor.lastrowid


def migrate_legacy_history(source_connection, target_connection):
    rows = source_connection.execute(
        """
        SELECT title, company, url, source, location, published_date,
               tags, salary, description, last_seen, eligible
        FROM postings
        ORDER BY source, last_seen, url
        """
    ).fetchall()

    for row in rows:
        url = row[2]
        if not isinstance(url, str) or not url.strip():
            raise ValueError("legacy posting url must not be blank")

    # Legacy rows only prove they were stored at last_seen, so each
    # (source, last_seen) pair becomes one run and nothing earlier is invented.
    run_ids = {}
    inserted = 0
    for (
        title,
        company,
        url,
        source,
        location,
        published_date,
        tags,
        salary,
        description,
        last_seen,
        eligible,
    ) in rows:
        run_key = (source, last_seen)
        if run_key not in run_ids:
            target_connection.execute(
                """
                INSERT INTO source_runs (source, run_at, status)
                VALUES (?, ?, 'legacy')
                ON CONFLICT (source, run_at) DO NOTHING
                """,
                run_key,
            )
            run_ids[run_key] = target_connection.execute(
                "SELECT id FROM source_runs WHERE source = ? AND run_at = ?",
                run_key,
            ).fetchone()[0]

        description_hash = store_description(target_connection, description)
        cursor = target_connection.execute(
            """
            INSERT INTO observations (
                source_run_id, source, posting_key, title, company, url,
                location, published_date, tags, salary, description_hash, eligible
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (source_run_id, source, posting_key) DO NOTHING
            """,
            (
                run_ids[run_key],
                source,
                url,
                title,
                company or "",
                url,
                location or "",
                published_date or "",
                tags or "[]",
                salary or "",
                description_hash,
                eligible,
            ),
        )
        inserted += cursor.rowcount

    return inserted


def snapshot_posting_key(url, title, company, location, published_date):
    if url and url.strip():
        return url
    # With no url, the key is a hash of the fields that tell such postings
    # apart, so the same posting gets the same key in every capture.
    fields = json.dumps([title, company, location, published_date])
    return "no-url:" + hashlib.sha256(fields.encode("utf-8")).hexdigest()


def capture_latest_snapshot(source_connection, target_connection):
    # last_seen is compared as text, which is correct while the scraper
    # keeps writing it as a UTC ISO-8601 timestamp.
    latest_runs = source_connection.execute(
        "SELECT source, MAX(last_seen) FROM postings GROUP BY source ORDER BY source"
    ).fetchall()

    inserted = 0
    for source, run_at in latest_runs:
        already_captured = target_connection.execute(
            "SELECT 1 FROM source_runs WHERE source = ? AND run_at = ?",
            (source, run_at),
        ).fetchone()
        if already_captured:
            continue

        # Rows with an older last_seen were not in the latest scrape, so they
        # are left out of this run.
        rows = source_connection.execute(
            """
            SELECT title, company, url, location, published_date,
                   tags, salary, description, eligible
            FROM postings
            WHERE source = ? AND last_seen = ?
            ORDER BY url, title, company, location, published_date
            """,
            (source, run_at),
        ).fetchall()

        # The cumulative table does not keep the raw response count, so
        # returned_count is left NULL.
        run_id = record_source_run(target_connection, source, run_at)
        for (
            title,
            company,
            url,
            location,
            published_date,
            tags,
            salary,
            description,
            eligible,
        ) in rows:
            record_observation(
                target_connection,
                run_id,
                source,
                snapshot_posting_key(url, title, company, location, published_date),
                title,
                store_description(target_connection, description),
                company=company,
                url=url,
                location=location,
                published_date=published_date,
                tags=tags,
                salary=salary,
                eligible=eligible,
            )
            inserted += 1

    return inserted
