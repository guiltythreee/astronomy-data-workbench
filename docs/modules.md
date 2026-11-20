# ADW modules

ADW is one workbench made of five named modules (run `adw modules` to list them).

| # | Module | Priority | Status | Package |
|---|---|---|---|---|
| 01 | Catalogue Acquisition Manager | 1 | partial | `provenance/` |
| 02 | Star Catalogue Validator | 1 | available for BSC; Hipparcos-2 validator implemented, real-data run pending | `sources/bsc`, `sources/hipparcos`, `schemas`, `inspection`, `validation`, `export` |
| 03 | Astronomical Cross-Matching Workbench | 2 | partial, **UNVERIFIED** (synthetic-tested only) | `matching/` |
| 04 | Coordinate Accuracy Laboratory | 2 | partial | `coordinates/` |
| 05 | Star Identity Explorer | 3 | partial | `identity/` |

## 01 · Catalogue Acquisition Manager

Controls source discovery and retrieval, and records exactly where each file came from so every
output can be traced back to its input.

- Records source name, URL/archive ID, catalogue release and retrieval time.
- Records licence/redistribution status (default: `unverified`).
- Computes a SHA-256 checksum of the untouched source file.
- Supports local-file ingestion when automated retrieval is unavailable.

**Status:** local-file manifest and SHA-256 are built; automated download is not.

## 02 · Star Catalogue Validator

Inspects a catalogue file's schema and checks every record, sorting rows into accepted, rejected
and manual-review with row-level reasons.

- Checks required columns, malformed rows, duplicate IDs and null conventions.
- Checks RA/Dec ranges and suspicious magnitudes, proper motions, parallaxes and radial velocities.
- Keeps frame, equinox, epoch, units and passband explicit.
- Never silently repairs or coerces data; raw values are kept beside normalized ones.

**Commands:** `adw inspect`, `adw validate bsc-tsv`, `adw validate hip2-tsv`, `adw export bsc-tsv`, `adw audit`.
**Status:** BSC V/50 parser and validator were checked against a real export. Hipparcos-2 TSV
validation is implemented and covered by synthetic edge-case tests; the real I/311/hip2 export
still needs a full validation run.

## 03 · Astronomical Cross-Matching Workbench

Links the same object across BSC, Hipparcos, Gaia and later catalogues using evidence, not just
nearest angular distance.

- Uses trusted catalogue association tables where available.
- Otherwise compares epoch-propagated positions plus magnitude, colour, parallax, proper motion,
  multiplicity and quality flags.
- Keeps candidate alternatives with confidence scores and evidence.
- Never silently accepts an uncertain pair.

**Status:** partial and **UNVERIFIED**. Epoch-corrected positional matching, preserved candidates,
manual-review routing and evidence records are built and tested on synthetic data only. Real-catalogue
validation is a separate gate. See `docs/crossmatching.md`. Command: `adw crossmatch`.

## 04 · Coordinate Accuracy Laboratory

Tests coordinate and astrometric transformations against independent references and reports
numerical residuals with stated tolerances.

- Frame handling (FK5 vs ICRS), epoch propagation, proper motion, parallax, radial velocity.
- Precession/nutation, equatorial-to-horizontal, topocentric vs geocentric.
- Treats atmospheric refraction as a separate effect.
- Compares with independent implementations or published reference cases.

**Command:** `adw coords-lab [--out report.json]`.
**Status:** partial implementation present. Reference suites and a JSON-report CLI exist; Astropy is used for independent comparisons. Real-catalogue validation and further topocentric/environment coverage remain outstanding.

## 05 · Star Identity Explorer

A human-facing view of one object: its identifiers, measurements, provenance, match alternatives
and validation state, with uncertainty shown, not hidden.

- Shows HR / HD / HIP / Gaia IDs as separate typed identifiers.
- Shows source measurements with epochs, frames, units and passbands.
- Shows cross-match alternatives, quality flags and provenance.
- Presents validated data only; it never changes the data.

**Command:** `adw explorer [records.json] [--out identity-explorer.html]`.
**Status:** partial implementation present. A local searchable HTML explorer can be built; bundled records are synthetic fixtures, and validated production catalogue integration is not complete.
