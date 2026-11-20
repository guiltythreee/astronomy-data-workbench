# Coordinate Accuracy Laboratory (Tool 04)

**Status: partially built (Phase 3).** Propagation, frames, horizontal coordinates,
nutation/aberration and refraction are checked. Topocentric parallax is not.

The lab compares ADW's *independent* implementations of astronomy formulas against
published examples and against Astropy, and records residuals with stated tolerances.
Results are data in a JSON report. A tolerance is a statement about how far two
approximate models are allowed to disagree. It is not a claim of proven accuracy.

## Run it

    python -m astronomy_data_workbench.coordinates --out coords-lab-report.json

Exit code 0 means no gated check failed; 1 means at least one did. The report lists every
check (residual, unit, tolerance, pass/fail, note), the Python/Astropy/NumPy versions, and
a `content_sha256` over everything except the run timestamp.

## Conventions the lab enforces

- BSC proper motion arrives in arcsec/yr. RA motion is already mu_alpha* (includes cos dec).
  Conversion to mas/yr is x1000 only; cos dec is never applied again.
- Any other RA motion must declare whether it includes cos dec. There is no default.
- FK5 (J2000) and ICRS are different frames and are never treated as the same.
- Refraction is a separate effect and is never folded into geometric altitude.
- UT1-UTC is an explicit input. It is never guessed.

## Suites and tolerances (25 checks)

| Suite | Check | Tolerance | Why this tolerance |
|---|---|---|---|
| propagation_and_frames (6) | Rigorous space-motion propagation vs Astropy, 2 stars x 2 epochs (J1991.25, J2016.0) | 0.1 mas | Same model written independently. An extreme-proper-motion star shows about 0.03 mas; cause not confirmed (possibly relativistic terms in Astropy). |
| | Linear propagation vs Astropy (informational) | 1 mas | Not gated. Fails on purpose (about 165 mas) to show linear propagation is unsafe for high proper motion. |
| | FK5(J2000) to ICRS offset | 0 < offset < 100 mas | Sanity bound only (about 30 mas observed). Guards against conflating the frames. |
| horizontal_mean_place (7) | GMST vs Meeus ex. 12.a | 0.01 arcsec | Published value. |
| | Altitude and azimuth vs Meeus ex. 13.b | 1 arcsec each | Published value. |
| | Mean-place pipeline vs Astropy (2 stars, alt and az) | 60 arcsec | Pipeline omits nutation, aberration and UT1-UTC. Deliberately loose. |
| apparent_place (8) | Nutation vs Meeus ex. 22.a | 0.2 arcsec | 4-term series against a full-theory value. |
| | Apparent-place altitude/azimuth vs Astropy (3 stars) | 2 arcsec | Residuals observed below 0.6 arcsec. The rest covers diurnal aberration and light deflection, which were not tested individually. |
| refraction (4) | Horizon refraction vs standard 34.5 arcmin | 1 arcmin | Real horizon refraction varies with weather. |
| | Zenith refraction | 0.01 arcmin | Formula constant makes it vanish. |
| | Saemundsson/Bennett round trip, 5-89 deg | 5 arcsec | Two approximate models; not an exact inverse. |
| | 40 sky positions vs Astropy, alt 10-85 deg | 12 arcsec | Mine runs about 5% larger. Both are approximate; which is closer to real conditions is unresolved. |

## Known limits

- Test star values (a Barnard's Star-like and a Sirius-like entry) are realistic inputs, not
  authoritative data. Residuals compare two calculations on the same input.
- Astropy is the main comparison source. It is mature but not the final authority. A second
  independent reference (SOFA, published test vectors) would strengthen the lab.
- UT1-UTC for 2026-11-16 comes from Astropy's predicted tables. Measured data may differ.
- Sky positions and the test date are fixed so runs are reproducible.
- Not covered: topocentric versus geocentric parallax (relevant to the Moon and planets,
  not stars), light deflection, diurnal aberration, and refraction near the horizon.
- Nothing here validates the BSC parser. That still needs a real BSC export.
