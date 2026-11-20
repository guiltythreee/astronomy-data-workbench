# Consolidation and validation report

> **Current merged snapshot.** The original consolidation notes below are historical. Module 03 now
> has an epoch-corrected positional matching implementation tested on synthetic scenarios only;
> real-catalogue validation remains pending. See `CHANGELOG.md` and `docs/crossmatching.md`.

## Deliverables

Five single-file Python archives are provided in `dist/`, one per named ADW tool. Each archive contains the ADW Python package and the tool entry point. `ADW-compiled-tools-and-source.zip` contains all five archives plus the consolidated source tree, tests, documentation, build script, and source-archive checksum inventory.

## Merge policy

- Used `adw-update-0.1.2.zip` as the base because it is the latest complete project snapshot.
- Applied the Phase 3 backups in chronological order, then the Phase 3–4 backup. The latest backup's empty root `src/astronomy_data_workbench/__init__.py` was deliberately not allowed to overwrite the 0.1.2 initializer, preserving `__version__` and package imports.
- Included the Coordinate Lab modules and tests, plus Identity Explorer builder, HTML template, synthetic fixture, and tests.
- Preserved the original source ZIP files unchanged. The two `adw-phase3-4-backup-6` archives are byte-identical; the duplicate was not applied twice.
- Integrated the later Cross-Matching Workbench implementation and its synthetic tests; retained explicit UNVERIFIED status pending real catalogue validation.
- Merged the Phase 3/4 CLI and wheel-package-data fixes without discarding the cross-matching implementation.

## Tool status after consolidation

| Tool | Status in supplied code | Compiled file |
|---|---|---|
| Catalogue Acquisition Manager | Partial: local-file provenance + SHA-256; no automated downloads | `01-catalogue-acquisition-manager.pyz` |
| Star Catalogue Validator | Implemented for BSC V/50 VizieR TSV | `02-star-catalogue-validator.pyz` |
| Astronomical Cross-Matching Workbench | Partial: synthetic-tested, UNVERIFIED on real catalogues | `03-astronomical-cross-matching-workbench.pyz` |
| Coordinate Accuracy Laboratory | Partial: reference suites + JSON report CLI | `04-coordinate-accuracy-laboratory.pyz` |
| Star Identity Explorer | Partial: searchable local HTML explorer; bundled data synthetic | `05-star-identity-explorer.pyz` |

## Validation performed

- `python -m compileall -q src tests`: passed.
- Earlier consolidation run: 63 passed; 2 modules skipped because that environment lacked `astropy` and `hypothesis`. A fresh merged-tree test result is recorded below after the current build.
- Acquisition archive smoke test: passed; generated a source manifest and SHA-256.
- Validator archive smoke test: passed on the included synthetic fixture (12 rows: 5 accepted, 2 review, 5 rejected).
- Cross-matching archive: rebuilt from the matching package; synthetic demo and bundle verification are covered by tests. Real catalogue validation remains pending.
- Identity Explorer archive: passed; generated a self-contained HTML page with its synthetic-data warning and embedded provenance.
- Coordinate archive: package compiles; runtime smoke test correctly reports missing Astropy dependency. Install runtime dependencies with `pip install numpy astropy` before running it.

## Important limits

The `.pyz` files are single-file application archives, not self-contained Python runtimes. They require Python 3.12+; the Coordinate Lab additionally requires NumPy and Astropy. No catalogue data was fabricated or downloaded. No cross-match capability was invented.


## Current merged-tree verification — 2026-11-19

- Merged the latest Cross-Matching snapshot with the Phase 3/4 CLI and wheel-packaging fixes.
- Preserved module 03 as **UNVERIFIED** pending real BSC, Hipparcos and Gaia validation.
- `PYTHONPATH=src python -m compileall -q src tests`: passed.
- `PYTHONPATH=src python -m pytest -ra`: **164 passed, 3 skipped**. The skips are the Astropy
  coordinate suite, the Hypothesis property suite, and the coordinate CLI smoke test because
  Astropy/Hypothesis are not installed in this build environment.
- Rebuilt all five `.pyz` archives from the merged source. Acquisition, validator and synthetic
  cross-match smoke tests passed; the explorer generated a page successfully. The coordinate
  archive correctly reports its missing Astropy dependency in this environment.
- Built a wheel and installed it into a clean virtual environment; the installed `adw explorer`
  command successfully loaded the bundled HTML/JSON package data.
- Ruff and strict MyPy were not rerun here because those executables are unavailable in this
  environment; the corresponding CI steps remain configured.

## 0.1.3 verification — 2026-11-19

- Version 0.1.3. Ruff clean, strict MyPy clean (41 source files), 185 tests passed, 0 skipped
  (Astropy and Hypothesis installed).
- All five `.pyz` archives rebuilt; clean-venv wheel install verified. See `RELEASE_NOTES-0.1.3.md`.
- The "Ruff and strict MyPy were not rerun" note above is superseded by this section.

## 0.1.4 verification - 2026-11-20

See `RELEASE_NOTES-0.1.4.md`. Behaviour change: negative parallax is info, not review.
