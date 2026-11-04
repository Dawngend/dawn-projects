LABELS = {
    "location": "location",
    "remote": "remote",
    "willing to relocate": "relocation",
    "relocate": "relocation",
    "relocation": "relocation",
}


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
