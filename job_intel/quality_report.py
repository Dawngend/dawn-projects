from pathlib import Path
import re

from contracts import (
    normalize_currency,
    normalize_published_date,
    normalize_salary,
    normalize_salary_period,
    normalize_salary_range,
    normalize_title,
)

# A plain base-10 amount: digits, optional comma thousands groups, optional
# decimals. float() alone would also accept "1e5", "1_000", "inf" and "nan".
AMOUNT_PATTERN = re.compile(r"([0-9]{1,3}(,[0-9]{3})+|[0-9]+)(\.[0-9]+)?")


def split_salary_text(salary):
    # The log stores salary as one text value. This split recognizes the
    # layout of the scraper's format_salary fallback, "<currency> <min> - <max>"
    # or "<currency> <value>". Some source parsers pass the upstream salary
    # text through unchanged, so other layouts can reach this function.
    # A pay period is only read after a "/", as in "USD 30 - 45 / hour".
    amounts_text, slash, period = salary.partition("/")
    parts = amounts_text.split()
    currency = parts[0] if parts else ""
    if not slash:
        period = None
    return currency, parts[1:], period


def read_amount(text):
    if not AMOUNT_PATTERN.fullmatch(text):
        return None
    return float(text.replace(",", ""))


def read_salary_range(amounts):
    if len(amounts) == 1:
        low, high = read_amount(amounts[0]), None
    elif len(amounts) == 3 and amounts[1] == "-":
        low, high = read_amount(amounts[0]), read_amount(amounts[2])
        if high is None:
            return None
    else:
        return None
    if low is None:
        return None
    return normalize_salary_range(low, high)


def build_run_quality_report(connection, source_run_id):
    run = connection.execute(
        """
        SELECT source, run_at, status, returned_count
        FROM source_runs
        WHERE id = ?
        """,
        (source_run_id,),
    ).fetchone()
    if run is None:
        raise ValueError(f"source run {source_run_id} was not found")
    source, run_at, status, returned_count = run

    rows = connection.execute(
        """
        SELECT title, published_date, salary
        FROM observations
        WHERE source_run_id = ?
        """,
        (source_run_id,),
    ).fetchall()

    invalid_titles = 0
    invalid_dates = 0
    blank_salaries = 0
    invalid_ranges = 0
    invalid_currencies = 0
    invalid_periods = 0
    for title, published_date, salary in rows:
        if not normalize_title(title):
            invalid_titles += 1
        # A blank date is missing, not invalid, so it is not counted here.
        if published_date.strip() and not normalize_published_date(published_date):
            invalid_dates += 1

        salary = normalize_salary(salary)
        if not salary:
            blank_salaries += 1
            continue
        currency, amounts, period = split_salary_text(salary)
        if read_salary_range(amounts) is None:
            invalid_ranges += 1
        if not normalize_currency(currency):
            invalid_currencies += 1
        # A salary with no "/" has no period, which is missing, not invalid.
        if period is not None and not normalize_salary_period(period):
            invalid_periods += 1

    if returned_count is None:
        returned_count = "not recorded"

    lines = [
        f"# Run Quality Report: Run {source_run_id}",
        "",
        f"- Source: {source}",
        f"- Run time: {run_at}",
        f"- Status: {status}",
        f"- Reported returned count: {returned_count}",
        f"- Observed rows: {len(rows)}",
        "",
        "## Contract Checks",
        "",
        f"- Blank or invalid titles: {invalid_titles}",
        f"- Nonblank invalid published dates: {invalid_dates}",
        f"- Blank salary text: {blank_salaries}",
        f"- Nonblank salary with invalid range: {invalid_ranges}",
        f"- Nonblank salary with invalid currency: {invalid_currencies}",
        f"- Nonblank salary with invalid period: {invalid_periods}",
    ]
    return "\n".join(lines) + "\n"


def write_run_quality_report(connection, source_run_id, output_dir):
    report = build_run_quality_report(connection, source_run_id)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"run_{source_run_id}.md"
    # newline="\n" stops Windows writing \r\n, so the file has the same bytes everywhere.
    report_path.write_text(report, encoding="utf-8", newline="\n")
    return report_path
