import re

LABELS = {
    "location": "location",
    "remote": "remote",
    "willing to relocate": "relocation",
    "relocate": "relocation",
    "relocation": "relocation",
}

US_COUNTRIES = [
    "united states",
    "usa",
]

US_STATES = [
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "district of columbia",
    "florida",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
]

US_STATE_CODES = [
    "AK",
    "AL",
    "AR",
    "AZ",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "GA",
    "HI",
    "IA",
    "ID",
    "IL",
    "IN",
    "KS",
    "KY",
    "LA",
    "MA",
    "MD",
    "ME",
    "MI",
    "MN",
    "MO",
    "MS",
    "MT",
    "NC",
    "ND",
    "NE",
    "NH",
    "NJ",
    "NM",
    "NV",
    "NY",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VA",
    "VT",
    "WA",
    "WI",
    "WV",
    "WY",
]

US_CITIES = [
    "atlanta",
    "austin",
    "baltimore",
    "bay area",
    "boston",
    "charlotte",
    "chicago",
    "cincinnati",
    "cleveland",
    "columbus",
    "dallas",
    "denver",
    "detroit",
    "houston",
    "indianapolis",
    "jacksonville",
    "kansas city",
    "las vegas",
    "los angeles",
    "miami",
    "milwaukee",
    "minneapolis",
    "nashville",
    "new orleans",
    "new york city",
    "nyc",
    "oakland",
    "orlando",
    "philadelphia",
    "phoenix",
    "pittsburgh",
    "portland",
    "raleigh",
    "sacramento",
    "salt lake city",
    "san antonio",
    "san diego",
    "san francisco",
    "san jose",
    "seattle",
    "sf",
    "tampa",
]


def build_word_pattern(words, flags=0):
    pattern = "|".join(re.escape(word) for word in words)
    return re.compile(r"\b(" + pattern + r")\b", flags)


US_NAME_PATTERN = build_word_pattern(
    US_COUNTRIES + US_STATES + US_CITIES, re.IGNORECASE
)
# Short codes stay uppercase so words like "in", "or", and "us" do not match.
US_CODE_PATTERN = build_word_pattern(["US"] + US_STATE_CODES)
REMOTE_PLACE_PATTERN = re.compile(r"remote\s*\(([^()]*)\)", re.IGNORECASE)


def parse_first_line(text):
    fields = {"location": "", "remote": "", "relocation": ""}
    if not text:
        return fields

    # The body of a post starts after <p>, so only the text before it is read.
    first_line = text.split("<p>", 1)[0].splitlines()
    if not first_line:
        return fields

    for part in first_line[0].split("|"):
        if ":" not in part:
            continue
        label, value = part.split(":", 1)
        field = LABELS.get(label.strip().lower())
        if field is not None:
            fields[field] = value.strip()
    return fields


def has_us_place(text):
    return (
        US_NAME_PATTERN.search(text) is not None
        or US_CODE_PATTERN.search(text) is not None
    )


def is_us_place(text):
    parts = [part.strip() for part in text.split(",")]
    return all(
        US_NAME_PATTERN.fullmatch(part) is not None
        or US_CODE_PATTERN.fullmatch(part) is not None
        for part in parts
    )


def is_us_location(location):
    if not location:
        return False
    # Remarks after "(", ";" or a dash ("overlaps US mornings") do not say where the person lives.
    before_remark = re.split(r";| - | — ", location)[0]
    main_place = before_remark.split("(", 1)[0]
    if has_us_place(main_place):
        return True
    # "Remote (US)" names a place only when the brackets hold a place, not a remark like "US hours".
    remote_match = REMOTE_PLACE_PATTERN.fullmatch(before_remark.strip())
    return remote_match is not None and is_us_place(remote_match.group(1))
