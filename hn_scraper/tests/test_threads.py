from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import threads
from threads import parse_monthly_threads, parse_top_level_comments

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name):
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.text.encode("utf-8")


def test_parse_monthly_threads_keeps_only_whoishiring_for_requested_month():
    # The fixture also has a "Who is hiring?" thread, the same title from
    # someone_else, and a whoishiring thread from October 2026.
    found = parse_monthly_threads(read_fixture("monthly_threads.json"), month="2026-11")

    assert len(found) == 1
    first = found[0]
    assert first["thread_id"] == "45678901"
    assert first["title"] == "Ask HN: Who wants to be hired? (November 2026)"
    assert first["url"] == "https://news.ycombinator.com/item?id=45678901"
    assert first["thread_month"] == "2026-11"
    assert first["created_at"] == "2026-11-02T17:01:05.000Z"

    other_month = parse_monthly_threads(
        read_fixture("monthly_threads.json"), month="2026-10"
    )
    assert [thread["thread_id"] for thread in other_month] == ["45678904"]


def test_fetch_monthly_threads_asks_algolia_for_that_month(monkeypatch):
    seen_urls = []

    def fake_urlopen(request, timeout=30):
        seen_urls.append(request.full_url)
        return FakeResponse('{"hits": []}')

    monkeypatch.setattr(threads, "urlopen", fake_urlopen)

    assert threads.fetch_monthly_threads("2026-11") == '{"hits": []}'

    url = urlparse(seen_urls[0])
    assert url.netloc == "hn.algolia.com"
    assert url.path == "/api/v1/search_by_date"
    query = parse_qs(url.query)
    assert query["query"] == ["Who wants to be hired?"]
    assert query["tags"] == ["story,author_whoishiring"]
    start, end = threads.month_range("2026-11")
    assert query["numericFilters"] == [f"created_at_i>={start},created_at_i<{end}"]
    assert start < end


def test_parse_top_level_comments_from_saved_thread():
    comments = parse_top_level_comments(read_fixture("sample_thread.json"))

    # The reply under the first comment and the deleted comment are left out.
    assert len(comments) == 2

    first = comments[0]
    assert first["comment_id"] == "45679010"
    assert first["thread_id"] == "45678901"
    assert first["username"] == "sample_dev"
    assert first["url"] == "https://news.ycombinator.com/item?id=45679010"
    assert first["posted_time"] == "2026-11-02T18:15:00.000Z"
    assert first["text"].startswith("Location: Austin, TX")

    assert comments[1]["username"] == "data_person"


def test_fetch_top_level_comments_follows_the_monthly_thread(monkeypatch):
    seen_urls = []
    responses = {
        "/search_by_date": read_fixture("monthly_threads.json"),
        "/items/45678901": read_fixture("sample_thread.json"),
    }

    def fake_fetch_url(url):
        seen_urls.append(url)
        for path, text in responses.items():
            if path in url:
                return text
        raise AssertionError(f"Unexpected URL: {url}")

    def no_network(*args, **kwargs):
        raise AssertionError("Network calls are not allowed in tests.")

    monkeypatch.setattr(threads, "fetch_url", fake_fetch_url)
    # Any real network call from here would fail the test.
    monkeypatch.setattr(threads, "urlopen", no_network)

    comments = threads.fetch_top_level_comments("2026-11")

    assert len(seen_urls) == 2
    assert "/search_by_date" in seen_urls[0]
    assert "author_whoishiring" in seen_urls[0]
    assert seen_urls[1].endswith("/items/45678901")
    assert [comment["username"] for comment in comments] == ["sample_dev", "data_person"]
    assert all(comment["thread_id"] == "45678901" for comment in comments)


def test_fetch_thread_reads_the_item_endpoint(monkeypatch):
    seen_urls = []

    def fake_urlopen(request, timeout=30):
        seen_urls.append(request.full_url)
        assert request.get_header("User-agent") == "hn-scraper/1.0"
        return FakeResponse('{"id": 45678901, "children": []}')

    monkeypatch.setattr(threads, "urlopen", fake_urlopen)

    assert threads.fetch_thread("45678901") == '{"id": 45678901, "children": []}'
    assert seen_urls == ["https://hn.algolia.com/api/v1/items/45678901"]


def test_parse_empty_thread():
    assert parse_top_level_comments('{"id": 1, "children": []}') == []
    assert parse_monthly_threads('{"hits": []}') == []
