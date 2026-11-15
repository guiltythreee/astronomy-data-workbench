# Data sources

| Source | Role | Status in ADW |
|---|---|---|
| Bright Star Catalogue (BSC), CDS V/50 | first ingestion target | Phase 1: VizieR TSV export |
| Hipparcos, I/239 | astrometry cross-check (ICRS, J1991.25) | Phase 2 |
| Gaia DR3 | high-precision astrometry (ICRS, J2016.0; G is not V) | Phase 2 |

## Licensing

Raw catalogue files are not committed. Record `--licence-status` for each export; the default
is `unverified`. A mirror's licence does not establish the original source's licence.

## BSC format notes

- The CDS fixed-width record (197 bytes) is a different format from a VizieR TSV export. Byte
  offsets must not be applied to the TSV.
- Expected TSV columns: HR, Name, HD, RAJ2000, DEJ2000, Vmag, pmRA, pmDE, Parallax, RadVel.
  Confirm headers and null markers on your real file with `adw inspect`.
- The catalogue has 9,110 rows including 14 non-stellar entries; not every row is a star.
