# Data Contracts

Rules for `normalize_title`, `normalize_published_date`, `normalize_salary`, `normalize_salary_range`, `normalize_currency`, and `normalize_salary_period` as implemented in `job_intel/contracts.py` and tested in `job_intel/tests/test_contracts.py`. Six functions are covered: the five text normalizers return `""` when an input is rejected, while `normalize_salary_range` returns `None`.

## Title (`normalize_title`)

### Accepted

- Non-blank `str` values. Leading and trailing whitespace (spaces, tabs, newlines) is stripped, while internal spacing is kept as-is (`"  Junior Data Scientist  "` becomes `"Junior Data Scientist"`, and `"Senior  Data  Engineer"` stays `"Senior  Data  Engineer"`).

### Rejected

- Empty or whitespace-only strings (`""`, `"   "`, `"\n\t"`).
- Non-string values (`None`, integers, floats, booleans, lists, and dicts).

## Published Date (`normalize_published_date`)

Accepted inputs have outer whitespace trimmed, convert any explicit offset to UTC, and return a UTC ISO-8601 timestamp ending in `+00:00`. Passing an already-normalized timestamp returns the same string.

### Accepted

- ISO-8601 timestamps and dates parsed by `datetime.fromisoformat`, including `Z` and numeric offsets (`"2026-11-03T08:00:00Z"`, `"2026-11-04T08:55:14.891833+00:00"`, `"2026-11-03T08:00:00-05:00"`), timezone-naive timestamps (`"2026-11-03T08:00:00"`), and date-only strings (`"2026-11-03"`).
- RFC 2822 RSS dates parsed by `email.utils.parsedate_to_datetime`, with or without a timezone offset (`"Wed, 21 Jun 2023 14:22:59 +0000"`, `"Tue, 03 Nov 2026 19:09:15 +0100"`, `"Tue, 03 Nov 2026 19:09:15"`).
- Unix epoch seconds given as a 9- or 10-digit decimal string or integer (`"1793772778"`, `1793772778`).

### Rejected

- `None`, empty strings, and whitespace-only strings (`""`, `"   "`, `"\n"`).
- Unparseable text and invalid calendar dates (`"not a date"`, `"2026-13-45"`, `"Tue, 32 Nov 2026 19:09:15 +0000"`).
- Digit strings that fail ISO and RFC 2822 parsing and do not have 9 or 10 decimal digits (`"12345"`, `"123456789012"`).

### Naive-timezone assumption

When a parsed ISO or RFC 2822 value has no timezone offset, `normalize_published_date` treats it as UTC (`+00:00`) rather than converting from a local timezone. Date-only ISO strings (`"2026-11-03"`) become midnight UTC (`"2026-11-03T00:00:00+00:00"`). This is a normalization assumption for inputs that omit an offset, not proof that the source recorded the time in UTC.

## Salary

Four functions cover the salary text, numeric range, currency code and pay period. The three text functions return `""` when an input is rejected, while `normalize_salary_range` returns `None`.

### Salary Text (`normalize_salary`)

The salary is kept as trimmed text. No numeric range is parsed, and no currency or pay period is read out of it.

#### Accepted

- Non-blank `str` values. Leading and trailing whitespace is stripped and everything inside is kept as-is (`"  USD 100000 - 120000  "` becomes `"USD 100000 - 120000"`, and `"USD 100000 -  120000"` keeps its inner double space).
- Any non-blank text, because the content is not checked (`"$120,000/yr"`, `"€60k-80k"` and `"DOE"` are all returned unchanged).

#### Rejected

- Empty or whitespace-only strings (`""`, `"   "`, `"\n\t"`).
- Non-string values, including numbers (`None`, `100000`, `4.5`, `True`, lists and dicts).

### Numeric Range (`normalize_salary_range`)

This function takes two numeric bounds, not salary text. It is separate from `normalize_salary` and does not parse the text.

A valid pair is returned as a two-item tuple of floats, with `None` kept for a missing bound. Any rejection returns `None` for the whole range, so one bad bound never leaves a half-valid result.

#### Accepted

- Two `int` or `float` values, or a mix, converted to floats (`(70000, 90000)` becomes `(70000.0, 90000.0)`).
- Equal bounds (`(80000, 80000)` becomes `(80000.0, 80000.0)`).
- Zero, because only values below zero are rejected (`(0, 50000)` becomes `(0.0, 50000.0)`).
- One bound missing, which stays `None` in the tuple (`(70000, None)` becomes `(70000.0, None)`, and `(None, 90000)` becomes `(None, 90000.0)`).
- Both bounds missing, which gives `(None, None)`.

#### Rejected

- A minimum greater than the maximum (`(90000, 70000)` and `(0.01, 0)`).
- A negative bound on either side (`(-1, 90000)`, `(70000, -1)`).
- A non-finite bound (`nan`, `inf`, `-inf`), or an integer too large to convert to a float.
- Booleans, even though Python treats `bool` as a kind of `int` (`(True, 90000)`, `(70000, False)`).
- Numeric strings and any other non-numeric value (`"70000"`, `"90k"`, `""`, `"DOE"`, lists, dicts and bytes).

#### Where It Is Stored

The observation log still stores raw salary text in the `observations.salary` column. There is no numeric minimum or maximum column there, so `normalize_salary_range` is not called when an observation is recorded and does not change the stored text. Structured numeric bounds exist in the separate `backfill_postings` table, whose `salary_min` and `salary_max` columns are loaded as they come in the export.

### Currency (`normalize_currency`)

This is a format check only. It accepts any three ASCII letters and does not check that the code is an assigned ISO 4217 currency.

#### Accepted

- `str` values that are exactly three ASCII letters after outer whitespace is stripped, returned in uppercase (`"USD"` stays `"USD"`, `"eur"` becomes `"EUR"`, `"gBp"` becomes `"GBP"`, `"  cad  "` becomes `"CAD"`).
- Three letters that are not a real currency code (`"zzz"` becomes `"ZZZ"`).

#### Rejected

- Empty or whitespace-only strings (`""`, `"   "`, `"\n\t"`).
- The wrong number of characters (`"US"`, `"USDT"`, `"$"`).
- Digits, symbols or inner spaces (`"US1"`, `"123"`, `"$US"`, `"U S"`).
- Non-ASCII letters (`"ÜSD"`, `"€UR"`, full-width `"ＵＳＤ"`).
- Non-string values (`None`, `123`, `4.5`, `True`, `b"USD"`, lists and dicts).

### Pay Period (`normalize_salary_period`)

The value is stripped and lowercased, then looked up in a fixed list of aliases. The result is one of `hour`, `day`, `week`, `month` or `year`.

| Returned value | Accepted labels |
|---|---|
| `hour` | `hour`, `hourly`, `hr`, `hrs` |
| `day` | `day`, `daily` |
| `week` | `week`, `weekly`, `wk` |
| `month` | `month`, `monthly`, `mo` |
| `year` | `year`, `yearly`, `yr`, `yrs`, `annual`, `annually` |

#### Accepted

- Any label in the table, in any letter case and with outer whitespace (`"Hourly"` becomes `"hour"`, `"  Weekly  "` becomes `"week"`, `"MONTHLY"` becomes `"month"`, `"Annually"` becomes `"year"`).

#### Rejected

- Empty or whitespace-only strings (`""`, `"   "`, `"\n\t"`).
- Labels that are not in the table, which return `""` instead of a guess (`"fortnight"`, `"quarter"`, `"sem"`, `"per year"`, `"yearss"`, `"$"`).
- Non-string values (`None`, `12`, `4.5`, `True`, lists and dicts).
