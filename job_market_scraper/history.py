from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3

from eligibility import is_eligible


def posting_identity(posting):
    if posting["url"]:
        return json.dumps([posting["url"]])
    return json.dumps([
        posting["title"], posting["company"], posting["location"],
        posting["published_date"],
    ])


def initialize_history(connection):
    columns = [row[1] for row in connection.execute("PRAGMA table_info(postings)")]
    migrate = bool(columns) and "identity" not in columns
    if migrate:
        connection.execute("ALTER TABLE postings RENAME TO postings_old")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS postings (
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
            eligible INTEGER NOT NULL,
            identity TEXT NOT NULL,
            PRIMARY KEY (source, identity)
        )
        """
    )
    if migrate:
        for row in connection.execute("SELECT * FROM postings_old").fetchall():
            posting = dict(zip(columns, row))
            connection.execute(
                """
                INSERT INTO postings
                SELECT *, ? FROM postings_old WHERE source = ? AND url = ?
                """,
                (posting_identity(posting), posting["source"], posting["url"]),
            )
        connection.execute("DROP TABLE postings_old")


def save_postings(database_path, postings, seen_at=None):
    if seen_at is None:
        seen_at = datetime.now(timezone.utc).isoformat()

    unique_postings = {
        (posting["source"], posting_identity(posting)): posting for posting in postings
    }

    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("BEGIN")
            initialize_history(connection)
            for (_, identity), posting in unique_postings.items():
                connection.execute(
                    """
                    INSERT INTO postings (
                        title, company, url, source, location, published_date,
                        tags, salary, description, first_seen, last_seen,
                        times_seen, eligible, identity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT (source, identity) DO UPDATE SET
                        title = excluded.title,
                        company = excluded.company,
                        location = excluded.location,
                        published_date = excluded.published_date,
                        tags = excluded.tags,
                        salary = excluded.salary,
                        description = excluded.description,
                        last_seen = excluded.last_seen,
                        times_seen = postings.times_seen + 1,
                        eligible = excluded.eligible
                    """,
                    (
                        posting["title"],
                        posting["company"],
                        posting["url"],
                        posting["source"],
                        posting["location"],
                        posting["published_date"],
                        json.dumps(posting["tags"]),
                        posting["salary"],
                        posting["description"],
                        seen_at,
                        seen_at,
                        int(is_eligible(posting)),
                        identity,
                    ),
                )
    return len(unique_postings)
