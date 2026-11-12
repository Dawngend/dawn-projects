from io import BytesIO
from pathlib import Path
import sys
from urllib.error import URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sources
from sources import (
    POSTING_FIELDS,
    parse_himalayas,
    parse_jobicy,
    parse_remoteok,
    parse_remotive,
    parse_weworkremotely,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name):
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def assert_posting_shape(postings, expected_source):
    assert len(postings) > 0
    for post in postings:
        assert tuple(post.keys()) == POSTING_FIELDS
        assert post["source"] == expected_source
        assert isinstance(post["tags"], list)


def test_fetch_url_waits_after_a_successful_fetch(monkeypatch):
    sleeps = []
    monkeypatch.setattr(sources, "urlopen", lambda request, timeout: BytesIO(b"body"))
    monkeypatch.setattr(sources.time, "sleep", sleeps.append)

    body = sources.fetch_url("https://example.com/api")

    assert body == "body"
    assert sleeps == [1.0]


def test_fetch_url_waits_when_fetching_fails(monkeypatch):
    sleeps = []

    def fail(request, timeout):
        raise URLError("connection refused")

    monkeypatch.setattr(sources, "urlopen", fail)
    monkeypatch.setattr(sources.time, "sleep", sleeps.append)

    with pytest.raises(URLError):
        sources.fetch_url("https://example.com/api")

    assert sleeps == [1.0]


def test_fetch_url_waits_when_decoding_fails(monkeypatch):
    sleeps = []
    monkeypatch.setattr(sources, "urlopen", lambda request, timeout: BytesIO(b"\xff"))
    monkeypatch.setattr(sources.time, "sleep", sleeps.append)

    with pytest.raises(UnicodeDecodeError):
        sources.fetch_url("https://example.com/api")

    assert sleeps == [1.0]


def test_parse_remoteok():
    postings = parse_remoteok(read_fixture("remoteok.json"))
    assert_posting_shape(postings, "remoteok")
    assert len(postings) == 2

    first = postings[0]
    assert first["title"] == "Machine Learning Engineer"
    assert first["company"] == "Northstar AI"
    assert first["url"] == "https://remoteok.com/remote-jobs/1001"
    assert first["location"] == "Worldwide"
    assert first["published_date"] == "2026-11-01T10:00:00+00:00"
    assert first["tags"] == ["python", "machine-learning", "pytorch"]
    assert first["salary"] == "USD 130000 - 170000"
    assert first["description"] == "Build and deploy machine learning models in Python."

    assert postings[1]["salary"] == ""


def test_parse_remotive():
    postings = parse_remotive(read_fixture("remotive.json"))
    assert_posting_shape(postings, "remotive")
    assert len(postings) == 2

    first = postings[0]
    assert first["title"] == "Backend Python Engineer"
    assert first["company"] == "CloudPipe"
    assert first["url"] == "https://remotive.com/remote-jobs/software-dev/backend-python-engineer-2001"
    assert first["location"] == "Worldwide"
    assert first["published_date"] == "2026-11-01T09:15:00"
    assert first["tags"] == ["python", "backend", "postgresql"]
    assert first["salary"] == "$120,000 - $150,000"
    assert first["description"] == "Maintain backend services and data pipelines."

    assert postings[1]["salary"] == ""


def test_parse_himalayas():
    postings = parse_himalayas(read_fixture("himalayas.json"))
    assert_posting_shape(postings, "himalayas")
    assert len(postings) == 2

    first = postings[0]
    assert first["title"] == "Data Scientist"
    assert first["company"] == "Signal Labs"
    assert first["url"] == "https://himalayas.app/companies/signal-labs/jobs/data-scientist"
    assert first["location"] == "Worldwide"
    assert first["published_date"] == "2026-11-01T08:00:00Z"
    assert first["tags"] == ["Data Science", "Python", "AI"]
    assert first["salary"] == "USD 115000 - 145000"
    assert first["description"] == "Analyze product metrics and train forecasting models."

    assert postings[1]["location"] == "Canada, United States"
    assert postings[1]["salary"] == ""


