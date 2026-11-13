# Source Fields

How each parser in `job_market_scraper/sources.py` maps upstream keys to the nine normalized fields in `POSTING_FIELDS`. Taken from the code only (checked 2026-11-13). It shows which keys the parsers ask for, not which keys the sources actually send.

## Input Shape and Skipped Items

| Parser | Endpoint constant | Expected input | Skipped items |
|---|---|---|---|
| `parse_remoteok` | `REMOTEOK_URL` | Top-level JSON list | Non-dict items, and items without a usable title |
| `parse_remotive` | `REMOTIVE_URL` | JSON object with a `jobs` list (`read_jobs`) | Same |
| `parse_himalayas` | `HIMALAYAS_URL` | JSON object with a `jobs` list (`read_jobs`) | Same |
| `parse_jobicy` | `JOBICY_URL` (`/api/v2/remote-jobs`) | JSON object with a `jobs` list (`read_jobs`) | Same |
| `parse_weworkremotely` | `WEWORKREMOTELY_URL` | RSS with an `rss` root and a `channel`, read from `./channel/item` | Items without a usable title |

A usable title is a `str` that is not blank (`has_title`). A wrong top-level shape raises `ValueError`.

## Field Mapping

"A, else B" means B is used only when A is falsy (Python `or`). For RSS, a key in angle brackets is the text of that child element of `<item>`.

| Output field | Remote OK | Remotive | Himalayas | Jobicy | We Work Remotely |
|---|---|---|---|---|---|
| `title` | `position`, else `title` | `title` | `title` | `jobTitle` | `<title>` text after the first `": "`, or the whole text if there is none |
| `company` | `company` | `company_name` | `companyName` | `companyName` | `<title>` text before the first `": "`, or blank if there is none |
| `url` | `url`, else `apply_url` | `url` | `applicationLink`, else `guid` | `url` | `<link>` |
| `source` | `"remoteok"` | `"remotive"` | `"himalayas"` | `"jobicy"` | `"weworkremotely"` |
| `location` | `location` | `candidate_required_location` | `locationRestrictions` | `jobGeo` | `<region>` |
| `published_date` | `date` | `publication_date` | `pubDate` | `pubDate` | `<pubDate>` |
| `tags` | `tags` | `tags` | `categories` | `jobIndustry` | Text of every `<category>` element |
| `salary` | `salary`, else `salary_min` and `salary_max` | `salary` | `salary`, else `minSalary` and `maxSalary` | `salary`, else `annualSalaryMin` and `annualSalaryMax` | `<salary>` |
| `description` | `description` | `description` | `description`, else `excerpt` | `jobDescription`, else `jobExcerpt` | `<description>` |

## Salary Fallbacks

Three parsers build a salary string with `format_salary(min, max, currency)` when the `salary` key is falsy.

| Parser | Minimum key | Maximum key | Currency label |
|---|---|---|---|
| Remote OK | `salary_min` | `salary_max` | Always `"USD"` (hard-coded) |
| Himalayas | `minSalary` | `maxSalary` | `currency`, else `"USD"` |
| Jobicy | `annualSalaryMin` | `annualSalaryMax` | `salaryCurrency`, else `"USD"` |

- Both bounds falsy (including `0`) gives `""`.
- Both bounds truthy gives `"<currency> <min> - <max>"`.
- One bound truthy gives `"<currency> <value>"`.
- No period (hour, year) is added, and the numbers are not checked.

Remotive and We Work Remotely read only their `salary` key or element and have no fallback.

## Source-Specific Steps

- **Himalayas location:** a list in `locationRestrictions` is joined with `", "`. Any other truthy value is converted with `str()`. A missing or falsy value becomes `""`.
- **We Work Remotely title and company:** the `<title>` text is split once on the first `": "`. The usable-title check runs on the part after the split.
- **We Work Remotely tags:** `<category>` elements with empty or missing text are left out.

## Shared Cleanup in `make_posting`

- `title`, `company`, `url`, `source`, `location` and `description` become `""` when falsy and are then stripped. These six call `.strip()` directly, so they are not converted with `str()` first.
- `published_date` and `salary` are converted with `str()` and stripped. A falsy value becomes `""`, so the date is stored as text and not parsed.
- `tags`: a single string becomes a one-item list. Each tag is converted with `str()` and stripped, and blank tags are dropped. A falsy value becomes `[]`.
