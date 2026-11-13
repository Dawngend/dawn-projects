from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math


def normalize_title(value):
    if not isinstance(value, str):
        return ""
    return value.strip()


def normalize_salary(value):
    if not isinstance(value, str):
        return ""
    return value.strip()


def normalize_salary_range(minimum, maximum):
    bounds = []
    for value in (minimum, maximum):
        if value is not None:
            # bool is a kind of int in Python, so it is rejected by name.
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return None
            try:
                value = float(value)
            except OverflowError:
                return None
            if not math.isfinite(value) or value < 0:
                return None
        bounds.append(value)

    minimum, maximum = bounds
    if minimum is not None and maximum is not None and minimum > maximum:
        return None
    return (minimum, maximum)


def normalize_currency(value):
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) == 3 and text.isascii() and text.isalpha():
        return text.upper()
    return ""


SALARY_PERIODS = {
    "hour": "hour",
    "hourly": "hour",
    "hr": "hour",
    "hrs": "hour",
    "day": "day",
    "daily": "day",
    "week": "week",
    "weekly": "week",
    "wk": "week",
    "month": "month",
    "monthly": "month",
    "mo": "month",
    "year": "year",
    "yearly": "year",
    "yr": "year",
    "yrs": "year",
    "annual": "year",
    "annually": "year",
}


def normalize_salary_period(value):
    if not isinstance(value, str):
        return ""
    return SALARY_PERIODS.get(value.strip().lower(), "")


def normalize_published_date(value):
    text = "" if value is None else str(value).strip()
    if not text:
        return ""

    moment = None
    for parse in (datetime.fromisoformat, parsedate_to_datetime):
        try:
            moment = parse(text)
            break
        except (TypeError, ValueError):
            continue

    if moment is None:
        # Only 9- or 10-digit numbers are read as Unix epoch seconds.
        if not (text.isdecimal() and 9 <= len(text) <= 10):
            return ""
        try:
            return datetime.fromtimestamp(int(text), tz=timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return ""

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()
