from datetime import datetime, timezone


def build_survival_records(run_rows, observation_rows):
    runs_by_id = {}
    seen_source_times = set()
    for row in run_rows:
        run_id = row["id"]
        if (
            run_id is None
            or isinstance(run_id, bool)
            or (isinstance(run_id, str) and not run_id.strip())
        ):
            raise ValueError("run id is required")
        if run_id in runs_by_id:
            raise ValueError(f"duplicate run id: {run_id}")

        source = row["source"]
        run_at = row["run_at"]
        status = row["status"]
        for name, value in (
            ("source", source),
            ("run_at", run_at),
            ("status", status),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-blank string")

        moment = datetime.fromisoformat(run_at.strip())
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        moment = moment.astimezone(timezone.utc)

        if (source, moment) in seen_source_times:
            raise ValueError(f"duplicate run time for {source}: {run_at}")
        seen_source_times.add((source, moment))

        runs_by_id[run_id] = {
            "id": run_id,
            "source": source,
            "run_at": run_at,
            "moment": moment,
            "status": status,
            "posting_keys": set(),
        }

    for row in observation_rows:
        run_id = row["source_run_id"]
        if run_id not in runs_by_id:
            raise ValueError(f"unknown source_run_id: {run_id}")
        run = runs_by_id[run_id]

        if "source" in row.keys():
            if not isinstance(row["source"], str) or row["source"] != run["source"]:
                raise ValueError("observation source does not match run source")

        posting_key = row["posting_key"]
        if not isinstance(posting_key, str) or not posting_key.strip():
            raise ValueError("posting_key must be a non-blank string")

        run["posting_keys"].add(posting_key)

    runs_by_source = {}
    for run in runs_by_id.values():
        runs_by_source.setdefault(run["source"], []).append(run)

    records = []
    for source in sorted(runs_by_source):
        source_runs = sorted(runs_by_source[source], key=lambda run: run["moment"])

        # Both ok and legacy runs prove presence for their stored postings.
        presence_runs_by_key = {}
        for run in source_runs:
            if run["status"] not in ("ok", "legacy"):
                continue
            for posting_key in run["posting_keys"]:
                presence_runs_by_key.setdefault(posting_key, []).append(run)

        # Legacy, failed and empty runs cannot prove that a posting disappeared.
        absence_runs = [
            run
            for run in source_runs
            if run["status"] == "ok" and run["posting_keys"]
        ]

        for posting_key in sorted(presence_runs_by_key):
            presence_runs = presence_runs_by_key[posting_key]
            first_seen = presence_runs[0]["run_at"]
            last_presence = presence_runs[-1]
            last_seen = last_presence["run_at"]

            first_missed = None
            for run in absence_runs:
                if (
                    run["moment"] > last_presence["moment"]
                    and posting_key not in run["posting_keys"]
                ):
                    first_missed = run["run_at"]
                    break

            event = first_missed is not None
            records.append(
                {
                    "source": source,
                    "posting_key": posting_key,
                    "first_seen": first_seen,
                    "last_seen": last_seen,
                    "first_missed": first_missed,
                    "event": event,
                    "censoring": "interval" if event else "right",
                }
            )

    return records
