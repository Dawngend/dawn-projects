import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from survival_records import build_survival_records

T1 = "2026-11-04T10:00:00+00:00"
T2 = "2026-11-05T10:00:00+00:00"
T3 = "2026-11-06T10:00:00+00:00"
T4 = "2026-11-07T10:00:00+00:00"
T5 = "2026-11-08T10:00:00+00:00"


def make_run(run_id, run_at, status="ok", source="board_alpha"):
    return {
        "id": run_id,
        "source": source,
        "run_at": run_at,
        "status": status,
    }


def make_observation(run_id, posting_key, source="board_alpha"):
    return {
        "source_run_id": run_id,
        "source": source,
        "posting_key": posting_key,
    }


def test_presence_followed_by_nonempty_ok_run_without_posting_is_an_event():
    runs = [make_run(1, T1), make_run(2, T2)]
    observations = [
        make_observation(1, "post-1"),
        make_observation(1, "post-2"),
        make_observation(2, "post-2"),
    ]

    records = build_survival_records(runs, observations)

    assert records == [
        {
            "source": "board_alpha",
            "posting_key": "post-1",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": T2,
            "event": True,
            "censoring": "interval",
        },
        {
            "source": "board_alpha",
            "posting_key": "post-2",
            "first_seen": T1,
            "last_seen": T2,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
    ]


def test_first_missed_uses_the_earliest_qualifying_ok_run_after_last_presence():
    runs = [make_run(1, T1), make_run(2, T2), make_run(3, T3), make_run(4, T4)]
    observations = [
        make_observation(1, "post-1"),
        make_observation(2, "post-1"),
        make_observation(3, "post-2"),
        make_observation(4, "post-2"),
    ]

    records = build_survival_records(runs, observations)

    assert records[0] == {
        "source": "board_alpha",
        "posting_key": "post-1",
        "first_seen": T1,
        "last_seen": T2,
        "first_missed": T3,
        "event": True,
        "censoring": "interval",
    }


def test_single_run_right_censors_at_last_presence():
    runs = [make_run(1, T1)]
    observations = [make_observation(1, "post-1"), make_observation(1, "post-2")]

    records = build_survival_records(runs, observations)

    assert records == [
        {
            "source": "board_alpha",
            "posting_key": "post-1",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
        {
            "source": "board_alpha",
            "posting_key": "post-2",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
    ]


def test_legacy_run_proves_presence_and_later_nonempty_ok_run_proves_absence():
    runs = [make_run(1, T1, status="legacy"), make_run(2, T2, status="ok")]
    observations = [
        make_observation(1, "post-1"),
        make_observation(2, "post-2"),
    ]

    records = build_survival_records(runs, observations)

    assert records[0] == {
        "source": "board_alpha",
        "posting_key": "post-1",
        "first_seen": T1,
        "last_seen": T1,
        "first_missed": T2,
        "event": True,
        "censoring": "interval",
    }


def test_legacy_run_never_proves_absence():
    runs = [make_run(1, T1, status="ok"), make_run(2, T2, status="legacy")]
    observations = [
        make_observation(1, "post-1"),
        make_observation(2, "post-2"),
    ]

    records = build_survival_records(runs, observations)

    assert records == [
        {
            "source": "board_alpha",
            "posting_key": "post-1",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
        {
            "source": "board_alpha",
            "posting_key": "post-2",
            "first_seen": T2,
            "last_seen": T2,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
    ]


@pytest.mark.parametrize("failure_status", ["failed", "error"])
def test_failed_runs_cannot_prove_absence_or_presence(failure_status):
    runs = [make_run(1, T1, status="ok"), make_run(2, T2, status=failure_status)]
    observations = [
        make_observation(1, "post-1"),
        make_observation(2, "stray-post"),
    ]

    records = build_survival_records(runs, observations)

    assert records == [
        {
            "source": "board_alpha",
            "posting_key": "post-1",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        }
    ]


def test_empty_ok_run_cannot_prove_absence():
    runs = [make_run(1, T1, status="ok"), make_run(2, T2, status="ok")]
    observations = [make_observation(1, "post-1")]

    records = build_survival_records(runs, observations)

    assert records == [
        {
            "source": "board_alpha",
            "posting_key": "post-1",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        }
    ]


def test_failed_empty_and_legacy_runs_are_skipped_until_a_nonempty_ok_run():
    runs = [
        make_run(1, T1, status="ok"),
        make_run(2, T2, status="failed"),
        make_run(3, T3, status="ok"),
        make_run(4, T4, status="legacy"),
        make_run(5, T5, status="ok"),
    ]
    observations = [
        make_observation(1, "post-1"),
        make_observation(4, "post-2"),
        make_observation(5, "post-2"),
    ]

    records = build_survival_records(runs, observations)

    assert records[0] == {
        "source": "board_alpha",
        "posting_key": "post-1",
        "first_seen": T1,
        "last_seen": T1,
        "first_missed": T5,
        "event": True,
        "censoring": "interval",
    }


def test_other_source_runs_do_not_prove_absence_and_same_keys_stay_separate():
    runs = [
        make_run(1, T1, status="ok", source="board_alpha"),
        make_run(2, T2, status="ok", source="board_beta"),
    ]
    observations = [
        make_observation(1, "shared-key", source="board_alpha"),
        make_observation(2, "other-key", source="board_beta"),
        make_observation(2, "shared-key", source="board_beta"),
    ]

    records = build_survival_records(runs, observations)

    assert records == [
        {
            "source": "board_alpha",
            "posting_key": "shared-key",
            "first_seen": T1,
            "last_seen": T1,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
        {
            "source": "board_beta",
            "posting_key": "other-key",
            "first_seen": T2,
            "last_seen": T2,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
        {
            "source": "board_beta",
            "posting_key": "shared-key",
            "first_seen": T2,
            "last_seen": T2,
            "first_missed": None,
            "event": False,
            "censoring": "right",
        },
    ]


def test_reappearing_posting_anchors_on_last_presence():
    runs = [make_run(1, T1), make_run(2, T2), make_run(3, T3)]
    observations = [
        make_observation(1, "post-1"),
        make_observation(2, "post-2"),
        make_observation(3, "post-1"),
    ]

    records = build_survival_records(runs, observations)

    assert records[0] == {
        "source": "board_alpha",
        "posting_key": "post-1",
        "first_seen": T1,
        "last_seen": T3,
        "first_missed": None,
        "event": False,
        "censoring": "right",
    }


def test_unsorted_inputs_with_timezone_offsets_sort_chronologically_and_stay_unchanged():
    # 12:00+02:00 is 10:00 UTC, earlier than 11:00Z on the same day.
    earlier_offset = "2026-11-04T12:00:00+02:00"
    later_utc = "2026-11-04T11:00:00Z"
    runs = [make_run(2, later_utc), make_run(1, earlier_offset)]
    observations = [make_observation(2, "post-2"), make_observation(1, "post-1")]
    runs_before = copy.deepcopy(runs)
    observations_before = copy.deepcopy(observations)

    records = build_survival_records(runs, observations)

    assert runs == runs_before
    assert observations == observations_before
    assert records[0] == {
        "source": "board_alpha",
        "posting_key": "post-1",
        "first_seen": earlier_offset,
        "last_seen": earlier_offset,
        "first_missed": later_utc,
        "event": True,
        "censoring": "interval",
    }


def test_empty_inputs_and_observationless_runs_return_no_records():
    assert build_survival_records([], []) == []
    assert build_survival_records([make_run(1, T1)], []) == []


@pytest.mark.parametrize(
    "runs, observations, match",
    [
        (
            [make_run(1, T1)],
            [make_observation(99, "post-1")],
            "unknown source_run_id",
        ),
        (
            [make_run(1, T1, source="board_alpha")],
            [make_observation(1, "post-1", source="board_beta")],
            "observation source does not match run source",
        ),
        (
            [make_run(1, T1), make_run(1, T2)],
            [],
            "duplicate run id",
        ),
        (
            [make_run(1, T1), make_run(2, "2026-11-04T10:00:00Z")],
            [],
            "duplicate run time",
        ),
        (
            [make_run(1, T1)],
            [make_observation(1, "   ")],
            "posting_key must be a non-blank string",
        ),
        (
            [make_run(1, "not-a-timestamp")],
            [],
            "Invalid isoformat string",
        ),
    ],
)
def test_invalid_run_or_observation_rows_raise_value_error(runs, observations, match):
    with pytest.raises(ValueError, match=match):
        build_survival_records(runs, observations)
