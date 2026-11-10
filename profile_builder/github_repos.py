import json
from urllib.request import Request, urlopen

USER_AGENT = "profile-builder/1.0"
REPOS_URL = "https://api.github.com/users/{username}/repos"


def fetch_public_repos(username):
    request = Request(
        REPOS_URL.format(username=username),
        headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urlopen(request, timeout=30) as response:
        repos = json.load(response)
    if not isinstance(repos, list) or not all(isinstance(repo, dict) for repo in repos):
        raise ValueError("GitHub response is not a list of repositories")
    return sort_by_last_push(repos)


def sort_by_last_push(repos):
    return sorted(repos, key=lambda repo: repo.get("pushed_at") or "", reverse=True)
