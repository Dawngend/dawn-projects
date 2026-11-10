from http.client import IncompleteRead
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build
import github_repos
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


@pytest.mark.parametrize("working_folder", [".", "output"])
def test_command_protects_its_guide(tmp_path, working_folder):
    for filename in ["build.py", "github_repos.py"]:
        shutil.copyfile(PROJECT_DIR / filename, tmp_path / filename)
    guide_path = tmp_path / "README.md"
    guide_bytes = b"# Project guide\r\nDo not replace.\r\n"
    guide_path.write_bytes(guide_bytes)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps({"name": "Test Name"}), encoding="utf-8")
    working_dir = tmp_path / working_folder
    working_dir.mkdir(exist_ok=True)

    result = subprocess.run(
        [sys.executable, str(tmp_path / "build.py"), str(profile_path)],
        cwd=working_dir,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )

    assert guide_path.read_bytes() == guide_bytes
    if working_folder == ".":
        assert result.returncode == 2
        assert "Refusing to overwrite the Profile Builder guide (README.md)." in result.stderr
        assert "Run from a separate output folder." in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert read_text(working_dir / "README.md") == "# Hi, I'm Test Name\n"


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


@pytest.mark.parametrize(
    "fetch_error",
    [
        HTTPError("https://api.github.com/users/test-name/repos", 404, "Not Found", {}, None),
        URLError("Connection unavailable"),
        TimeoutError("Request timed out"),
        json.JSONDecodeError("Invalid response", "", 0),
        IncompleteRead(b"[", 2),
        b'["\xff"]',
        b'{"message": "API rate limit exceeded"}',
        b'["not a repo"]',
        b'[{"name": "ok", "pushed_at": "2025-01-01T00:00:00Z"}, null]',
    ],
    ids=[
        "http",
        "connection",
        "timeout",
        "invalid-json",
        "truncated-http",
        "invalid-utf8",
        "json-object",
        "list-of-strings",
        "list-with-null",
    ],
)
@pytest.mark.parametrize("existing_output", [False, True])
def test_failed_fetch_leaves_output_untouched(
    tmp_path, monkeypatch, capsys, fetch_error, existing_output
):
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({"name": "Test Name", "github_username": "test-name"}),
        encoding="utf-8",
    )
    output_path = tmp_path / "README.md"
    original_output = b"# Existing README\r\nKeep this content.\r\n"
    if existing_output:
        output_path.write_bytes(original_output)

    class TruncatedResponse(BytesIO):
        def read(self):
            raise fetch_error

    def fake_urlopen(request, timeout):
        if isinstance(fetch_error, IncompleteRead):
            return TruncatedResponse()
        if isinstance(fetch_error, bytes):
            return BytesIO(fetch_error)
        raise fetch_error

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["build.py", "profile.json"])
    monkeypatch.setattr(github_repos, "urlopen", fake_urlopen)

    with pytest.raises(SystemExit) as error:
        build.main()

    assert error.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "error: Unable to fetch GitHub repositories. "
        "Check github_username and your connection, or try again later.\n"
    )
    if existing_output:
        assert output_path.read_bytes() == original_output
    else:
        assert not output_path.exists()


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
