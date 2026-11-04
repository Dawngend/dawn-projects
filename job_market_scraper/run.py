from pathlib import Path

from dashboard import write_dashboard
from history import save_postings
import sources


def main(output_dir=None):
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output"
    output_dir = Path(output_dir)

    source_functions = [
        (sources.fetch_remoteok, sources.parse_remoteok),
        (sources.fetch_remotive, sources.parse_remotive),
        (sources.fetch_himalayas, sources.parse_himalayas),
        (sources.fetch_jobicy, sources.parse_jobicy),
        (sources.fetch_weworkremotely, sources.parse_weworkremotely),
    ]
    postings = []
    for fetch, parse in source_functions:
        postings.extend(parse(fetch()))

    output_dir.mkdir(parents=True, exist_ok=True)
    database_path = output_dir / "history.db"
    save_postings(database_path, postings)
    dashboard_path = write_dashboard(database_path, output_dir / "dashboard.html")

    print(f"Postings fetched: {len(postings)}")
    print(f"History saved to {database_path}")
    print(f"Dashboard saved to {dashboard_path}")
    return dashboard_path


if __name__ == "__main__":
    main()
