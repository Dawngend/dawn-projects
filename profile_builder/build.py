import argparse
import json
from pathlib import Path


def build_readme(profile):
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

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    args = parser.parse_args()

    with open(args.profile, encoding="utf-8") as json_file:
        profile = json.load(json_file)

    Path("README.md").write_text(build_readme(profile), encoding="utf-8")


if __name__ == "__main__":
    main()
