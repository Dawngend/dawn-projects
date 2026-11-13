from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contracts import (
    normalize_currency,
    normalize_published_date,
    normalize_salary,
    normalize_salary_period,
    normalize_salary_range,
    normalize_title,
)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("USD", "USD"),
        ("eur", "EUR"),
        ("gBp", "GBP"),
        ("  cad  ", "CAD"),
        ("\tphp\n", "PHP"),
        ("zzz", "ZZZ"),
    ],
)
def test_three_ascii_letter_currencies_are_returned_uppercase(value, expected):
    assert normalize_currency(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "\n\t",
        "US",
        "USDT",
        "$",
        "$US",
        "US1",
        "123",
        "U S",
        "ÜSD",
        "€UR",
        "ＵＳＤ",
    ],
)
def test_invalid_currency_strings_return_an_empty_string(value):
    assert normalize_currency(value) == ""


@pytest.mark.parametrize(
    "value", [None, 123, 4.5, True, b"USD", ["USD"], {"currency": "USD"}]
)
def test_non_string_currencies_return_an_empty_string(value):
    assert normalize_currency(value) == ""


@pytest.mark.parametrize(
    "value, expected",
    [
        ("USD 100000 - 120000", "USD 100000 - 120000"),
        ("  USD 100000 - 120000  ", "USD 100000 - 120000"),
        ("\t€60k-80k\n", "€60k-80k"),
        ("$120,000/yr", "$120,000/yr"),
        ("USD 100000 -  120000", "USD 100000 -  120000"),
        ("DOE", "DOE"),
    ],
)
def test_non_blank_salaries_are_kept_except_outer_whitespace(value, expected):
    assert normalize_salary(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_blank_salaries_return_an_empty_string(value):
    assert normalize_salary(value) == ""


@pytest.mark.parametrize("value", [None, 100000, 4.5, True, ["USD 1"], {"min": 1}])
def test_non_string_salaries_return_an_empty_string(value):
    assert normalize_salary(value) == ""


@pytest.mark.parametrize(
    "minimum, maximum, expected",
    [
        (70000, 90000, (70000.0, 90000.0)),
        (25.5, 40.75, (25.5, 40.75)),
        (70000, 90000.5, (70000.0, 90000.5)),
        (80000, 80000, (80000.0, 80000.0)),
        (0, 0, (0.0, 0.0)),
        (0, 50000, (0.0, 50000.0)),
    ],
)
def test_valid_salary_bounds_are_returned_as_floats(minimum, maximum, expected):
    result = normalize_salary_range(minimum, maximum)

    assert result == expected
    assert isinstance(result, tuple)
    assert [type(bound) for bound in result] == [float, float]


@pytest.mark.parametrize(
    "minimum, maximum, expected",
    [
        (70000, None, (70000.0, None)),
        (None, 90000, (None, 90000.0)),
        (None, None, (None, None)),
    ],
)
def test_missing_salary_bounds_are_kept_as_none(minimum, maximum, expected):
    assert normalize_salary_range(minimum, maximum) == expected


@pytest.mark.parametrize(
    "minimum, maximum",
    [
        (90000, 70000),
        (0.01, 0),
        (-1, 90000),
        (70000, -1),
        (-0.5, None),
        (None, -90000),
    ],
)
def test_negative_or_reversed_salary_bounds_are_rejected(minimum, maximum):
    assert normalize_salary_range(minimum, maximum) is None


@pytest.mark.parametrize(
    "minimum, maximum",
    [
        (float("nan"), 90000),
        (70000, float("nan")),
        (float("inf"), None),
        (70000, float("inf")),
        (float("-inf"), 90000),
        (10**400, None),
    ],
)
def test_non_finite_salary_bounds_are_rejected(minimum, maximum):
    assert normalize_salary_range(minimum, maximum) is None


@pytest.mark.parametrize(
    "minimum, maximum",
    [
        (True, 90000),
        (70000, False),
        (True, True),
        ("70000", "90000"),
        ("70000", 90000),
        (70000, "90k"),
        ("", None),
        (None, "DOE"),
        ([70000], 90000),
        (70000, {"max": 90000}),
        (b"70000", None),
    ],
)
def test_boolean_or_non_numeric_salary_bounds_are_rejected(minimum, maximum):
    assert normalize_salary_range(minimum, maximum) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("hour", "hour"),
        ("Hourly", "hour"),
        ("HR", "hour"),
        (" hrs ", "hour"),
        ("day", "day"),
        ("Daily", "day"),
        ("week", "week"),
        ("  Weekly  ", "week"),
        ("wk", "week"),
        ("month", "month"),
        ("MONTHLY", "month"),
        ("mo", "month"),
        ("year", "year"),
        ("Yearly", "year"),
        ("yr", "year"),
        ("yrs", "year"),
        ("annual", "year"),
        ("Annually", "year"),
    ],
)
def test_common_period_labels_are_mapped_to_five_values(value, expected):
    assert normalize_salary_period(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "   ", "\n\t", "fortnight", "quarter", "sem", "per year", "yearss", "$"],
)
def test_unknown_periods_return_an_empty_string(value):
    assert normalize_salary_period(value) == ""


