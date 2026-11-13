# Salary Source Audit

Checked on 2026-11-13 using only `job_market_scraper/sources.py` and a read-only aggregate query on `job_market_scraper/output/history.db`. Blank means `trim(salary) = ''` in the saved database.

## Remote OK

### Verified facts

- The history contains 99 Remote OK rows. The saved `salary` field is nonblank in 21 rows and blank in 78 rows.
- `parse_remoteok` first reads the upstream `salary` key.
- If that value is falsy, it calls `format_salary` with upstream `salary_min`, `salary_max`, and a hard-coded USD currency label.
- The fallback returns a formatted value when either bound is truthy. It returns an empty string when both bounds are falsy.
- `make_posting` converts the resulting salary to a string and strips surrounding whitespace. A remaining false-like value becomes an empty string.

### Finding

**Unresolved from the available evidence.** The saved blanks are real, but they do not show whether the source omitted salary information or supplied it in a form the parser did not retain. The parser does have a `salary_min` and `salary_max` fallback, so the blanks are not explained by a complete absence of that fallback. Raw responses and parser-version history are unavailable here, so a source omission and a remaining parser gap cannot be distinguished.

## We Work Remotely

### Verified facts

- The history contains 100 We Work Remotely rows. The saved `salary` field is blank in all 100 rows.
- `parse_weworkremotely` reads only the RSS `salary` element through `item.findtext("salary")`.
- There is no salary-minimum or salary-maximum fallback and no extraction from any other field.
- `make_posting` applies the same string conversion and whitespace stripping used for the other sources.

### Finding

**Unresolved from the available evidence.** The parser has a narrow salary mapping, but the aggregate counts cannot show whether the saved runs received blank or absent `salary` elements, or whether usable salary information appeared elsewhere and was discarded. Therefore, neither a source omission nor an actual parser-caused loss can be established from this evidence alone. The missing fallbacks are a parser limitation, not proof that salary data was lost.

## Evidence Limit

The database stores only the normalized `salary` text, not the upstream salary keys or RSS elements. Deciding between source omission and parser loss would require saved raw responses or suitable fixtures, without treating absence from the normalized database as absence from the source.
