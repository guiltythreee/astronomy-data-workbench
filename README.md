# Astronomy Data Workbench (ADW)

A standalone, local-first Python tool that inspects, validates and audits astronomical
catalogue files **before** any application (such as Star Map) consumes them.

> Parsing a file successfully is not the same as the data being scientifically right.
> ADW records where data came from, checks it, explains every problem row, and never
> modifies the source file.

**Status:** Phase 0 (foundation) + Phase 1 (BSC TSV ingestion and validation). Cross-matching,
the Coordinate Accuracy Lab and the Identity Explorer come later; see `docs/roadmap.md`.

## Install

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Requires Python 3.12+. Runtime has no third-party dependencies yet.

## Use

```bash
adw inspect my_bsc_export.tsv                       # what is in this file?
adw validate bsc-tsv my_bsc_export.tsv              # summary + row-level reasons
adw export bsc-tsv my_bsc_export.tsv --out adw-out  # write the audit bundle
adw audit adw-out --source my_bsc_export.tsv        # re-verify checksums
```

Try it now on the synthetic fixture (invented values, not real catalogue data):

```bash
adw validate bsc-tsv tests/fixtures/bsc_synthetic.tsv
```

### What `export` writes

| File | Content |
|---|---|
| `accepted.jsonl` | rows that passed every check, with normalized values **and** the raw cells |
| `review.jsonl` | parseable but suspicious rows, with reasons |
| `rejected.jsonl` | unusable rows, with reasons and source line numbers |
| `issues.csv` | one line per issue |
| `report.md` | human-readable summary |
| `audit.json` | input SHA-256, versions, config, counts, issue codes, output checksums |

Outputs contain no timestamps (only `audit.json` does), so the same input, config and version
always give byte-identical outputs and the same `content_checksum`.

## Data and licensing policy

- Catalogue data is **never** committed or redistributed here until the original CDS licence and
  redistribution terms are verified. `.gitignore` blocks `*.tsv` except the synthetic fixture.
- ADW's MIT licence covers the code only.

## Key conventions (BSC)

- Positions: FK5, equinox J2000, epoch J2000.0.
- `pmRA` is already mu_alpha* (includes cos dec); it is never multiplied by cos dec again.
- arcsec/yr and arcsec become mas/yr and mas by an explicit ×1000 only.
- Missing or malformed values are flagged, never silently turned into defaults.

See `docs/` for the full policy.
