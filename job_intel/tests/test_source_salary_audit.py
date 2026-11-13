from pathlib import Path
import sys
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from source_salary_audit import (
    summarize_remoteok_salary,
    summarize_weworkremotely_salary,
)

REMOTEOK_RECORDS = [
    {"position": "Data Analyst", "salary": "USD 70000 - 90000"},
    {"position": "BI Analyst", "salary": "", "salary_min": 60000, "salary_max": 80000},
    {"position": "Data Engineer", "salary": "   ", "salary_min": "", "salary_max": None},
    {"position": "ML Engineer"},
    {"position": "Backend Engineer", "salary_min": 0, "salary_max": ""},
]

WWR_ITEMS_XML = """
<rss>
  <channel>
    <item><title>Beta: Data Analyst</title><salary>USD 70000 - 90000</salary></item>
    <item><title>Beta: BI Analyst</title><salary></salary></item>
    <item><title>Beta: Data Engineer</title><salary>   </salary></item>
    <item><title>Beta: ML Engineer</title></item>
  </channel>
</rss>
"""


def wwr_items():
    root = ElementTree.fromstring(WWR_ITEMS_XML)
    return root.findall("./channel/item")


def test_remoteok_records_without_salary_fields_are_counted_only_as_records():
    summary = summarize_remoteok_salary([{"position": "ML Engineer"}])

    assert summary == {
        "records": 1,
        "salary_present": 0,
        "salary_nonblank": 0,
        "salary_min_present": 0,
        "salary_min_nonblank": 0,
        "salary_max_present": 0,
        "salary_max_nonblank": 0,
    }


def test_remoteok_blank_salary_fields_are_present_but_not_nonblank():
    summary = summarize_remoteok_salary(
        [{"position": "Data Engineer", "salary": "   ", "salary_min": "", "salary_max": None}]
    )

    assert summary == {
        "records": 1,
        "salary_present": 1,
        "salary_nonblank": 0,
        "salary_min_present": 1,
        "salary_min_nonblank": 0,
        "salary_max_present": 1,
        "salary_max_nonblank": 0,
    }


def test_remoteok_populated_fields_are_present_and_nonblank():
    summary = summarize_remoteok_salary(
        [{"position": "Data Analyst", "salary": "USD 70000 - 90000", "salary_min": 70000, "salary_max": 90000}]
    )

    assert summary == {
        "records": 1,
        "salary_present": 1,
        "salary_nonblank": 1,
        "salary_min_present": 1,
        "salary_min_nonblank": 1,
        "salary_max_present": 1,
        "salary_max_nonblank": 1,
    }


def test_remoteok_numeric_zero_and_text_zero_are_nonblank():
    summary = summarize_remoteok_salary(
        [{"position": "Unpaid Intern", "salary": "0", "salary_min": 0, "salary_max": "0"}]
    )

    assert summary == {
        "records": 1,
        "salary_present": 1,
        "salary_nonblank": 1,
        "salary_min_present": 1,
        "salary_min_nonblank": 1,
        "salary_max_present": 1,
        "salary_max_nonblank": 1,
    }


def test_remoteok_none_stays_blank_even_next_to_zero():
    summary = summarize_remoteok_salary(
        [{"position": "Mixed", "salary_min": None, "salary_max": 0}]
    )

    assert summary == {
        "records": 1,
        "salary_present": 0,
        "salary_nonblank": 0,
        "salary_min_present": 1,
        "salary_min_nonblank": 0,
        "salary_max_present": 1,
        "salary_max_nonblank": 1,
    }


def test_remoteok_mixed_records_add_up():
    summary = summarize_remoteok_salary(REMOTEOK_RECORDS)

    # salary_min of record 5 is numeric 0, which counts as nonblank.
    assert summary == {
        "records": 5,
        "salary_present": 3,
        "salary_nonblank": 1,
        "salary_min_present": 3,
        "salary_min_nonblank": 2,
        "salary_max_present": 3,
        "salary_max_nonblank": 1,
    }


def test_remoteok_summary_holds_no_salary_text():
    summary = summarize_remoteok_salary(REMOTEOK_RECORDS)

    assert all(isinstance(value, int) for value in summary.values())
    text = " ".join(str(value) for value in summary.values())
    assert "USD" not in text
    assert "70000" not in text
    assert "90000" not in text


def test_weworkremotely_missing_salary_element_is_not_present():
    item = ElementTree.fromstring("<item><title>Beta: ML Engineer</title></item>")

    assert summarize_weworkremotely_salary([item]) == {
        "items": 1,
        "salary_present": 0,
        "salary_nonblank": 0,
    }


def test_weworkremotely_blank_salary_element_is_present_but_not_nonblank():
    items = [
        ElementTree.fromstring("<item><salary></salary></item>"),
        ElementTree.fromstring("<item><salary>   </salary></item>"),
    ]

    assert summarize_weworkremotely_salary(items) == {
        "items": 2,
        "salary_present": 2,
        "salary_nonblank": 0,
    }


def test_weworkremotely_populated_salary_element_is_nonblank():
    item = ElementTree.fromstring("<item><salary>USD 70000 - 90000</salary></item>")

    assert summarize_weworkremotely_salary([item]) == {
        "items": 1,
        "salary_present": 1,
        "salary_nonblank": 1,
    }


def test_weworkremotely_mixed_items_add_up_and_hold_no_salary_text():
    summary = summarize_weworkremotely_salary(wwr_items())

    assert summary == {"items": 4, "salary_present": 3, "salary_nonblank": 1}
    assert all(isinstance(value, int) for value in summary.values())
    text = " ".join(str(value) for value in summary.values())
    assert "USD" not in text
    assert "70000" not in text


def test_weworkremotely_zero_salary_text_is_nonblank():
    item = ElementTree.fromstring("<item><salary>0</salary></item>")

    assert summarize_weworkremotely_salary([item]) == {
        "items": 1,
        "salary_present": 1,
        "salary_nonblank": 1,
    }


def test_weworkremotely_feed_with_no_items_counts_nothing():
    root = ElementTree.fromstring("<rss><channel></channel></rss>")

    assert summarize_weworkremotely_salary(root.findall("./channel/item")) == {
        "items": 0,
        "salary_present": 0,
        "salary_nonblank": 0,
    }
