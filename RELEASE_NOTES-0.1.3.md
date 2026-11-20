# ADW 0.1.3 release notes

One consolidated release of the five named ADW modules, built from the single merged tree
(`ADW-current-merged.zip`). Earlier archives (`adw-integrated-backup-2.zip`, `adw-05-docs-fixed.zip`,
`ADW-current-merged.zip`) were not modified.

## What is in this release

| # | Module | CLI | Single-file tool | Status |
|---|---|---|---|---|
| 01 | Catalogue Acquisition Manager | `adw export` (manifest in `audit.json`) | `01-catalogue-acquisition-manager.pyz` | Partial: local-file provenance + SHA-256; no automated downloads |
| 02 | Star Catalogue Validator | `adw inspect / validate / export / audit` | `02-star-catalogue-validator.pyz` | BSC V/50 VizieR TSV; synthetic fixtures only |
| 03 | Astronomical Cross-Matching Workbench | `adw crossmatch run / demo / verify` | `03-astronomical-cross-matching-workbench.pyz` | **UNVERIFIED**: synthetic-tested only |
| 04 | Coordinate Accuracy Laboratory | `adw coords-lab` | `04-coordinate-accuracy-laboratory.pyz` | Partial: reference suites + JSON report (needs NumPy, Astropy) |
| 05 | Star Identity Explorer | `adw explorer` | `05-star-identity-explorer.pyz` | Partial: bundled records are synthetic |

## Changes since 0.1.2

- Cross-matching workbench, coordinate lab and identity explorer integrated into the main CLI.
- Explorer assets packaged in the wheel; `.pyz` tools load them via `importlib.resources`.
- Module status metadata and documentation reconciled with the commands that actually exist.
- Stale 0.1.x consolidation notes in `CHANGELOG.md` removed (they said matching was still planned).
- Lint fixes (Ruff 0.17 default rules): implicit string concatenation, `dict()` literals, import
  order, an invalid `# fmt: skip`, and a blind `pytest.raises(Exception)` now `FrozenInstanceError`.
  No behavioural change.

## Verification (2026-11-19, Python 3.12.3, Ruff 0.17.6)

- `ruff check .`: clean. `mypy` (strict): no issues in 41 source files.
- `pytest`: **185 passed, 0 skipped** (Astropy and Hypothesis installed).
- Wheel built and installed into a clean venv: `adw --version` = 0.1.3; `inspect`, `export`, `audit`,
  `explorer`, `coords-lab` (all_passed=True) and `crossmatch demo` / `verify` ran correctly.
- All five `.pyz` rebuilt and smoke-tested; `04` correctly reports a missing Astropy when run
  without it.

## Known limits (unchanged)

- No real-catalogue validation has been done. The BSC parser has only seen the synthetic fixture.
- Cross-matching keeps its UNVERIFIED label until real BSC, Hipparcos and Gaia validation passes.
- `.pyz` files need an installed Python 3.12+; tool 04 also needs NumPy and Astropy.

## Next gate

Real BSC V/50 validation (see `docs/roadmap.md`).
