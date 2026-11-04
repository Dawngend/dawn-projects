import argparse
from pathlib import Path
import re

from posts import is_us_location, parse_first_line
from storage import OUTPUT_DIR, export_csv, save_posts
from threads import fetch_top_level_comments

# Posts write the contact as "Contact:" or "Email:", in the first line or the body.
CONTACT_PATTERN = re.compile(r"\b(?:contact|email)\s*:\s*([^|<\n]+)", re.IGNORECASE)


def parse_contact(text):
    if not text:
        return ""
    match = CONTACT_PATTERN.search(text)
    return match.group(1).strip() if match else ""


def main(month, output_dir=None):
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir = Path(output_dir)
    database_path = output_dir / "posts.db"
    csv_path = output_dir / "posts.csv"

    comments = fetch_top_level_comments(month)

    us_posts = []
    for comment in comments:
        fields = parse_first_line(comment["text"])
        if not is_us_location(fields["location"]):
            continue
        us_posts.append(
            {
                "username": comment["username"],
                "location": fields["location"],
                "url": comment["url"],
                "contact": parse_contact(comment["text"]),
                "thread_month": month,
                "posted_time": comment["posted_time"],
            }
        )

    save_posts(us_posts, database_path)
    export_csv(database_path, csv_path)

    print(f"Comments read: {len(comments)}")
    print(f"US posts saved: {len(us_posts)}")
    print(f"Database saved to {database_path}")
    print(f"CSV saved to {csv_path}")
    return database_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True, help="YYYY-MM, for example 2026-11")
    main(parser.parse_args().month)