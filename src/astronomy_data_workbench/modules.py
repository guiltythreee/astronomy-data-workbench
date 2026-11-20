"""Registry of the five named ADW modules, their descriptions and current build status.

This is the single source of truth for `adw modules` and is checked against docs/modules.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

AVAILABLE = "available"
PARTIAL = "partial"
PLANNED = "planned"


@dataclass(frozen=True)
class ToolModule:
    number: str
    name: str
    description: str
    responsibilities: tuple[str, ...]
    package: str
    command: str | None
    priority: int
    status: str
    status_note: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["responsibilities"] = list(self.responsibilities)
        return data


MODULES: tuple[ToolModule, ...] = (
    ToolModule(
        number="01",
        name="Catalogue Acquisition Manager",
        description=(
            "Controls source discovery and retrieval, and records exactly where each file came "
            "from so every output can be traced back to its input."
        ),
        responsibilities=(
            "Record source name, URL/archive ID, catalogue release and retrieval time",
            "Record licence/redistribution status (default: unverified)",
            "Compute a SHA-256 checksum of the untouched source file",
            "Support local-file ingestion when automated retrieval is unavailable",
        ),
        package="provenance",
        command="adw export (writes the manifest into audit.json)",
        priority=1,
        status=PARTIAL,
        status_note="Local-file manifest + SHA-256 implemented; automated download not built.",
    ),
    ToolModule(
        number="02",
        name="Star Catalogue Validator",
        description=(
            "Inspects a catalogue file's schema and checks every record, sorting rows into "
            "accepted, rejected and manual-review with row-level reasons."
        ),
        responsibilities=(
            "Check required columns, malformed rows, duplicate IDs and null conventions",
            "Check RA/Dec ranges and suspicious magnitudes, proper motions, parallaxes, RVs",
            "Keep frame, equinox, epoch, units and passband explicit",
            "Never silently repair or coerce data; keep raw values beside normalized ones",
        ),
        package="sources/bsc, sources/hipparcos, schemas, inspection, validation, export",
        command="adw inspect | validate bsc-tsv | validate hip2-tsv | export bsc-tsv | audit",
        priority=1,
        status=AVAILABLE,
        status_note=("BSC (V/50) parser/validator checked against a real export; Hipparcos-2 validator "
                      "implemented with synthetic tests; real I/311/hip2 validation pending."),
    ),
    ToolModule(
        number="03",
        name="Astronomical Cross-Matching Workbench",
        description=(
            "Links the same object across BSC, Hipparcos, Gaia and later catalogues using "
            "evidence, not just nearest angular distance."
        ),
        responsibilities=(
            "Use trusted catalogue association tables where available",
            (
                "Otherwise compare epoch-propagated positions plus magnitude, colour, parallax, "
                "proper motion, multiplicity and quality flags"
            ),
            "Keep candidate alternatives with confidence scores and evidence",
            "Never silently accept an uncertain pair",
        ),
        package="matching",
        command="adw crossmatch run | demo | verify",
        priority=2,
        status=PARTIAL,
        status_note=(
            "UNVERIFIED. Epoch-corrected positional matching, preserved candidates, manual-review "
            "routing and evidence records are built and tested on SYNTHETIC data only; not "
            "validated against real BSC, Hipparcos or Gaia records."
        ),
    ),
    ToolModule(
        number="04",
        name="Coordinate Accuracy Laboratory",
        description=(
            "Tests coordinate and astrometric transformations against independent references "
            "and reports numerical residuals with stated tolerances."
        ),
        responsibilities=(
            "Frame handling (FK5 vs ICRS), epoch propagation, proper motion, parallax, RV",
            "Precession/nutation, equatorial-to-horizontal, topocentric vs geocentric",
            "Treat atmospheric refraction as a separate effect",
            "Compare with independent implementations or published reference cases",
        ),
        package="coordinates",
        command="adw coords-lab",
        priority=2,
        status=PARTIAL,
        status_note="Phase 3 reference suites and CLI implemented; requires NumPy/Astropy and further real-data validation.",
    ),
    ToolModule(
        number="05",
        name="Star Identity Explorer",
        description=(
            "A human-facing view of one object: its identifiers, measurements, provenance, "
            "match alternatives and validation state, with uncertainty shown, not hidden."
        ),
        responsibilities=(
            "Show HR / HD / HIP / Gaia IDs as separate typed identifiers",
            "Show source measurements with epochs, frames, units and passbands",
            "Show cross-match alternatives, quality flags and provenance",
            "Present validated data only; it never changes the data",
        ),
        package="identity",
        command="adw explorer",
        priority=3,
        status=PARTIAL,
        status_note="Phase 4 local HTML explorer implemented; current bundled records are explicitly synthetic and matching is not integrated.",
    ),
)
