import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
