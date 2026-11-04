from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
