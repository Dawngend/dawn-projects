"""Aggregate counts for the salary fields of saved Remote OK and We Work
Remotely responses. Only counts leave these functions, never salary text."""


def is_blank(value):
    # Only None and empty or whitespace-only text are blank. Numeric 0 and
    # the text "0" are real values, so they count as nonblank.
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def summarize_remoteok_salary(records):
    summary = {
        "records": len(records),
        "salary_present": 0,
        "salary_nonblank": 0,
        "salary_min_present": 0,
        "salary_min_nonblank": 0,
        "salary_max_present": 0,
        "salary_max_nonblank": 0,
    }
    for record in records:
        for field in ("salary", "salary_min", "salary_max"):
            if field not in record:
                continue
            summary[f"{field}_present"] += 1
            if not is_blank(record[field]):
                summary[f"{field}_nonblank"] += 1
    return summary


def summarize_weworkremotely_salary(items):
    summary = {"items": len(items), "salary_present": 0, "salary_nonblank": 0}
    for item in items:
        salary = item.find("salary")
        if salary is None:
            continue
        summary["salary_present"] += 1
        if not is_blank(salary.text):
            summary["salary_nonblank"] += 1
    return summary
