from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3

from eligibility import is_eligible


def save_postings(database_path, postings, seen_at=None):
    if seen_at is None:
        seen_at = datetime.now(timezone.utc).isoformat()

    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
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
                    PRIMARY KEY (source, url)
                )
                """
            )
            for posting in postings:
                connection.execute(
                    """
                    INSERT INTO postings (
                        title, company, url, source, location, published_date,
                        tags, salary, description, first_seen, last_seen,
                        times_seen, eligible
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    ON CONFLICT (source, url) DO UPDATE SET
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
                    ),
                )
