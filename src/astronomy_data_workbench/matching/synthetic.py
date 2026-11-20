"""Deterministic SYNTHETIC cross-matching scenarios with stated expected outcomes.

Everything here is invented. It exists so the matching logic can be built and tested without a
real BSC, Hipparcos or Gaia file. Passing these scenarios says the code does what it is
designed to do; it says nothing about how well it matches real catalogues (UNVERIFIED).

Each scenario sits in its own patch of sky so all of them can be run together as one demo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from astronomy_data_workbench.matching.epoch import propagate_entry
from astronomy_data_workbench.matching.geometry import (
    MAS_TO_RAD,
    tangent_basis,
    to_ra_dec,
    unit_vector,
)
from astronomy_data_workbench.matching.models import (
    ACCEPTED,
    ALL_CANDIDATES_IMPLAUSIBLE,
    AMBIGUOUS_CANDIDATES,
    EPOCH_UNCORRECTED,
    LOW_CONFIDENCE,
    MAG_INCONSISTENT,
    NO_CANDIDATES,
    PARALLAX_INCONSISTENT,
    PM_INCONSISTENT,
    POSITION_INCONSISTENT,
    POSSIBLE_DUPLICATE_REFERENCE,
    POSSIBLE_MULTIPLE,
    RECIPROCAL_CONFLICT,
    REJECTED,
    REVIEW,
    UNMATCHED,
    Catalogue,
    CatalogueEntry,
    MatchConfig,
)

GENERATOR_VERSION = "1"
PRIMARY_NAME = "SYN-PRIMARY"  # BSC-like: epoch 2000.0, FK5, poorer positions
REFERENCE_NAME = "SYN-REFERENCE"  # Hipparcos-like: epoch 1991.25, ICRS, good positions
PRIMARY_EPOCH = 2000.0
REFERENCE_EPOCH = 1991.25
PRIMARY_POS_ERR_MAS = 400.0
REFERENCE_POS_ERR_MAS = 5.0
_CFG = MatchConfig()


@dataclass(frozen=True)
class Expectation:
    decision: str
    reasons: tuple[str, ...] = ()  # reasons that must be present
    top: str | None = None  # expected best candidate id
    min_candidates: int = 0


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    primary: tuple[CatalogueEntry, ...]
    reference: tuple[CatalogueEntry, ...]
    expected: dict[str, Expectation] = field(default_factory=dict)


def shift(ra_deg: float, dec_deg: float, east_mas: float, north_mas: float) -> tuple[float, float]:
    """Move a point by a small tangent-plane offset in mas (safe at the poles)."""
    p, east, north = tangent_basis(ra_deg, dec_deg)
    return to_ra_dec(p + (east_mas * east + north_mas * north) * MAS_TO_RAD)


def place_at_epoch(
    truth_ra: float,
    truth_dec: float,
    entry_epoch: float,
    pm_ra_cosdec: float,
    pm_dec: float,
    common_epoch: float = REFERENCE_EPOCH,
) -> tuple[float, float]:
    """Catalogued position at `entry_epoch` that propagates to (truth_ra, truth_dec) at
    `common_epoch` under this package's own space-motion model."""
    target = unit_vector(truth_ra, truth_dec)
    ra, dec = truth_ra, truth_dec
    for _ in range(6):
        probe = CatalogueEntry("T", "T", ra, dec, entry_epoch, 1.0, pm_ra_cosdec, pm_dec)
        forward = propagate_entry(probe, common_epoch, _CFG).vector
        _, east, north = tangent_basis(ra, dec)
        err = target - forward
        ra, dec = shift(ra, dec, float(err @ east) / MAS_TO_RAD, float(err @ north) / MAS_TO_RAD)
    return ra, dec


def _p(tag: str, suffix: str, ra: float, dec: float, **kw: object) -> CatalogueEntry:
    """Primary (BSC-like) entry; `ra`/`dec` are the catalogued position at epoch 2000.0."""
    base: dict[str, object] = {
        "epoch": PRIMARY_EPOCH, "pos_err_mas": PRIMARY_POS_ERR_MAS, "frame": "FK5",
        "passband": "Johnson V", "synthetic": True,
    }  # fmt: skip
    base.update(kw)
    return CatalogueEntry(PRIMARY_NAME, f"{tag}-{suffix}", ra, dec, **base)  # type: ignore[arg-type]


