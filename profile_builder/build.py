import argparse
import json
from pathlib import Path

from github_repos import fetch_public_repos


def format_cell(value):
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def build_github_table(repos):
    lines = [
        "| Project | Description | Language | Stars | Last Push |",
        "| --- | --- | --- | --- | --- |",
    ]
    for repo in repos:
        pushed_at = repo.get("pushed_at") or ""
        lines.append(
            "| [{}]({}) | {} | {} | {} | {} |".format(
                format_cell(repo.get("name")),
                repo.get("html_url") or "",
                format_cell(repo.get("description")),
                format_cell(repo.get("language")),
                repo.get("stargazers_count") or 0,
                pushed_at[:10],
            )
        )
    return lines


def build_readme(profile, github_projects=None):
    if github_projects is None:
        github_projects = profile.get("github_projects")

    lines = [f"# Hi, I'm {profile['name']}"]

    if profile.get("bio"):
        lines += ["", profile["bio"]]

    if profile.get("links"):
        lines += ["", "## Links", ""]
        for label, url in profile["links"].items():
            lines.append(f"- [{label}]({url})")

    if profile.get("skills"):
        lines += ["", "## Skills", "", ", ".join(profile["skills"])]

    if profile.get("projects"):
        lines += ["", "## Featured Projects", ""]
        for project in profile["projects"]:
            lines.append(f"- [{project['name']}]({project['url']}): {project['description']}")

    if github_projects:
        lines += ["", "## GitHub Projects", ""]
        lines += build_github_table(github_projects)

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    args = parser.parse_args()

    with open(args.profile, encoding="utf-8") as json_file:
        profile = json.load(json_file)

    github_projects = None
    github_username = profile.get("github_username")
    if github_username:
        github_projects = fetch_public_repos(github_username)

    Path("README.md").write_text(
        build_readme(profile, github_projects), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
