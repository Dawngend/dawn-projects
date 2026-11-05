import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build
from build import build_readme

PROJECT_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def read_text(path):
    with open(path, encoding="utf-8") as text_file:
        return text_file.read()


def test_sample_profile_matches_expected_readme():
    with open(PROJECT_DIR / "profile.json", encoding="utf-8") as json_file:
        profile = json.load(json_file)

    assert build_readme(profile) == read_text(FIXTURES_DIR / "expected_readme.md")


def test_small_profile_matches_expected_text():
    profile = {
        "name": "Test Name",
        "bio": "One line bio.",
        "links": {"GitHub": "https://github.com/test-name"},
        "skills": ["Python"],
        "projects": [
            {
                "name": "demo",
                "url": "https://github.com/test-name/demo",
                "description": "A demo project.",
            }
        ],
    }

    assert build_readme(profile) == (
        "# Hi, I'm Test Name\n"
        "\n"
        "One line bio.\n"
        "\n"
        "## Links\n"
        "\n"
        "- [GitHub](https://github.com/test-name)\n"
        "\n"
        "## Skills\n"
        "\n"
        "Python\n"
        "\n"
        "## Featured Projects\n"
        "\n"
        "- [demo](https://github.com/test-name/demo): A demo project.\n"
    )


@pytest.mark.parametrize(
    "optional_fields",
    [
        {},
        {
            "bio": "",
            "links": {},
            "skills": [],
            "projects": [],
            "github_projects": [],
        },
        {
            "bio": None,
            "links": None,
            "skills": None,
            "projects": None,
            "github_projects": None,
        },
    ],
)
def test_missing_or_empty_optional_sections_are_omitted(optional_fields):
    profile = {"name": "Test Name", **optional_fields}

    assert build_readme(profile) == "# Hi, I'm Test Name\n"


def test_only_populated_sections_are_included():
    profile = {"name": "Test Name", "skills": ["Python"]}

    assert build_readme(profile) == (
        "# Hi, I'm Test Name\n"
        "\n"
        "## Skills\n"
        "\n"
        "Python\n"
    )


def test_github_projects_are_rendered_as_a_table():
    repo = {
        "name": "demo",
        "html_url": "https://github.com/test-name/demo",
        "description": "A demo | project.",
        "language": "Python",
        "stargazers_count": 3,
        "pushed_at": "2025-02-03T04:05:06Z",
    }
    profile = {"name": "Test Name", "github_projects": [repo]}

    assert build_readme(profile) == (
        "# Hi, I'm Test Name\n"
        "\n"
        "## GitHub Projects\n"
        "\n"
        "| Project | Description | Language | Stars | Last Push |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| [demo](https://github.com/test-name/demo) | A demo \\| project. | Python | 3 | 2025-02-03 |\n"
    )


def test_command_writes_sample_readme(tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_text = read_text(PROJECT_DIR / "profile.json")
    profile_path.write_text(profile_text, encoding="utf-8")

    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "build.py"), "profile.json"],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        check=True,
        capture_output=True,
        text=True,
    )

    assert read_text(tmp_path / "README.md") == read_text(
        FIXTURES_DIR / "expected_readme.md"
    )
    assert read_text(profile_path) == profile_text


def test_command_writes_utf8_without_optional_sections(tmp_path):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({"name": "Jos\u00e9"}, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("Old content\n", encoding="utf-8")

    subprocess.run(
        [sys.executable, str(PROJECT_DIR / "build.py"), "profile.json"],
        cwd=tmp_path,
        stdin=subprocess.DEVNULL,
        check=True,
        capture_output=True,
        text=True,
    )

    assert read_text(tmp_path / "README.md") == "# Hi, I'm Jos\u00e9\n"


def test_command_fetches_github_projects_when_username_is_set(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({"name": "Test Name", "github_username": "test-name"}),
        encoding="utf-8",
    )
    repo = {
        "name": "demo",
        "html_url": "https://github.com/test-name/demo",
        "description": "A demo project.",
        "language": "Python",
        "stargazers_count": 3,
        "pushed_at": "2025-02-03T04:05:06Z",
    }
    requested = []

    def fake_fetch_public_repos(username):
        requested.append(username)
        return [repo]

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build.py", "profile.json"])
    monkeypatch.setattr(build, "fetch_public_repos", fake_fetch_public_repos)

    build.main()

    assert requested == ["test-name"]
    assert read_text(tmp_path / "README.md") == (
        "# Hi, I'm Test Name\n"
        "\n"
        "## GitHub Projects\n"
        "\n"
        "| Project | Description | Language | Stars | Last Push |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| [demo](https://github.com/test-name/demo) | A demo project. | Python | 3 | 2025-02-03 |\n"
    )