def _r(tag: str, suffix: str, ra: float, dec: float, **kw: object) -> CatalogueEntry:
    """Reference (Hipparcos-like) entry; `ra`/`dec` are the catalogued position at 1991.25."""
    base: dict[str, object] = {
        "epoch": REFERENCE_EPOCH, "pos_err_mas": REFERENCE_POS_ERR_MAS, "frame": "ICRS",
        "passband": "Hipparcos Hp", "synthetic": True,
    }  # fmt: skip
    base.update(kw)
    return CatalogueEntry(REFERENCE_NAME, f"{tag}-{suffix}", ra, dec, **base)  # type: ignore[arg-type]


def _primary_at(truth_ra: float, truth_dec: float, east: float, north: float,
                pm: tuple[float, float]) -> tuple[float, float]:  # fmt: skip
    """Primary position at 2000.0 so that, once corrected to 1991.25, it sits at truth + offset."""
    ra, dec = shift(truth_ra, truth_dec, east, north)
    return place_at_epoch(ra, dec, PRIMARY_EPOCH, pm[0], pm[1])


def _clean() -> Scenario:
    ra, dec, pm = 20.0, 25.0, (80.0, -30.0)
    pra, pdec = _primary_at(ra, dec, 60.0, -40.0, pm)
    return Scenario(
        "clean", "Isolated star; positions agree after epoch correction.",
        (_p("CLEAN", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, parallax_mas=20.0, parallax_err_mas=1.0, mag=5.0),),
        (_r("CLEAN", "R", ra, dec, pm_ra_cosdec_mas_yr=82.0, pm_dec_mas_yr=-28.0,
            pm_err_mas_yr=1.0, parallax_mas=20.5, parallax_err_mas=1.0, mag=5.05),),
        {"CLEAN-P": Expectation(ACCEPTED, top="CLEAN-R", min_candidates=1)},
    )  # fmt: skip


def _high_proper_motion() -> Scenario:
    ra, dec, pm = 45.0, -30.0, (1200.0, -800.0)
    pra, pdec = _primary_at(ra, dec, 30.0, 20.0, pm)
    return Scenario(
        "high_proper_motion",
        "Fast mover (1.44 arcsec/yr, ~12.6 arcsec over the epoch gap). A decoy sits at the "
        "star's UNcorrected catalogued position, so a naive nearest-neighbour match would pick it.",
        (_p("HPM", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, parallax_mas=60.0, parallax_err_mas=1.0, mag=6.0),),
        (_r("HPM", "R", ra, dec, pm_ra_cosdec_mas_yr=1195.0, pm_dec_mas_yr=-805.0,
            pm_err_mas_yr=1.0, parallax_mas=60.5, parallax_err_mas=1.0, mag=6.1),
         _r("HPM", "DECOY", pra, pdec, pm_ra_cosdec_mas_yr=5.0, pm_dec_mas_yr=3.0,
            pm_err_mas_yr=1.0, parallax_mas=2.0, parallax_err_mas=1.0, mag=9.0)),
        {"HPM-P": Expectation(ACCEPTED, top="HPM-R", min_candidates=1)},
    )  # fmt: skip


def _polar() -> Scenario:
    ra, dec, pm = 300.0, 89.95, (500.0, 200.0)
    pra, pdec = _primary_at(ra, dec, -50.0, 30.0, pm)
    return Scenario(
        "polar", "High proper motion very close to the celestial pole (no 1/cos(dec) blow-up).",
        (_p("POLAR", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=6.5),),
        (_r("POLAR", "R", ra, dec, pm_ra_cosdec_mas_yr=498.0, pm_dec_mas_yr=203.0,
            pm_err_mas_yr=1.0, mag=6.6),),
        {"POLAR-P": Expectation(ACCEPTED, top="POLAR-R", min_candidates=1)},
    )  # fmt: skip


