# Changelog

## 0.1.4
See `RELEASE_NOTES-0.1.4.md`. 0.1.3 is unchanged and remains reproducible.
- Validation policy: a negative measured parallax is no longer a review trigger. `PARALLAX_NEGATIVE`
  is now an *info* diagnostic; the signed value is kept (never clamped) and the row's outcome is
  decided by its other issues. Checked on a real BSC V/50 export: the 164 negative-parallax rows
  (5% of the 3,289 parallaxes) moved from review to accepted (9,096 accepted, 0 review, 14 rejected).

## 0.1.3
One consolidated release of the five ADW modules. See `RELEASE_NOTES-0.1.3.md`.

- Cross-Matching Workbench (module 03), **UNVERIFIED**: epoch-corrected positional matching,
  preserved multiple candidates, manual-review routing (ambiguous, binary, duplicate, conflicting,
  uncorrected or inconsistent pairs), no silent acceptance of low confidence, and recorded evidence,
  uncertainty and provenance. `adw crossmatch run | demo | verify`; docs in `docs/crossmatching.md`.
- Synthetic scenarios for binaries, duplicates, high proper motion and positional ambiguity.
- UNVERIFIED status shown in the CLI, every output file, the Identity Explorer and the docs.
- Coordinate Accuracy Laboratory (`adw coords-lab`) and Star Identity Explorer (`adw explorer`)
  restored alongside `adw crossmatch` in the main CLI; module status metadata corrected.
- Explorer HTML/JSON assets are packaged in the wheel and loaded through `importlib.resources`
  (works from the `.pyz` archives); installed-wheel smoke test added to CI.
- NumPy/Astropy declared as runtime dependencies and imported lazily so unrelated commands do not
  need them; strict MyPy configured for Astropy's untyped interfaces.
- Lint clean under the current Ruff default rule set; strict MyPy clean.
- Five `.pyz` launchers rebuilt from the merged source (module 03 now runs the real matching CLI).
- Still synthetic-only: no real BSC, Hipparcos or Gaia validation has been done.

## 0.1.2
- The five named modules are now explicit: `modules.py` registry, `docs/modules.md`, README
  table and an `adw modules` command (descriptions, responsibilities, priority, status).
- Placeholder packages `matching/`, `coordinates/`, `identity/` (documented as planned, empty by
  design). A test enforces that nothing is built in them before its phase.

## 0.1.1
- Property-based tests (Hypothesis): coordinate ranges, declination sign symmetry, parsers never
  return NaN/inf, validator never crashes and never leaves a non-accepted row without a reason.
- Test for real-world file quirks (padded header/cells, multiple spaces in coordinates, trailing
  blank lines).
- `.gitattributes` keeps line endings consistent on Windows.

## 0.1.0
First working release (Phase 0 + Phase 1).

Supported assumptions (verify against your real file with `adw inspect`):
- Input: UTF-8, tab-separated VizieR export of BSC (CDS V/50); optional `#` comments, then a
  header row, then optional units row and `----` row. Not the 197-byte fixed-width CDS file.
- Required columns: HR, RAJ2000, DEJ2000. Expected: Name, HD, Vmag, pmRA, pmDE, Parallax, RadVel.
- Null marker: empty cell only, unless `--null-marker` is given.
- Position FK5 / J2000 / epoch J2000.0; pm in arcsec/yr with RA component = mu_alpha*;
  parallax in arcsec; radial velocity in km/s; Vmag = Johnson V.
- Not yet tested on a real, licence-permitted BSC export (only a synthetic fixture).


## Unreleased

- Add a Hipparcos-2 (VizieR I/311/hip2) TSV validator with explicit ICRS/J1991.25 metadata,
  signed-parallax handling, uncertainty checks, duplicate HIP detection, and JSONL row output.
- Preserve extreme proper motions rather than applying an arbitrary hard maximum; accept zero
  photometric-colour uncertainty.
- Add synthetic tests for observed Hipparcos-2 schema edge cases. Real-export validation remains
  pending; cross-matching remains UNVERIFIED.
