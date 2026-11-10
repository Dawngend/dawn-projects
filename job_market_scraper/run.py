from pathlib import Path
import sys

from dashboard import write_dashboard
from history import save_postings
import sources


def main(output_dir=None):
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output"
    output_dir = Path(output_dir)

    source_functions = [
        ("remoteok", sources.fetch_remoteok, sources.parse_remoteok),
        ("remotive", sources.fetch_remotive, sources.parse_remotive),
        ("himalayas", sources.fetch_himalayas, sources.parse_himalayas),
        ("jobicy", sources.fetch_jobicy, sources.parse_jobicy),
        ("weworkremotely", sources.fetch_weworkremotely, sources.parse_weworkremotely),
    ]
    postings = []
    failed_sources = []
    for name, fetch, parse in source_functions:
        try:
            source_postings = parse(fetch())
        except Exception as error:
            failed_sources.append(name)
            print(
                f"Failed source: {name} ({type(error).__name__}). Try again later.",
                file=sys.stderr,
            )
            continue
        postings.extend(source_postings)

    if len(failed_sources) == len(source_functions):
        print("No sources succeeded. Output files were not changed.", file=sys.stderr)
        raise SystemExit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "history.db"
    unique_postings = save_postings(database_path, postings)
    dashboard_path = write_dashboard(
        database_path, output_dir / "dashboard.html", failed_sources=failed_sources
    )

    if failed_sources:
        succeeded = len(source_functions) - len(failed_sources)
        print(
            f"Partial results: {unique_postings} unique postings this run "
            f"from {succeeded} of {len(source_functions)} sources."
        )
    else:
        print(f"Unique postings this run: {unique_postings}")
    print(f"History saved to {database_path}")
    print(f"Dashboard saved to {dashboard_path}")
    return dashboard_path


if __name__ == "__main__":
    main()