def _ra_wrap() -> Scenario:
    return Scenario(
        "ra_wrap", "Pair straddling RA = 0/360 degrees.",
        (_p("WRAP", "P", 359.99995, 2.0, pm_ra_cosdec_mas_yr=0.0, pm_dec_mas_yr=0.0,
            pm_err_mas_yr=10.0, mag=5.5),),
        (_r("WRAP", "R", 0.00005, 2.0, pm_ra_cosdec_mas_yr=0.0, pm_dec_mas_yr=0.0,
            pm_err_mas_yr=1.0, mag=5.5),),
        {"WRAP-P": Expectation(ACCEPTED, top="WRAP-R", min_candidates=1)},
    )  # fmt: skip


def _missing_pm() -> Scenario:
    ra, dec, pm = 70.0, 5.0, (900.0, -400.0)
    # The primary has no proper motion, so its 2000.0 position cannot be brought back to 1991.25.
    pra, pdec = place_at_epoch(ra, dec, PRIMARY_EPOCH, pm[0], pm[1])
    return Scenario(
        "missing_pm", "Fast mover whose primary entry has no proper motion: cannot be corrected.",
        (_p("NOPM", "P", pra, pdec, mag=7.0),),
        (_r("NOPM", "R", ra, dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=7.1),),
        {"NOPM-P": Expectation(REVIEW, (EPOCH_UNCORRECTED,), top="NOPM-R", min_candidates=1)},
    )  # fmt: skip


def _binary() -> Scenario:
    ra, dec, pm = 95.0, 40.0, (40.0, 10.0)
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, pm)
    ra_a, dec_a = shift(ra, dec, -800.0, 0.0)
    ra_b, dec_b = shift(ra, dec, 800.0, 0.0)
    return Scenario(
        "binary",
        "Unresolved double in the primary (one entry, V=4.0); the reference resolves two "
        "components 1.6 arcsec apart (4.6 + 5.0 combine to ~4.03).",
        (_p("BIN", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=4.0),),
        (_r("BIN", "A", ra_a, dec_a, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=4.6),
         _r("BIN", "B", ra_b, dec_b, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=5.0)),
        {"BIN-P": Expectation(REVIEW, (POSSIBLE_MULTIPLE, AMBIGUOUS_CANDIDATES), min_candidates=2)},
    )  # fmt: skip


def _duplicate_reference() -> Scenario:
    ra, dec, pm = 120.0, -10.0, (-60.0, 25.0)
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, pm)
    ra_b, dec_b = shift(ra, dec, 150.0, 0.0)
    return Scenario(
        "duplicate_reference", "The reference lists the same star twice, 0.15 arcsec apart.",
        (_p("DUPR", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=6.2),),
        (_r("DUPR", "A", ra, dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=6.2),
         _r("DUPR", "B", ra_b, dec_b, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=6.2)),
        {"DUPR-P": Expectation(REVIEW, (POSSIBLE_DUPLICATE_REFERENCE,), min_candidates=2)},
    )  # fmt: skip


def _duplicate_query() -> Scenario:
    ra, dec, pm = 145.0, 60.0, (10.0, 5.0)
    pa_ra, pa_dec = _primary_at(ra, dec, 0.0, 0.0, pm)
    pb_ra, pb_dec = _primary_at(ra, dec, 200.0, 0.0, pm)
    return Scenario(
        "duplicate_query", "Two primary entries (0.2 arcsec apart) claim the same reference star.",
        (_p("DUPQ", "P1", pa_ra, pa_dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=6.0),
         _p("DUPQ", "P2", pb_ra, pb_dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=6.0)),
        (_r("DUPQ", "R", ra, dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=6.0),),
        {"DUPQ-P1": Expectation(REVIEW, (RECIPROCAL_CONFLICT,), top="DUPQ-R", min_candidates=1),
         "DUPQ-P2": Expectation(REVIEW, (RECIPROCAL_CONFLICT,), top="DUPQ-R", min_candidates=1)},
    )  # fmt: skip