def test_parse_jobicy():
    postings = parse_jobicy(read_fixture("jobicy.json"))
    assert_posting_shape(postings, "jobicy")
    assert len(postings) == 2

    first = postings[0]
    assert first["title"] == "Data Engineer"
    assert first["company"] == "StreamWorks"
    assert first["url"] == "https://jobicy.com/jobs/4001-data-engineer"
    assert first["location"] == "Anywhere"
    assert first["published_date"] == "2026-11-02 07:30:00"
    assert first["tags"] == ["Data Science", "Engineering"]
    assert first["salary"] == "USD 110000 - 140000"
    assert first["description"] == "Build ETL jobs and warehouse tables in Python and SQL."

    assert postings[1]["salary"] == ""


@pytest.mark.parametrize(
    "industry, expected_tags",
    [
        (" Data Science ", ["Data Science"]),
        ([" Data Science ", "Engineering", " "], ["Data Science", "Engineering"]),
        ("", []),
        ("   ", []),
        ([], []),
        (None, []),
    ],
)
def test_parse_jobicy_normalizes_string_and_list_tags(industry, expected_tags):
    postings = parse_jobicy({
        "jobs": [{"jobTitle": "Data Engineer", "jobIndustry": industry}]
    })

    assert len(postings) == 1
    assert postings[0]["tags"] == expected_tags


@pytest.mark.parametrize(
    "parser, item, expected_title",
    [
        (parse_remotive, {"title": "Backend Engineer", "url": "u"}, "Backend Engineer"),
        (parse_himalayas, {"title": "Data Scientist"}, "Data Scientist"),
        (parse_jobicy, {"jobTitle": "Data Engineer"}, "Data Engineer"),
    ],
    ids=["remotive", "himalayas", "jobicy"],
)
@pytest.mark.parametrize("bad_entry", [None, "text", 42, ["nested"]])
def test_parsers_skip_non_object_job_entries(parser, item, expected_title, bad_entry):
    postings = parser({"jobs": [bad_entry, item]})

    assert len(postings) == 1
    assert postings[0]["title"] == expected_title


@pytest.mark.parametrize(
    "parser, title_field, item, expected_title",
    [
        (parse_remotive, "title", {"title": "Backend Engineer"}, "Backend Engineer"),
        (parse_himalayas, "title", {"title": "Data Scientist"}, "Data Scientist"),
        (parse_jobicy, "jobTitle", {"jobTitle": "Data Engineer"}, "Data Engineer"),
    ],
    ids=["remotive", "himalayas", "jobicy"],
)
@pytest.mark.parametrize("bad_title", [None, "", "   ", "\t\n"])
def test_json_parsers_skip_blank_titles(parser, title_field, item, expected_title, bad_title):
    postings = parser({"jobs": [{title_field: bad_title}, item]})

    assert len(postings) == 1
    assert postings[0]["title"] == expected_title


@pytest.mark.parametrize(
    "parser, item, expected_title",
    [
        (parse_remotive, {"title": "Backend Engineer"}, "Backend Engineer"),
        (parse_himalayas, {"title": "Data Scientist"}, "Data Scientist"),
        (parse_jobicy, {"jobTitle": "Data Engineer"}, "Data Engineer"),
    ],
    ids=["remotive", "himalayas", "jobicy"],
)
def test_json_parsers_skip_records_missing_titles(parser, item, expected_title):
    postings = parser({"jobs": [{}, item]})

    assert len(postings) == 1
    assert postings[0]["title"] == expected_title


@pytest.mark.parametrize("bad_title", [None, "", "   ", "\t\n"])
def test_parse_remoteok_skips_blank_titles(bad_title):
    postings = parse_remoteok([{"title": bad_title}, {"position": "ML Engineer"}])

    assert len(postings) == 1
    assert postings[0]["title"] == "ML Engineer"


