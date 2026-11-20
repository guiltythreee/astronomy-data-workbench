## Unreleased: Coordinate Accuracy Laboratory (Phase 3, partial)

Added (`coordinates/`):
- conventions.py: explicit BSC proper-motion unit conversion (no second cos dec).
- propagation.py: independent rigorous and linear epoch propagation.
- horizontal.py: sidereal time, precession, equatorial to horizontal (Meeus).
- apparent.py: nutation, annual aberration, apparent-place pipeline (Meeus).
- refraction.py: Saemundsson and Bennett refraction as a separate effect.
- reference.py / lab.py: 25 checks with stated tolerances; JSON report with content checksum.

Assumptions in this release:
- Compared mainly against Astropy 8.0.2 / NumPy 2.5.4; one reference library only.
- UT1-UTC is taken from predicted IERS data for the test date.
- Tolerances are stated in docs/coordinates-lab.md; the 0.03 mas gap for extreme
  proper motion and the 5% refraction difference from Astropy are unresolved.

Not included: topocentric parallax, `adw coords-lab` wiring into the main CLI.
