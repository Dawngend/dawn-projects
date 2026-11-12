from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import build_dashboard, load_postings, write_dashboard
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
    assert "cell.textContent.toLowerCase()" in page


def test_dashboard_search_trims_padded_query(filled_database):
    page = build_dashboard(filled_database)

    assert "const searchText = searchInput.value.trim().toLowerCase();" in page
    assert "rowText.includes(searchText)" in page
    assert "noMatchesRow.hidden = visibleCount > 0;" in page


def test_dashboard_search_does_not_match_across_adjacent_columns(filled_database):
    page = build_dashboard(filled_database)

    assert "<td>Sample Company</td><td>remoteok</td>" in page
    assert "row.textContent" not in page
    assert "Array.from(row.cells)" in page
    assert "cell.textContent.toLowerCase()" in page
    assert r'.join("\n")' in page
    assert "const searchText = searchInput.value.trim().toLowerCase();" in page
    assert "const isVisible = rowText.includes(searchText);" in page
    assert "noMatchesRow.hidden = visibleCount > 0;" in page


def test_dashboard_no_matching_row_only_with_eligible_postings(database_path):
    empty_page = build_dashboard(database_path)

    assert 'id="no-matches"' not in empty_page

    save_postings(database_path, [make_posting()])
    page = build_dashboard(database_path)

    assert (
        '<tr id="no-matches" hidden>'
        '<td colspan="7">No matching postings.</td>'
        "</tr>"
    ) in page
    assert page.count('class="job-row"') == 1
    assert 'document.getElementById("no-matches")' in page
    assert "noMatchesRow.hidden = visibleCount > 0;" in page


def test_dashboard_announces_no_matching_postings_for_screen_readers(database_path):
    empty_page = build_dashboard(database_path)

    assert 'id="no-matches"' not in empty_page
    assert '<tr><td colspan="7">No eligible postings yet.</td></tr>' in empty_page
    assert '<p id="search-status" class="sr-only" role="status"></p>' in empty_page

    save_postings(database_path, [make_posting()])
    page = build_dashboard(database_path)

    assert ".sr-only {" in page
    assert '<p id="search-status" class="sr-only" role="status"></p>' in page
    assert (
        '<tr id="no-matches" hidden>'
        '<td colspan="7">No matching postings.</td>'
        "</tr>"
    ) in page
    assert 'document.getElementById("search-status")' in page
    assert 'const statusText = visibleCount === 0 ? "No matching postings." : "";' in page
    assert "if (searchStatus.textContent !== statusText)" in page
    assert "searchStatus.textContent = statusText;" in page


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


def test_dashboard_handles_json_null_stored_tags(database_path):
    save_postings(database_path, [make_posting(tags=None)])

    assert load_postings(database_path)[0]["tags"] == []
    page = build_dashboard(database_path)

    assert "1 postings seen, 1 eligible." in page
    assert page.count('class="job-row"') == 1
    assert "<td>Data Scientist</td><td>1</td>" in page
    assert "<td>USD 100000 - 120000</td><td></td>" in page


def test_dashboard_treats_json_string_stored_tags_as_one_tag(database_path):
    save_postings(database_path, [make_posting(tags="python")])

    assert load_postings(database_path)[0]["tags"] == ["python"]
    page = build_dashboard(database_path)

    assert "<td>python</td><td>1</td>" in page
    assert "<td>USD 100000 - 120000</td><td>python</td>" in page
    assert "<td>p, y, t, h, o, n</td>" not in page


def test_dashboard_handles_json_number_stored_tags(database_path):
    save_postings(database_path, [make_posting(tags=1)])

    assert load_postings(database_path)[0]["tags"] == []
    page = build_dashboard(database_path)

    assert "1 postings seen, 1 eligible." in page
    assert page.count('class="job-row"') == 1
    assert "<td>USD 100000 - 120000</td><td></td>" in page


def test_dashboard_keeps_only_string_tags_from_mixed_scalars(database_path):
    save_postings(
        database_path,
        [make_posting(tags=["python", 1, None, True, 2.5, "sql"])],
    )

    assert load_postings(database_path)[0]["tags"] == ["python", "sql"]
    page = build_dashboard(database_path)

    assert "<td>python</td><td>1</td>" in page
    assert "<td>sql</td><td>1</td>" in page
    assert "<td>USD 100000 - 120000</td><td>python, sql</td>" in page
    assert "<td>None</td>" not in page
    assert "<td>True</td>" not in page


def test_dashboard_skips_nested_tags_in_stored_list(database_path):
    save_postings(
        database_path,
        [make_posting(tags=["python", ["nested"], {"name": "sql"}, "ml"])],
    )

    assert load_postings(database_path)[0]["tags"] == ["python", "ml"]
    page = build_dashboard(database_path)

    assert "<td>python</td><td>1</td>" in page
    assert "<td>ml</td><td>1</td>" in page
    assert "<td>USD 100000 - 120000</td><td>python, ml</td>" in page
    assert "nested" not in page
    assert "<td>sql</td>" not in page


def test_dashboard_trims_tags_and_drops_blank_tags_in_stored_list(database_path):
    save_postings(
        database_path,
        [make_posting(tags=["  python ", "", "   ", "sql\n"])],
    )

    assert load_postings(database_path)[0]["tags"] == ["python", "sql"]
    page = build_dashboard(database_path)

    assert "<td>python</td><td>1</td>" in page
    assert "<td>sql</td><td>1</td>" in page
    assert "<td>USD 100000 - 120000</td><td>python, sql</td>" in page
    assert "<td></td><td>1</td>" not in page


def test_dashboard_handles_blank_json_string_stored_tags(database_path):
    save_postings(database_path, [make_posting(tags="   ")])

    assert load_postings(database_path)[0]["tags"] == []
    page = build_dashboard(database_path)

    assert "1 postings seen, 1 eligible." in page
    assert page.count('class="job-row"') == 1
    assert "<td>USD 100000 - 120000</td><td></td>" in page


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
