import json
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

USER_AGENT = "job-market-scraper/1.0"
REQUEST_DELAY_SECONDS = 1.0

REMOTEOK_URL = "https://remoteok.com/api"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
HIMALAYAS_URL = "https://himalayas.app/jobs/api"
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
WEWORKREMOTELY_URL = "https://weworkremotely.com/remote-jobs.rss"

POSTING_FIELDS = (
    "title",
    "company",
    "url",
    "source",
    "location",
    "published_date",
    "tags",
    "salary",
    "description",
)


def fetch_url(url, delay_seconds=REQUEST_DELAY_SECONDS):
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    finally:
        if delay_seconds > 0:
            time.sleep(delay_seconds)


def format_salary(min_value, max_value, currency=""):
    if not min_value and not max_value:
        return ""
    prefix = f"{currency} " if currency else ""
    if min_value and max_value:
        return f"{prefix}{min_value} - {max_value}"
    return f"{prefix}{min_value or max_value}"


def make_posting(
    title,
    company,
    url,
    source,
    location,
    published_date,
    tags,
    salary,
    description,
):
    if isinstance(tags, str):
        tags = [tags]
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "url": (url or "").strip(),
        "source": (source or "").strip(),
        "location": (location or "").strip(),
        "published_date": str(published_date or "").strip(),
        "tags": [str(tag).strip() for tag in (tags or []) if str(tag).strip()],
        "salary": str(salary or "").strip(),
        "description": (description or "").strip(),
    }


def has_title(title):
    return isinstance(title, str) and bool(title.strip())


def read_jobs(raw_data):
    payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object with a jobs list")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError("Expected JSON object with a jobs list")
    return jobs


def fetch_remoteok():
    return fetch_url(REMOTEOK_URL)


def parse_remoteok(raw_data):
    items = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    if not isinstance(items, list):
        raise ValueError("Expected JSON list of jobs")
    postings = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("position") or item.get("title")
        if not has_title(title):
            continue
        salary = item.get("salary") or format_salary(
            item.get("salary_min"), item.get("salary_max"), "USD"
        )
        postings.append(
            make_posting(
                title=title,
                company=item.get("company"),
                url=item.get("url") or item.get("apply_url"),
                source="remoteok",
                location=item.get("location"),
                published_date=item.get("date"),
                tags=item.get("tags"),
                salary=salary,
                description=item.get("description"),
            )
        )
    return postings


def fetch_remotive():
    return fetch_url(REMOTIVE_URL)


def parse_remotive(raw_data):
    postings = []
    for item in read_jobs(raw_data):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not has_title(title):
            continue
        postings.append(
            make_posting(
                title=title,
                company=item.get("company_name"),
                url=item.get("url"),
                source="remotive",
                location=item.get("candidate_required_location"),
                published_date=item.get("publication_date"),
                tags=item.get("tags"),
                salary=item.get("salary"),
                description=item.get("description"),
            )
        )
    return postings


def fetch_himalayas():
    return fetch_url(HIMALAYAS_URL)


def parse_himalayas(raw_data):
    postings = []
    for item in read_jobs(raw_data):
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not has_title(title):
            continue
        locations = item.get("locationRestrictions") or []
        location = ", ".join(locations) if isinstance(locations, list) else str(locations)
        salary = item.get("salary") or format_salary(
            item.get("minSalary"),
            item.get("maxSalary"),
            item.get("currency") or "USD",
        )
        postings.append(
            make_posting(
                title=title,
                company=item.get("companyName"),
                url=item.get("applicationLink") or item.get("guid"),
                source="himalayas",
                location=location,
                published_date=item.get("pubDate"),
                tags=item.get("categories"),
                salary=salary,
                description=item.get("description") or item.get("excerpt"),
            )
        )
    return postings


def fetch_jobicy():
    return fetch_url(JOBICY_URL)


def parse_jobicy(raw_data):
    postings = []
    for item in read_jobs(raw_data):
        if not isinstance(item, dict):
            continue
        title = item.get("jobTitle")
        if not has_title(title):
            continue
        salary = item.get("salary") or format_salary(
            item.get("annualSalaryMin"),
            item.get("annualSalaryMax"),
            item.get("salaryCurrency") or "USD",
        )
        postings.append(
            make_posting(
                title=title,
                company=item.get("companyName"),
                url=item.get("url"),
                source="jobicy",
                location=item.get("jobGeo"),
                published_date=item.get("pubDate"),
                tags=item.get("jobIndustry"),
                salary=salary,
                description=item.get("jobDescription") or item.get("jobExcerpt"),
            )
        )
    return postings


def fetch_weworkremotely():
    return fetch_url(WEWORKREMOTELY_URL)


def parse_weworkremotely(raw_xml):
    root = ET.fromstring(raw_xml)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Expected RSS root with a channel")
    postings = []
    for item in root.findall("./channel/item"):
        raw_title = item.findtext("title") or ""
        if ": " in raw_title:
            company, title = raw_title.split(": ", 1)
        else:
            company, title = "", raw_title
        if not has_title(title):
            continue
        tags = [elem.text for elem in item.findall("category") if elem.text]
        postings.append(
            make_posting(
                title=title,
                company=company,
                url=item.findtext("link"),
                source="weworkremotely",
                location=item.findtext("region"),
                published_date=item.findtext("pubDate"),
                tags=tags,
                salary=item.findtext("salary"),
                description=item.findtext("description"),
            )
        )
    return postings