@pytest.mark.parametrize(
    "value", [None, 12, 4.5, True, ["year"], {"period": "year"}]
)
def test_non_string_periods_return_an_empty_string(value):
    assert normalize_salary_period(value) == ""


@pytest.mark.parametrize(
    "value, expected",
    [
        ("Data Analyst", "Data Analyst"),
        ("  Junior Data Scientist  ", "Junior Data Scientist"),
        ("\tML Engineer\n", "ML Engineer"),
        ("Senior  Data  Engineer", "Senior  Data  Engineer"),
    ],
)
def test_non_blank_titles_are_stripped(value, expected):
    assert normalize_title(value) == expected


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_blank_titles_return_an_empty_string(value):
    assert normalize_title(value) == ""


@pytest.mark.parametrize("value", [None, 123, 4.5, True, ["Data Analyst"], {"title": "x"}])
def test_non_string_titles_return_an_empty_string(value):
    assert normalize_title(value) == ""


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-11-03T08:00:00Z", "2026-11-03T08:00:00+00:00"),
        ("2026-11-04T08:55:14.891833+00:00", "2026-11-04T08:55:14.891833+00:00"),
        ("2026-11-03T08:00:00-05:00", "2026-11-03T13:00:00+00:00"),
        ("2026-11-03T08:00:00", "2026-11-03T08:00:00+00:00"),
        ("2026-11-03", "2026-11-03T00:00:00+00:00"),
    ],
)
def test_iso_values_are_returned_in_utc(value, expected):
    assert normalize_published_date(value) == expected


def test_epoch_seconds_become_a_utc_timestamp():
    assert normalize_published_date("1793772778") == "2026-11-04T06:12:58+00:00"
    assert normalize_published_date(1793772778) == "2026-11-04T06:12:58+00:00"


def test_eight_digit_date_is_a_calendar_date_not_epoch_seconds():
    # fromisoformat accepts YYYYMMDD before the epoch fallback runs.
    assert normalize_published_date("20261103") == "2026-11-03T00:00:00+00:00"


def test_space_separated_iso_timestamp_is_read_as_utc():
    assert (
        normalize_published_date("2026-11-03 08:00:00")
        == "2026-11-03T08:00:00+00:00"
    )


def test_rfc_2822_dates_are_returned_in_utc():
    assert (
        normalize_published_date("Wed, 21 Jun 2023 14:22:59 +0000")
        == "2023-06-21T14:22:59+00:00"
    )
    assert (
        normalize_published_date("Tue, 03 Nov 2026 19:09:15 +0100")
        == "2026-11-03T18:09:15+00:00"
    )


def test_rfc_2822_without_a_timezone_is_read_as_utc():
    assert (
        normalize_published_date("Tue, 03 Nov 2026 19:09:15")
        == "2026-11-03T19:09:15+00:00"
    )


def test_surrounding_whitespace_is_ignored():
    assert normalize_published_date("  2026-11-03T08:00:00Z  ") == (
        "2026-11-03T08:00:00+00:00"
    )


def test_normalizing_twice_gives_the_same_result():
    once = normalize_published_date("2026-11-03T08:00:00-05:00")
    assert normalize_published_date(once) == once


@pytest.mark.parametrize("value", [None, "", "   ", "\n"])
def test_blank_values_return_an_empty_string(value):
    assert normalize_published_date(value) == ""


@pytest.mark.parametrize(
    "value",
    [
        "not a date",
        "2026-13-45",
        "Tue, 32 Nov 2026 19:09:15 +0000",
        "12345",
        "123456789012",
    ],
)
def test_invalid_values_return_an_empty_string(value):
    assert normalize_published_date(value) == ""