def _ambiguous() -> Scenario:
    ra, dec, pm = 170.0, 15.0, (20.0, 20.0)
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, pm)
    ra_a, dec_a = shift(ra, dec, -3000.0, 0.0)
    ra_b, dec_b = shift(ra, dec, 3000.0, 0.0)
    ra_c, dec_c = shift(ra, dec, 0.0, 11000.0)
    same = {"pm_ra_cosdec_mas_yr": pm[0], "pm_dec_mas_yr": pm[1], "pm_err_mas_yr": 1.0, "mag": 6.0}
    return Scenario(
        "positional_ambiguity",
        "Poor primary position (3 arcsec): two equally good references 6 arcsec apart plus a "
        "distant third. Nothing but position separates them.",
        (_p("AMB", "P", pra, pdec, pos_err_mas=3000.0, pm_ra_cosdec_mas_yr=pm[0],
            pm_dec_mas_yr=pm[1], pm_err_mas_yr=10.0, mag=6.0),),
        (_r("AMB", "R1", ra_a, dec_a, **same), _r("AMB", "R2", ra_b, dec_b, **same),
         _r("AMB", "R3", ra_c, dec_c, **same)),
        {"AMB-P": Expectation(REVIEW, (AMBIGUOUS_CANDIDATES, LOW_CONFIDENCE), min_candidates=3)},
    )  # fmt: skip


def _marginal() -> Scenario:
    ra, dec, pm = 320.0, 45.0, (30.0, 30.0)
    pra, pdec = _primary_at(ra, dec, 1500.0, 0.0, pm)
    return Scenario(
        "marginal", "A single candidate, but 3.7 sigma away: low confidence must not be accepted.",
        (_p("MARG", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=6.0),),
        (_r("MARG", "R", ra, dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=6.0),),
        {"MARG-P": Expectation(REVIEW, (POSITION_INCONSISTENT, LOW_CONFIDENCE),
                               top="MARG-R", min_candidates=1)},
    )  # fmt: skip


def _no_counterpart() -> Scenario:
    return Scenario(
        "no_counterpart", "No reference object anywhere near.",
        (_p("LONE", "P", 195.0, -55.0, pm_ra_cosdec_mas_yr=0.0, pm_dec_mas_yr=0.0,
            pm_err_mas_yr=10.0, mag=6.0),),
        (),
        {"LONE-P": Expectation(UNMATCHED, (NO_CANDIDATES,))},
    )  # fmt: skip


def _implausible() -> Scenario:
    ra, dec, pm = 220.0, 35.0, (15.0, -10.0)
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, pm)
    ra_n, dec_n = shift(ra, dec, 0.0, 2800.0)
    return Scenario(
        "implausible_neighbour",
        "Precise positions disagree by 2.8 arcsec: an unrelated chance neighbour.",
        (_p("NEAR", "P", pra, pdec, pos_err_mas=50.0, pm_ra_cosdec_mas_yr=pm[0],
            pm_dec_mas_yr=pm[1], pm_err_mas_yr=1.0, mag=6.0),),
        (_r("NEAR", "R", ra_n, dec_n, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=6.0),),
        {"NEAR-P": Expectation(REJECTED, (ALL_CANDIDATES_IMPLAUSIBLE,), min_candidates=1)},
    )  # fmt: skip


def _pm_conflict() -> Scenario:
    ra, dec = 245.0, -20.0
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, (300.0, 0.0))
    return Scenario(
        "pm_conflict", "Positions agree but the proper motions strongly disagree.",
        (_p("PMC", "P", pra, pdec, pm_ra_cosdec_mas_yr=300.0, pm_dec_mas_yr=0.0,
            pm_err_mas_yr=10.0, mag=6.0),),
        (_r("PMC", "R", ra, dec, pm_ra_cosdec_mas_yr=0.0, pm_dec_mas_yr=0.0,
            pm_err_mas_yr=1.0, mag=6.0),),
        {"PMC-P": Expectation(REVIEW, (PM_INCONSISTENT,), top="PMC-R", min_candidates=1)},
    )  # fmt: skip


