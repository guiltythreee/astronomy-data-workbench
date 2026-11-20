"""Schema conventions for the VizieR I/311/hip2 (Hipparcos-2) TSV export."""

SCHEMA_VERSION = "hipparcos-2-vizier-tsv/1"
SOURCE_NAME = "Hipparcos-2, VizieR I/311/hip2"
REQUIRED_COLUMNS = ("HIP", "RArad", "DErad")
EXPECTED_COLUMNS = (
    "HIP", "RArad", "e_RArad", "DErad", "e_DErad", "Plx", "e_Plx",
    "pmRA", "e_pmRA", "pmDE", "e_pmDE", "Hpmag", "e_Hpmag", "B-V", "e_B-V", "HIP1",
)
EPOCH_JYEAR = 1991.25
FRAME = "ICRS"
POSITION_UNITS = "deg"
ASTROMETRIC_ERROR_UNITS = "mas"
PROPER_MOTION_UNITS = "mas/yr"
