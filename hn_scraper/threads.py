import json
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ALGOLIA_API = "https://hn.algolia.com/api/v1"
USER_AGENT = "hn-scraper/1.0"
THREAD_TITLE = "Ask HN: Who wants to be hired?"


def fetch_url(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def month_range(month):
    start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return int(start.timestamp()), int(end.timestamp())


def fetch_monthly_threads(month):
    start, end = month_range(month)
    query = urlencode(
        {
            "query": "Who wants to be hired?",
            "tags": "story,author_whoishiring",
            "numericFilters": f"created_at_i>={start},created_at_i<{end}",
            "hitsPerPage": 20,
        }
    )
    return fetch_url(f"{ALGOLIA_API}/search_by_date?{query}")


def parse_monthly_threads(raw_data, month=None):
    payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    threads = []
    for hit in payload.get("hits", []):
        if hit.get("author") != "whoishiring":
            continue
        title = (hit.get("title") or "").strip()
        if THREAD_TITLE not in title:
            continue
        created_at = hit.get("created_at") or ""
        if month is not None and created_at[:7] != month:
            continue
        thread_id = str(hit.get("objectID") or "")
        if not thread_id:
            continue
        threads.append(
            {
                "thread_id": thread_id,
                "title": title,
                "url": f"https://news.ycombinator.com/item?id={thread_id}",
                "thread_month": created_at[:7],
                "created_at": created_at,
            }
        )
    return threads


def fetch_top_level_comments(month):
    found = parse_monthly_threads(fetch_monthly_threads(month), month=month)
    if not found:
        return []
    return parse_top_level_comments(fetch_thread(found[0]["thread_id"]))


def fetch_thread(thread_id):
    return fetch_url(f"{ALGOLIA_API}/items/{thread_id}")


def parse_top_level_comments(raw_data):
    payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    thread_id = str(payload.get("id") or "")
    comments = []
    for child in payload.get("children", []):
        # Replies live under a comment, so only direct children are read here.
        # Deleted comments come back with no author or no text.
        if child.get("type") not in (None, "comment"):
            continue
        if not child.get("author") or not child.get("text"):
            continue
        comment_id = str(child.get("id") or "")
        if not comment_id:
            continue
        comments.append(
            {
                "comment_id": comment_id,
                "thread_id": thread_id,
                "username": child["author"],
                "text": child["text"],
                "url": f"https://news.ycombinator.com/item?id={comment_id}",
                "posted_time": child.get("created_at") or "",
            }
        )
    return comments
