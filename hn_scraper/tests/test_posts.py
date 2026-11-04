import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from posts import parse_first_line
from threads import parse_top_level_comments

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def read_first_lines():
    return json.loads((FIXTURES_DIR / "first_lines.json").read_text(encoding="utf-8"))


def test_standard_first_line():
    case = read_first_lines()["standard"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_values_are_kept_as_written():
    case = read_first_lines()["values_as_written"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_lowercase_labels_without_spaces_around_pipes():
    case = read_first_lines()["lowercase_no_spaces"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_fields_in_another_order_with_an_extra_field():
    case = read_first_lines()["fields_in_another_order"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_extra_spaces_around_labels_and_values():
    case = read_first_lines()["extra_spaces"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_missing_field_is_left_empty():
    case = read_first_lines()["missing_relocation"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_post_that_does_not_follow_the_pattern():
    cases = read_first_lines()

    assert parse_first_line(cases["free_text"]["text"]) == cases["free_text"]["expected"]
    assert (
        parse_first_line(cases["labels_on_later_line"]["text"])
        == cases["labels_on_later_line"]["expected"]
    )
    assert parse_first_line(cases["empty"]["text"]) == cases["empty"]["expected"]
    assert parse_first_line(None) == cases["empty"]["expected"]


def test_unknown_labels_are_not_guessed_into_fields():
    case = read_first_lines()["unknown_labels"]

    assert parse_first_line(case["text"]) == case["expected"]


def test_first_line_of_each_comment_in_saved_thread():
    text = (FIXTURES_DIR / "sample_thread.json").read_text(encoding="utf-8")
    comments = parse_top_level_comments(text)

    parsed = [parse_first_line(comment["text"]) for comment in comments]

    assert parsed == [
        {"location": "Austin, TX", "remote": "Yes", "relocation": "No"},
        {"location": "Remote (US)", "remote": "Yes", "relocation": "Yes"},
    ]
