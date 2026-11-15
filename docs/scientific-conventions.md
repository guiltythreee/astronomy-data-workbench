# Scientific conventions (BSC)

- **Frame/epoch:** FK5, equinox J2000, epoch J2000.0. Not reinterpreted as 1991.25.
- **Proper motion:** arcsec/yr in the source. RA component is mu_alpha* (already times cos dec).
  Converted to mas/yr by x1000 only.
- **Parallax:** arcsec in the source; converted to mas by x1000.
- **Radial velocity:** km/s, unchanged.
- **Photometry:** Vmag recorded with passband "Johnson V". Never merged with Gaia G.
- **Coordinates:** RA as `HH MM SS.s` (hours) or decimal degrees; Dec as `+DD MM SS` or decimal
  degrees. The sign applies to the whole declination (so `-00 30 12` is negative).
  A bare integer is read as decimal degrees.