@pytest.mark.parametrize("bad_entry", [None, "text", 42, ["nested"], {"legal": "notice"}])
def test_parse_remoteok_skips_bad_or_metadata_entries(bad_entry):
    postings = parse_remoteok([bad_entry, {"position": "ML Engineer"}])

    assert len(postings) == 1
    assert postings[0]["title"] == "ML Engineer"


@pytest.mark.parametrize("parser", [parse_remotive, parse_himalayas, parse_jobicy])
@pytest.mark.parametrize(
    "payload",
    [
        None,
        "null",
        "[]",
        "42",
        '"text"',
        '{"jobs": null}',
        '{"jobs": 42}',
        '{"jobs": {"title": "Not a list"}}',
        "{}",
    ],
)
def test_json_job_parsers_reject_wrong_envelopes(parser, payload):
    with pytest.raises(ValueError):
        parser(payload)


@pytest.mark.parametrize("parser", [parse_remotive, parse_himalayas, parse_jobicy])
@pytest.mark.parametrize("payload", ['{"jobs": []}', {"jobs": []}])
def test_json_job_parsers_allow_valid_empty_feeds(parser, payload):
    assert parser(payload) == []


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "null",
        "{}",
        '{"jobs": []}',
        "42",
        '"text"',
    ],
)
def test_parse_remoteok_rejects_wrong_envelopes(payload):
    with pytest.raises(ValueError):
        parse_remoteok(payload)


@pytest.mark.parametrize("payload", ["[]", [], '[{"legal": "Remote OK API"}]'])
def test_parse_remoteok_allows_valid_empty_feeds(payload):
    assert parse_remoteok(payload) == []


def test_parse_weworkremotely():
    postings = parse_weworkremotely(read_fixture("weworkremotely.xml"))
    assert_posting_shape(postings, "weworkremotely")
    assert len(postings) == 2

    first = postings[0]
    assert first["title"] == "AI Engineer"
    assert first["company"] == "Vector Metrics"
    assert first["url"] == "https://weworkremotely.com/remote-jobs/vector-metrics-ai-engineer"
    assert first["location"] == "Anywhere in the World"
    assert first["published_date"] == "Mon, 02 Nov 2026 10:00:00 +0000"
    assert first["tags"] == ["Back-End Programming", "Machine Learning"]
    assert first["salary"] == ""
    assert first["description"] == "Work on LLM tooling and Python backend APIs."


def test_parse_weworkremotely_skips_items_without_usable_titles():
    raw_xml = (
        '<rss version="2.0"><channel>'
        "<item><link>https://example.com/no-title</link></item>"
        "<item><title></title><link>https://example.com/empty</link></item>"
        "<item><title>   </title><link>https://example.com/blank</link></item>"
        "<item><title>Acme: </title><link>https://example.com/company-only</link></item>"
        "<item><title>Acme: ML Engineer</title>"
        "<link>https://example.com/ml-engineer</link></item>"
        "</channel></rss>"
    )

    postings = parse_weworkremotely(raw_xml)

    assert len(postings) == 1
    assert postings[0]["title"] == "ML Engineer"
    assert postings[0]["company"] == "Acme"
    assert postings[0]["url"] == "https://example.com/ml-engineer"


@pytest.mark.parametrize(
    "raw_xml",
    [
        "<html><body>Service Unavailable</body></html>",
        '<rss version="2.0"></rss>',
        "<feed><channel></channel></feed>",
    ],
)
def test_parse_weworkremotely_rejects_wrong_envelopes(raw_xml):
    with pytest.raises(ValueError):
        parse_weworkremotely(raw_xml)


def test_parse_weworkremotely_allows_valid_empty_feed():
    raw_xml = '<rss version="2.0"><channel><title>We Work Remotely</title></channel></rss>'
    assert parse_weworkremotely(raw_xml) == []
