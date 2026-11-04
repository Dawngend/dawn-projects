from collections import Counter
from contextlib import closing
from html import escape
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlparse


def load_postings(database_path):
    with closing(sqlite3.connect(database_path)) as connection:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'postings'"
        ).fetchone()
        if table is None:
            return []

        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT title, company, url, source, location, published_date, tags,
                   salary, description, first_seen, last_seen, times_seen, eligible
            FROM postings
            ORDER BY first_seen DESC, title
            """
        ).fetchall()

    postings = []
    for row in rows:
        posting = dict(row)
        try:
            posting["tags"] = json.loads(posting["tags"])
        except json.JSONDecodeError:
            posting["tags"] = []
        postings.append(posting)
    return postings


def count_by_source(postings):
    totals = Counter()
    eligible_totals = Counter()
    for posting in postings:
        totals[posting["source"]] += 1
        if posting["eligible"]:
            eligible_totals[posting["source"]] += 1

    rows = [
        (source, totals[source], eligible_totals[source]) for source in totals
    ]
    return sorted(rows, key=lambda row: (-row[1], row[0]))


def count_new_by_day(postings):
    counts = Counter(posting["first_seen"][:10] for posting in postings)
    return sorted(counts.items(), reverse=True)


def count_common(values, limit=10):
    counts = Counter(values)
    rows = sorted(counts.items(), key=lambda row: (-row[1], row[0].lower()))
    return rows[:limit]


def source_rows(rows):
    if not rows:
        return '<tr><td colspan="3">No postings yet.</td></tr>'
    return "\n".join(
        "<tr>"
        f"<td>{escape(source)}</td>"
        f"<td>{total}</td>"
        f"<td>{eligible}</td>"
        "</tr>"
        for source, total, eligible in rows
    )


def count_rows(rows, empty_message):
    if not rows:
        return f'<tr><td colspan="2">{escape(empty_message)}</td></tr>'
    return "\n".join(
        "<tr>"
        f"<td>{escape(str(name))}</td>"
        f"<td>{count}</td>"
        "</tr>"
        for name, count in rows
    )


def safe_url(url):
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return url
    return ""


def job_rows(postings):
    if not postings:
        return '<tr><td colspan="7">No eligible postings yet.</td></tr>'

    rows = []
    for posting in postings:
        tags = ", ".join(posting["tags"])
        url = safe_url(posting["url"])
        title = escape(posting["title"])
        if url:
            title = (
                f'<a href="{escape(url, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{title}</a>'
            )
        rows.append(
            '<tr class="job-row">'
            f"<td>{title}</td>"
            f"<td>{escape(posting['company'])}</td>"
            f"<td>{escape(posting['source'])}</td>"
            f"<td>{escape(posting['location'])}</td>"
            f"<td>{escape(posting['published_date'])}</td>"
            f"<td>{escape(posting['salary'])}</td>"
            f"<td>{escape(tags)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def build_dashboard(database_path):
    postings = load_postings(database_path)
    eligible_postings = [posting for posting in postings if posting["eligible"]]
    titles = count_common(posting["title"] for posting in eligible_postings)
    tags = count_common(
        tag for posting in eligible_postings for tag in posting["tags"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Market Dashboard</title>
<style>
  body {{
    color: #1f2937;
    font-family: Arial, Helvetica, sans-serif;
    line-height: 1.5;
    margin: 0;
  }}
  main {{
    margin: 0 auto;
    max-width: 1100px;
    padding: 24px 16px 40px;
  }}
  h1, h2 {{
    line-height: 1.2;
  }}
  section {{
    margin-top: 32px;
  }}
  .table-wrap {{
    overflow-x: auto;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
  }}
  caption {{
    font-weight: bold;
    padding: 8px;
    text-align: left;
  }}
  th, td {{
    border: 1px solid #d1d5db;
    padding: 8px;
    text-align: left;
    vertical-align: top;
  }}
  th {{
    background: #f3f4f6;
  }}
  label {{
    display: block;
    font-weight: bold;
    margin-bottom: 6px;
  }}
  input {{
    box-sizing: border-box;
    font: inherit;
    max-width: 480px;
    padding: 8px;
    width: 100%;
  }}
  a {{
    color: #075985;
  }}
</style>
</head>
<body>
<main>
  <h1>Job Market Dashboard</h1>
  <p>{len(postings)} postings seen, {len(eligible_postings)} eligible.</p>

  <section>
    <h2>Totals by Source</h2>
    <div class="table-wrap">
      <table>
        <caption>All postings stored from each source</caption>
        <thead>
          <tr><th scope="col">Source</th><th scope="col">All postings</th><th scope="col">Eligible</th></tr>
        </thead>
        <tbody>
          {source_rows(count_by_source(postings))}
        </tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>New Postings by Day</h2>
    <div class="table-wrap">
      <table>
        <caption>Postings first seen on each day</caption>
        <thead>
          <tr><th scope="col">Date</th><th scope="col">New postings</th></tr>
        </thead>
        <tbody>
          {count_rows(count_new_by_day(postings), "No postings yet.")}
        </tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Most Common Eligible Titles</h2>
    <div class="table-wrap">
      <table>
        <caption>Top 10 titles among eligible postings</caption>
        <thead>
          <tr><th scope="col">Title</th><th scope="col">Postings</th></tr>
        </thead>
        <tbody>
          {count_rows(titles, "No eligible postings yet.")}
        </tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Most Common Eligible Tags</h2>
    <div class="table-wrap">
      <table>
        <caption>Top 10 tags among eligible postings</caption>
        <thead>
          <tr><th scope="col">Tag</th><th scope="col">Postings</th></tr>
        </thead>
        <tbody>
          {count_rows(tags, "No eligible postings yet.")}
        </tbody>
      </table>
    </div>
  </section>

  <section>
    <h2>Eligible Postings</h2>
    <label for="job-search">Search eligible postings</label>
    <input id="job-search" type="search" placeholder="Search title, company, source, location, salary, or tag">
    <div class="table-wrap">
      <table id="jobs-table">
        <caption>Eligible postings with links to the source posting</caption>
        <thead>
          <tr>
            <th scope="col">Title</th>
            <th scope="col">Company</th>
            <th scope="col">Source</th>
            <th scope="col">Location</th>
            <th scope="col">Published</th>
            <th scope="col">Salary</th>
            <th scope="col">Tags</th>
          </tr>
        </thead>
        <tbody>
          {job_rows(eligible_postings)}
        </tbody>
      </table>
    </div>
  </section>
</main>
<script>
  const searchInput = document.getElementById("job-search");
  const jobRows = document.querySelectorAll(".job-row");

  searchInput.addEventListener("input", function () {{
    const searchText = searchInput.value.toLowerCase();
    jobRows.forEach(function (row) {{
      const rowText = row.textContent.toLowerCase();
      row.style.display = rowText.includes(searchText) ? "" : "none";
    }});
  }});
</script>
</body>
</html>
"""


def write_dashboard(database_path, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_dashboard(database_path), encoding="utf-8")
    return output_path