def _parallax_conflict() -> Scenario:
    ra, dec, pm = 270.0, 70.0, (10.0, 10.0)
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, pm)
    return Scenario(
        "parallax_conflict", "Positions and motions agree but the parallaxes do not.",
        (_p("PLX", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, parallax_mas=50.0, parallax_err_mas=1.0, mag=6.0),),
        (_r("PLX", "R", ra, dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, parallax_mas=5.0, parallax_err_mas=1.0, mag=6.0),),
        {"PLX-P": Expectation(REVIEW, (PARALLAX_INCONSISTENT,), top="PLX-R", min_candidates=1)},
    )  # fmt: skip


def _mag_conflict() -> Scenario:
    ra, dec, pm = 295.0, -70.0, (10.0, 10.0)
    pra, pdec = _primary_at(ra, dec, 0.0, 0.0, pm)
    return Scenario(
        "mag_conflict", "Positions agree but the magnitudes differ by 3.",
        (_p("MAG", "P", pra, pdec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=10.0, mag=3.0),),
        (_r("MAG", "R", ra, dec, pm_ra_cosdec_mas_yr=pm[0], pm_dec_mas_yr=pm[1],
            pm_err_mas_yr=1.0, mag=6.0),),
        {"MAG-P": Expectation(REVIEW, (MAG_INCONSISTENT,), top="MAG-R", min_candidates=1)},
    )  # fmt: skip


SCENARIO_BUILDERS = (
    _clean, _high_proper_motion, _polar, _ra_wrap, _missing_pm, _binary, _duplicate_reference,
    _duplicate_query, _ambiguous, _marginal, _no_counterpart, _implausible, _pm_conflict,
    _parallax_conflict, _mag_conflict,
)  # fmt: skip


def all_scenarios() -> list[Scenario]:
    return [build() for build in SCENARIO_BUILDERS]


def _provenance(role: str) -> dict[str, object]:
    return {
        "origin": "synthetic scenario generator",
        "generator_version": GENERATOR_VERSION,
        "role": role,
        "synthetic": True,
        "note": "Invented values. Not real catalogue data.",
    }


def demo_catalogues() -> tuple[Catalogue, Catalogue, dict[str, Expectation]]:
    """All scenarios merged into one primary and one reference catalogue, plus expectations."""
    scenarios = all_scenarios()
    primary = tuple(e for s in scenarios for e in s.primary)
    reference = tuple(e for s in scenarios for e in s.reference)
    expected = {k: v for s in scenarios for k, v in s.expected.items()}
    return (
        Catalogue(PRIMARY_NAME, primary, synthetic=True, provenance=_provenance("primary")),
        Catalogue(REFERENCE_NAME, reference, synthetic=True, provenance=_provenance("reference")),
        expected,
    )


def scenario_catalogues(scenario: Scenario) -> tuple[Catalogue, Catalogue]:
    """One scenario as catalogues. An empty reference gets a far-away filler so it is valid."""
    reference = scenario.reference or (
        _r("FILLER", "R", 0.0, -89.0, pm_ra_cosdec_mas_yr=0.0, pm_dec_mas_yr=0.0, mag=9.0),
    )
    return (
        Catalogue(PRIMARY_NAME, scenario.primary, True, _provenance("primary")),
        Catalogue(REFERENCE_NAME, reference, True, _provenance("reference")),
    )


def separation_check(a: CatalogueEntry, b: CatalogueEntry) -> float:
    """Raw separation in arcsec between two catalogued positions (no epoch correction)."""
    from astronomy_data_workbench.matching.geometry import separation_mas

    return separation_mas(unit_vector(a.ra_deg, a.dec_deg), unit_vector(b.ra_deg, b.dec_deg)) / 1000.0


__all__ = [
    "Expectation", "Scenario", "all_scenarios", "demo_catalogues", "place_at_epoch",
    "scenario_catalogues", "separation_check", "shift",
]  # fmt: skip
