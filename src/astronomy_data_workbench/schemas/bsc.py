"""Schema and scientific conventions for the BSC (CDS V/50) VizieR TSV export.

Header names and null markers must still be checked against the real file with `adw inspect`.
The 197-byte fixed-width CDS record layout does NOT apply to this tab-separated export.
"""

SCHEMA_VERSION = "bsc-vizier-tsv/1"
SOURCE_NAME = "Bright Star Catalogue (BSC), CDS V/50"

REQUIRED_COLUMNS = ("HR", "RAJ2000", "DEJ2000")
EXPECTED_COLUMNS = (
    "HR", "Name", "HD", "RAJ2000", "DEJ2000", "Vmag", "pmRA", "pmDE", "Parallax", "RadVel",
)  # fmt: skip
NUMERIC_OPTIONAL = ("Vmag", "pmRA", "pmDE", "Parallax", "RadVel")

# Position: FK5, equinox J2000, epoch J2000.0 (not 1991.25).
FRAME = "FK5"
EQUINOX = "J2000"
EPOCH = "J2000.0"

# Source units. pmRA is already mu_alpha* (includes cos(dec)): never multiply by cos(dec) again.
SOURCE_UNITS = {
    "pmRA": "arcsec/yr",
    "pmDE": "arcsec/yr",
    "Parallax": "arcsec",
    "RadVel": "km/s",
    "Vmag": "mag",
}
ARCSEC_TO_MAS = 1000.0  # the only conversion applied to pm and parallax (explicit)
PM_RA_CONVENTION = "mu_alpha_star (already includes cos(dec))"
PASSBAND = "Johnson V"
