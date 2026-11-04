from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import build_dashboard, write_dashboard
from history import save_postings


@pytest.fixture
def database_path():
    with tempfile.NamedTemporaryFile(
        suffix=".db", dir=Path(__file__).parent, delete=False
    ) as temporary_file:
        path = Path(temporary_file.name)

    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def make_posting(**changes):
    posting = {
        "title": "Data Scientist",
        "company": "Sample Company",
        "url": "https://example.com/jobs/1",
        "source": "remoteok",
        "location": "Worldwide",
        "published_date": "2026-11-01T08:00:00Z",
        "tags": ["python", "machine learning"],
        "salary": "USD 100000 - 120000",
        "description": "Build forecasting models.",
    }
    posting.update(changes)
    return posting


@pytest.fixture
def filled_database(database_path):
    first_day = "2026-11-04T10:00:00+00:00"
    second_day = "2026-11-05T10:00:00+00:00"

    save_postings(
        database_path,
        [
            make_posting(),
            make_posting(
                url="https://example.com/jobs/2",
                source="remotive",
                tags=["python", "backend"],
            ),
        ],
        seen_at=first_day,
    )
    save_postings(
        database_path,
        [
            make_posting(
                title="Data Engineer",
                url="https://example.com/jobs/3",
                source="jobicy",
                tags=["python", "sql"],
            ),
            make_posting(
                title="Bookkeeper",
                url="https://example.com/jobs/4",
                source="remoteok",
                location="USA Only",
                tags=["finance"],
            ),
        ],
        seen_at=second_day,
    )
    return database_path


def test_dashboard_shows_source_totals(filled_database):
    page = build_dashboard(filled_database)

    assert "<td>remoteok</td><td>2</td><td>1</td>" in page
    assert "<td>remotive</td><td>1</td><td>1</td>" in page
    assert "<td>jobicy</td><td>1</td><td>1</td>" in page
    assert "4 postings seen, 3 eligible." in page


def test_dashboard_shows_new_postings_by_day(filled_database):
    page = build_dashboard(filled_database)

    assert "<td>2026-11-05</td><td>2</td>" in page
    assert "<td>2026-11-04</td><td>2</td>" in page


def test_dashboard_shows_common_eligible_titles_and_tags(filled_database):
    page = build_dashboard(filled_database)

    assert "<td>Data Scientist</td><td>2</td>" in page
    assert "<td>Data Engineer</td><td>1</td>" in page
    assert "<td>python</td><td>3</td>" in page
    assert "<td>machine learning</td><td>1</td>" in page
    assert "<td>finance</td>" not in page


def test_dashboard_lists_only_eligible_postings_with_links(filled_database):
    page = build_dashboard(filled_database)

    assert page.count('class="job-row"') == 3
    assert (
        '<a href="https://example.com/jobs/1" '
        'target="_blank" rel="noopener noreferrer">Data Scientist</a>'
    ) in page
    assert "https://example.com/jobs/4" not in page
    assert "Bookkeeper" not in page


def test_dashboard_search_uses_inline_script(filled_database):
    page = build_dashboard(filled_database)

    assert '<label for="job-search">Search eligible postings</label>' in page
    assert '<input id="job-search" type="search"' in page
    assert 'document.getElementById("job-search")' in page
    assert 'addEventListener("input"' in page
    assert "row.textContent.toLowerCase()" in page


def test_dashboard_has_no_outside_assets(filled_database):
    page = build_dashboard(filled_database)

    assert "<style>" in page
    assert "<link" not in page
    assert "<img" not in page
    assert " src=" not in page
    assert "@import" not in page
    assert "url(" not in page


def test_dashboard_escapes_posting_text_and_links(database_path):
    save_postings(
        database_path,
        [
            make_posting(
                title="Python <script>alert(1)</script>",
                company="North & Co <Labs>",
                url="https://example.com/jobs/1?x=1&y=2",
                tags=["python & data"],
            )
        ],
    )

    page = build_dashboard(database_path)

    assert "Python &lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "Python <script>alert(1)</script>" not in page
    assert "North &amp; Co &lt;Labs&gt;" in page
    assert 'href="https://example.com/jobs/1?x=1&amp;y=2"' in page
    assert "python &amp; data" in page


def test_dashboard_does_not_link_unsafe_urls(database_path):
    save_postings(
        database_path,
        [make_posting(url="javascript:alert(1)")],
    )

    page = build_dashboard(database_path)

    assert "javascript:" not in page
    assert "<td>Data Scientist</td>" in page


def test_dashboard_handles_an_empty_database(database_path):
    page = build_dashboard(database_path)

    assert "0 postings seen, 0 eligible." in page
    assert "No postings yet." in page
    assert "No eligible postings yet." in page
    assert 'class="job-row"' not in page


def test_write_dashboard_writes_one_html_file(filled_database):
    with tempfile.NamedTemporaryFile(
        suffix=".html", dir=Path(__file__).parent, delete=False
    ) as temporary_file:
        output_path = Path(temporary_file.name)

    try:
        result = write_dashboard(filled_database, output_path)

        assert result == output_path
        assert output_path.read_text(encoding="utf-8") == build_dashboard(filled_database)
    finally:
        output_path.unlink(missing_ok=True)
