from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eligibility import is_eligible, location_is_open, title_matches


def test_title_keywords_match():
    for title in [
        "AI Engineer",
        "ML Researcher",
        "Machine Learning Engineer",
        "Data Scientist",
        "Data Engineer",
        "Data Analyst",
        "Backend Developer",
        "Python Developer",
        "senior data scientist, remote",
    ]:
        assert title_matches(title) is True


def test_other_titles_do_not_match():
    for title in [
        "Product Designer",
        "Content Writer",
        "Customer Support Specialist",
        "Training Coordinator",
        "Email Marketing Manager",
        "Sales Executive",
    ]:
        assert title_matches(title) is False


def test_blank_title_does_not_match():
    assert title_matches("") is False
    assert title_matches(None) is False


def test_open_locations_are_kept():
    for location in [
        "Worldwide",
        "Anywhere",
        "Anywhere in the World",
        "Remote",
        "Remote - Global",
        "",
    ]:
        assert location_is_open(location) is True


def test_country_locations_are_skipped():
    for location in [
        "USA Only",
        "US",
        "United States",
        "UK Only",
        "Canada",
        "Canada, United States",
        "Germany",
        "Japan",
        "Kenya",
        "Chile",
        "Europe",
        "Asia-Pacific",
        "Scandinavia",
        "EMEA",
        "Remote - US Only",
        "Anywhere in the US",
        "Worldwide except India",
    ]:
        assert location_is_open(location) is False


def test_dotted_country_abbreviations_are_skipped():
    for location in [
        "U.S. Only",
        "U.S.",
        "U.S.A.",
        "Remote - U.S.",
        "Anywhere in the U.S.",
        "U.K. Only",
        "u.k.",
    ]:
        assert location_is_open(location) is False


def test_open_locations_with_periods_are_kept():
    for location in [
        "Anywhere.",
        "Worldwide. Async team.",
        "Remote (incl. contractors)",
    ]:
        assert location_is_open(location) is True


def test_dotted_us_location_is_not_eligible():
    assert is_eligible({"title": "Data Scientist", "location": "U.S. Only"}) is False


def test_is_eligible_needs_both():
    assert is_eligible({"title": "Data Scientist", "location": "Worldwide"}) is True
    assert is_eligible({"title": "Data Scientist", "location": "USA Only"}) is False
    assert is_eligible({"title": "Bookkeeper", "location": "Worldwide"}) is False
    assert is_eligible({"title": "Bookkeeper", "location": "USA Only"}) is False
