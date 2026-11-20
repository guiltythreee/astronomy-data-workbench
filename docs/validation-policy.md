# Validation policy

**Outcomes:** any error -> *rejected*; else any warning -> *review*; else *accepted*. Row-level
*info* diagnostics are recorded but never change the outcome.

| Code | Severity | Meaning |
|---|---|---|
| ROW_COLUMN_COUNT | error | row width differs from header |
| HR_MISSING / HR_MALFORMED / HR_DUPLICATE | error | bad identifier (every duplicate is rejected) |
| RA_/DEC_ MISSING / MALFORMED / OUT_OF_RANGE | error | position unusable |
| NUMERIC_MALFORMED | warning | optional numeric unparseable; raw kept, normalized empty |
| VMAG_MISSING / VMAG_OUT_OF_RANGE | warning | possibly non-stellar or bad magnitude |
| PM_INCOMPLETE / PM_SUSPICIOUS | warning | one component only / implausibly large |
| PARALLAX_SUSPICIOUS | warning | implausibly large positive parallax |
| PARALLAX_NEGATIVE | info | negative measured parallax; kept signed, never clamped, does not change the outcome |
| RADVEL_SUSPICIOUS | warning | implausibly large |
| FILE_MISSING_COLUMN | file warning | expected column absent |
| FILE_EXTRA_COLUMN | file info | unexpected column, kept in raw only |

Fatal (exit 2, nothing written): missing required column (HR, RAJ2000, DEJ2000), duplicate
header names, non-UTF-8 input. Thresholds live in `ValidationConfig` and are stored in `audit.json`.

Never done: silent coercion to null, invented epochs/frames/units, passband conversion,
discarding source flags, or modifying the input file.


## Hipparcos-2 (VizieR I/311/hip2)

The `hip2-tsv` validator is a separate schema from BSC. Its required columns are `HIP`, `RArad`,
and `DErad`; the expected export profile is `HIP`, `RArad`, `e_RArad`, `DErad`, `e_DErad`, `Plx`,
`e_Plx`, `pmRA`, `e_pmRA`, `pmDE`, `e_pmDE`, `Hpmag`, `e_Hpmag`, `B-V`, `e_B-V`, and `HIP1`.

- `RArad` and `DErad` are degrees (not radians), in ICRS at epoch J1991.25.
- Astrometric uncertainties are in mas; proper motions and their uncertainties are in mas/yr.
- Negative parallax is retained with `PARALLAX_NEGATIVE` at `info` severity.
- No fixed maximum proper-motion threshold is applied; extreme but finite values are preserved.
- Astrometric uncertainties, when present, must be positive. Photometric uncertainties may be zero
  but cannot be negative; in particular `e_B-V = 0` is accepted.
- `HIP1` is treated as a VizieR hyperlink placeholder, not a cross-catalogue identifier.
- Raw values are preserved beside normalized values. Duplicate/non-positive HIP identifiers and
  invalid positions are rejected; malformed optional numeric values and invalid uncertainties go
  to review.

The exported metadata line `Coosys J2000_1991.250: eq_FK5 J2000` conflicts with the I/311 catalogue
astrometric frame documentation. ADW records the documented catalogue frame as ICRS and epoch
J1991.25; it does not rewrite the original file. The raw export should be retained so this metadata
inconsistency remains auditable. The Hipparcos-2 validator has synthetic tests but must still be run
against the real export before its schema assumptions are considered empirically verified.
