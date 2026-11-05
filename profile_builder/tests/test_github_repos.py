import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import github_repos


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_public_repos_uses_user_endpoint_and_sorts_by_last_push(monkeypatch):
    repos = [
        {"name": "old", "pushed_at": "2024-01-01T00:00:00Z"},
        {"name": "newest", "pushed_at": "2025-05-05T00:00:00Z"},
        {"name": "middle", "pushed_at": "2024-06-01T00:00:00Z"},
    ]
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["user_agent"] = request.get_header("User-agent")
        captured["accept"] = request.get_header("Accept")
        captured["timeout"] = timeout
        return FakeResponse(json.dumps(repos).encode("utf-8"))

    monkeypatch.setattr(github_repos, "urlopen", fake_urlopen)

    result = github_repos.fetch_public_repos("test-user")

    assert [repo["name"] for repo in result] == ["newest", "middle", "old"]
    assert captured == {
        "url": "https://api.github.com/users/test-user/repos",
        "user_agent": github_repos.USER_AGENT,
        "accept": "application/vnd.github+json",
        "timeout": 30,
    }


def test_sort_by_last_push_puts_repos_without_a_push_date_last():
    repos = [
        {"name": "no-date"},
        {"name": "dated", "pushed_at": "2024-01-01T00:00:00Z"},
    ]

    result = github_repos.sort_by_last_push(repos)

    assert [repo["name"] for repo in result] == ["dated", "no-date"]
