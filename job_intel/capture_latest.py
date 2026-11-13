import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
from urllib.parse import quote

from observation_log import capture_latest_snapshot, create_schema
from quality_report import write_run_quality_report

DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[1] / "job_market_scraper" / "output" / "history.db"
)
DEFAULT_TARGET = Path(__file__).resolve().parent / "data" / "observations.db"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--target", type=Path, default=None)
    args = parser.parse_args(argv)

    source_path = DEFAULT_SOURCE if args.source is None else args.source
    target_path = DEFAULT_TARGET if args.target is None else args.target
    if target_path.name.lower() == "backfill.db":
        raise ValueError("observations must not be written to backfill.db")
    reports_dir = target_path.parent / "quality_reports"

    # The path is percent-encoded so a "#", "%" or space in it is read as
    # part of the file name. An unescaped "#" would cut the URI short and
    # drop mode=ro.
    encoded_path = quote(source_path.resolve().as_posix(), safe="/:")
    source_uri = f"file:{encoded_path}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(target_path)) as target:
            create_schema(target)
            with target:
                inserted = capture_latest_snapshot(source, target)

            # The capture is already saved here, so a report that fails to
            # write does not undo it. Every run in the log gets its report
            # written again, so the next call restores a missing report.
            run_ids = target.execute(
                "SELECT id FROM source_runs ORDER BY id"
            ).fetchall()
            for (run_id,) in run_ids:
                write_run_quality_report(target, run_id, reports_dir)

    print(f"Observations inserted: {inserted}")
    print(f"Observations saved to {target_path}")
    print(f"Quality reports written: {len(run_ids)}")
    print(f"Quality reports saved to {reports_dir}")
    return inserted


if __name__ == "__main__":
    main()
