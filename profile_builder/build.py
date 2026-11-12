import argparse
from http.client import HTTPException
import json
from pathlib import Path
from urllib.error import URLError

from github_repos import fetch_public_repos


def format_cell(value):
    return (
        str(value or "")
        .replace("|", "\\|")
        .replace("\r\n", " ")
        .replace("\r", " ")
        .replace("\n", " ")
    )


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

    output_path = Path("README.md")
    guide_path = Path(__file__).resolve().with_name("README.md")
    if output_path.resolve() == guide_path.resolve():
        parser.error(
            "Refusing to overwrite the Profile Builder guide (README.md). "
            "Run from a separate output folder."
        )

    with open(args.profile, encoding="utf-8") as json_file:
        profile = json.load(json_file)

    github_projects = None
    github_username = profile.get("github_username")
    if github_username:
        try:
            github_projects = fetch_public_repos(github_username)
        except (URLError, OSError, HTTPException, ValueError):
            parser.exit(
                1,
                "error: Unable to fetch GitHub repositories. "
                "Check github_username and your connection, or try again later.\n",
            )

    output_path.write_text(
        build_readme(profile, github_projects), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
