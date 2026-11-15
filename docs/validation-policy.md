# Validation policy

**Outcomes:** any error -> *rejected*; else any warning -> *review*; else *accepted*.

| Code | Severity | Meaning |
|---|---|---|
| ROW_COLUMN_COUNT | error | row width differs from header |
| HR_MISSING / HR_MALFORMED / HR_DUPLICATE | error | bad identifier (every duplicate is rejected) |
| RA_/DEC_ MISSING / MALFORMED / OUT_OF_RANGE | error | position unusable |
| NUMERIC_MALFORMED | warning | optional numeric unparseable; raw kept, normalized empty |
| VMAG_MISSING / VMAG_OUT_OF_RANGE | warning | possibly non-stellar or bad magnitude |
| PM_INCOMPLETE / PM_SUSPICIOUS | warning | one component only / implausibly large |
| PARALLAX_NEGATIVE / PARALLAX_SUSPICIOUS | warning | needs judgement |
| RADVEL_SUSPICIOUS | warning | implausibly large |
| FILE_MISSING_COLUMN | file warning | expected column absent |
| FILE_EXTRA_COLUMN | file info | unexpected column, kept in raw only |

Fatal (exit 2, nothing written): missing required column (HR, RAJ2000, DEJ2000), duplicate
header names, non-UTF-8 input. Thresholds live in `ValidationConfig` and are stored in `audit.json`.

Never done: silent coercion to null, invented epochs/frames/units, passband conversion,
discarding source flags, or modifying the input file.
