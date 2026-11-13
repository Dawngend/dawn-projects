import csv


def create_backfill_schema(connection):
    # The export has no posting key, so id keeps repeated export rows apart.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS backfill_postings (
            id INTEGER PRIMARY KEY,
            source TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            published_at TEXT,
            tags_json TEXT,
            salary_min REAL,
            salary_max REAL,
            salary_currency TEXT,
            salary_period TEXT,
            eligible INTEGER,
            first_seen_at TEXT,
            last_seen_at TEXT,
            times_seen INTEGER
        )
        """
    )


def load_backfill_csv(connection, csv_path):
    columns = [
        row[1]
        for row in connection.execute("PRAGMA table_info(backfill_postings)")
        if row[1] != "id"
    ]

    stored_rows = connection.execute(
        "SELECT COUNT(*) FROM backfill_postings"
    ).fetchone()[0]
    if stored_rows:
        raise ValueError("backfill_postings is not empty")

    with open(csv_path, newline="", encoding="utf-8") as csv_file:
        reader = csv.reader(csv_file)
        header = next(reader, None)
        if header != columns:
            raise ValueError(f"expected header {columns}, found {header}")

        # The whole file is checked before any insert, so a bad row
        # cannot leave a partial load behind.
        rows = []
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(columns):
                raise ValueError(
                    f"line {line_number} has {len(row)} values, expected {len(columns)}"
                )
            rows.append([value if value != "" else None for value in row])

    placeholders = ", ".join("?" for _ in columns)
    connection.execute("SAVEPOINT load_backfill_csv")
    try:
        connection.executemany(
            f"INSERT INTO backfill_postings ({', '.join(columns)}) "
            f"VALUES ({placeholders})",
            rows,
        )
    except Exception:
        connection.execute("ROLLBACK TO load_backfill_csv")
        connection.execute("RELEASE load_backfill_csv")
        raise
    connection.execute("RELEASE load_backfill_csv")
    return len(rows)
