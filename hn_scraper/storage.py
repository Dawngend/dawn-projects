from contextlib import closing
import csv
from pathlib import Path
import sqlite3

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATABASE_PATH = OUTPUT_DIR / "posts.db"
CSV_PATH = OUTPUT_DIR / "posts.csv"

COLUMNS = ["username", "location", "url", "contact", "thread_month", "posted_time"]


def save_posts(posts, database_path=DATABASE_PATH):
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            # Each comment has its own link, so the link is the key that stops
            # the same post from being saved twice.
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    username TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT PRIMARY KEY,
                    contact TEXT NOT NULL,
                    thread_month TEXT NOT NULL,
                    posted_time TEXT NOT NULL
                )
                """
            )
            for post in posts:
                connection.execute(
                    """
                    INSERT INTO posts (
                        username, location, url, contact, thread_month, posted_time
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (url) DO UPDATE SET
                        username = excluded.username,
                        location = excluded.location,
                        contact = excluded.contact,
                        thread_month = excluded.thread_month,
                        posted_time = excluded.posted_time
                    """,
                    (
                        post["username"],
                        post["location"],
                        post["url"],
                        post["contact"],
                        post["thread_month"],
                        post["posted_time"],
                    ),
                )


def export_csv(database_path=DATABASE_PATH, csv_path=CSV_PATH):
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT username, location, url, contact, thread_month, posted_time
            FROM posts
            ORDER BY thread_month, posted_time, url
            """
        ).fetchall()

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return csv_path
