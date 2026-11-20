"""Data model for the Cross-Matching Workbench (module 03).

Every structure here carries the validation status. Cross-matching has only been exercised on
synthetic data, so the status is UNVERIFIED until a real catalogue passes the validation gate.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

from astronomy_data_workbench.errors import SchemaError

VALIDATION_STATUS = "UNVERIFIED"
UNVERIFIED_BANNER = (
    "VALIDATION STATUS: UNVERIFIED - cross-matching has only been tested on synthetic data and "
    "has not been validated against real BSC, Hipparcos or Gaia records."
)
VALIDATION_GATE = (
    "Real-catalogue validation is a separate gate: run the parser and the matching pipeline on a "
    "real, licence-permitted BSC export, then Hipparcos and Gaia, before removing UNVERIFIED."
)
ALGORITHM = "epoch-positional/1"

# Decisions
ACCEPTED = "accepted"
REVIEW = "review"
REJECTED = "rejected"
UNMATCHED = "unmatched"
DECISIONS = (ACCEPTED, REVIEW, REJECTED, UNMATCHED)

# Reason / flag codes. BLOCKING flags stop automatic acceptance.
NO_CANDIDATES = "NO_CANDIDATES"
ALL_CANDIDATES_IMPLAUSIBLE = "ALL_CANDIDATES_IMPLAUSIBLE"
POSITION_INCONSISTENT = "POSITION_INCONSISTENT"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"
POSSIBLE_MULTIPLE = "POSSIBLE_MULTIPLE"
POSSIBLE_DUPLICATE_REFERENCE = "POSSIBLE_DUPLICATE_REFERENCE"
RECIPROCAL_CONFLICT = "RECIPROCAL_CONFLICT"
EPOCH_UNCORRECTED = "EPOCH_UNCORRECTED"
PM_INCONSISTENT = "PM_INCONSISTENT"
PARALLAX_INCONSISTENT = "PARALLAX_INCONSISTENT"
MAG_INCONSISTENT = "MAG_INCONSISTENT"
NEARBY_REFERENCE_OBJECT = "NEARBY_REFERENCE_OBJECT"  # informational, not blocking

BLOCKING_FLAGS = (
    EPOCH_UNCORRECTED,
    PM_INCONSISTENT,
    PARALLAX_INCONSISTENT,
    MAG_INCONSISTENT,
    POSSIBLE_MULTIPLE,
    POSSIBLE_DUPLICATE_REFERENCE,
)


def _is_number(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


@dataclass(frozen=True)
class CatalogueEntry:
    """One catalogue object with explicit epoch, frame and uncertainty. Nothing is defaulted."""

    catalogue: str
    entry_id: str
    ra_deg: float
    dec_deg: float
    epoch: float  # Julian year of the position, e.g. 2000.0, 1991.25, 2016.0
    pos_err_mas: float  # per-axis 1-sigma positional uncertainty at `epoch`
    pm_ra_cosdec_mas_yr: float | None = None  # mu_alpha* (already includes cos dec)
    pm_dec_mas_yr: float | None = None
    pm_err_mas_yr: float | None = None
    parallax_mas: float | None = None
    parallax_err_mas: float | None = None
    radial_velocity_km_s: float | None = None
    mag: float | None = None
    passband: str | None = None
    frame: str = "ICRS"
    identifiers: dict[str, str] = field(default_factory=dict)
    synthetic: bool = False

    def __post_init__(self) -> None:
        where = f"{self.catalogue}/{self.entry_id}"
        if not self.entry_id or not self.catalogue:
            raise SchemaError("catalogue entries need a catalogue name and an id")
        if not (math.isfinite(self.ra_deg) and 0.0 <= self.ra_deg < 360.0):
            raise SchemaError(f"{where}: ra_deg {self.ra_deg!r} outside [0, 360)")
        if not (math.isfinite(self.dec_deg) and -90.0 <= self.dec_deg <= 90.0):
            raise SchemaError(f"{where}: dec_deg {self.dec_deg!r} outside [-90, 90]")
        if not math.isfinite(self.epoch):
            raise SchemaError(f"{where}: epoch must be a finite Julian year")
        if not (math.isfinite(self.pos_err_mas) and self.pos_err_mas > 0.0):
            raise SchemaError(f"{where}: pos_err_mas must be a positive number")
        for name in ("pm_ra_cosdec_mas_yr", "pm_dec_mas_yr", "parallax_mas",
                     "radial_velocity_km_s", "mag"):  # fmt: skip
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise SchemaError(f"{where}: {name} must be finite or absent")
        for name in ("pm_err_mas_yr", "parallax_err_mas"):
            value = getattr(self, name)
            if value is not None and not (math.isfinite(value) and value > 0.0):
                raise SchemaError(f"{where}: {name} must be positive or absent")
        if (self.pm_ra_cosdec_mas_yr is None) != (self.pm_dec_mas_yr is None):
            raise SchemaError(f"{where}: give both proper-motion components or neither")

    @property
    def has_proper_motion(self) -> bool:
        return _is_number(self.pm_ra_cosdec_mas_yr) and _is_number(self.pm_dec_mas_yr)

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalogue": self.catalogue,
            "id": self.entry_id,
            "ra_deg": self.ra_deg,
            "dec_deg": self.dec_deg,
            "epoch": self.epoch,
            "frame": self.frame,
            "pos_err_mas": self.pos_err_mas,
            "pm_ra_cosdec_mas_yr": self.pm_ra_cosdec_mas_yr,
            "pm_dec_mas_yr": self.pm_dec_mas_yr,
            "pm_err_mas_yr": self.pm_err_mas_yr,
            "parallax_mas": self.parallax_mas,
            "parallax_err_mas": self.parallax_err_mas,
            "radial_velocity_km_s": self.radial_velocity_km_s,
            "mag": self.mag,
            "passband": self.passband,
            "identifiers": dict(self.identifiers),
            "synthetic": self.synthetic,
        }


@dataclass(frozen=True)
class Catalogue:
    name: str
    entries: tuple[CatalogueEntry, ...]
    synthetic: bool = False
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise SchemaError("a catalogue needs a name")
        seen: set[str] = set()
        for e in self.entries:
            if e.catalogue != self.name:
                raise SchemaError(f"entry {e.entry_id!r} belongs to {e.catalogue!r}, not {self.name!r}")
            if e.entry_id in seen:
                raise SchemaError(f"{self.name}: duplicate entry id {e.entry_id!r}")
            seen.add(e.entry_id)


@dataclass(frozen=True)
class MatchConfig:
    """All thresholds. Every value is recorded in the output; none is a validated constant."""

    # Common epoch to which both catalogues are propagated. None = median reference epoch.
    reference_epoch: float | None = None
    # Candidate search gate: max(gate_floor_arcsec, gate_sigma * combined sigma), capped.
    gate_floor_arcsec: float = 3.0
    gate_sigma: float = 5.0
    max_gate_arcsec: float = 60.0
    # Acceptance: all of these must hold, otherwise the pair goes to manual review.
    accept_sigma: float = 3.0
    accept_confidence: float = 0.90
    consistency_sigma: float = 3.0  # proper-motion / parallax agreement
    max_mag_diff: float = 1.5  # loose: catalogues use different passbands
    max_uncorrected_dt_years: float = 1.0  # missing proper motion over longer gaps blocks acceptance
    # Automatic rejection only when every candidate is beyond this many sigma.
    reject_sigma: float = 8.0
    # Scoring.
    # Stand-in for the chance-alignment likelihood ("no true counterpart"). Small on purpose:
    # absolute position is judged by accept_sigma, competition between candidates by the share.
    # It should be set from real source density once real catalogues exist (UNVERIFIED).
    null_weight: float = 0.001
    factor_floor: float = 0.05
    mag_tolerance: float = 0.5
    # Ambiguity and multiplicity.
    ambiguity_fraction: float = 0.10  # second score >= fraction * top score -> ambiguous
    multiplicity_score_fraction: float = 0.01
    multiplicity_radius_arcsec: float = 5.0
    duplicate_radius_arcsec: float = 0.3
    # Uncertainty assumptions that are recorded wherever they are used.
    missing_pm_sigma_mas_yr: float = 200.0
    fallback_pm_err_mas_yr: float = 10.0
    fallback_parallax_err_mas: float = 5.0

    def __post_init__(self) -> None:
        positive = ("gate_floor_arcsec", "gate_sigma", "max_gate_arcsec", "accept_sigma",
                    "consistency_sigma", "max_mag_diff", "reject_sigma", "null_weight",
                    "mag_tolerance", "multiplicity_radius_arcsec", "duplicate_radius_arcsec",
                    "missing_pm_sigma_mas_yr", "fallback_pm_err_mas_yr",
                    "fallback_parallax_err_mas")  # fmt: skip
        for name in positive:
            if not getattr(self, name) > 0.0:
                raise ValueError(f"{name} must be > 0")
        if self.max_uncorrected_dt_years < 0.0:
            raise ValueError("max_uncorrected_dt_years must be >= 0")
        if not 0.0 < self.accept_confidence <= 1.0:
            raise ValueError("accept_confidence must be in (0, 1]")
        for name in ("factor_floor", "ambiguity_fraction", "multiplicity_score_fraction"):
            if not 0.0 < getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.reject_sigma <= self.accept_sigma:
            raise ValueError("reject_sigma must be larger than accept_sigma")
        if self.gate_floor_arcsec > self.max_gate_arcsec:
            raise ValueError("gate_floor_arcsec must not exceed max_gate_arcsec")
        if self.reference_epoch is not None and not math.isfinite(self.reference_epoch):
            raise ValueError("reference_epoch must be finite")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateMatch:
    """One possible counterpart. All candidates inside the gate are kept, never just the best."""

    rank: int
    entry: CatalogueEntry
    separation_mas: float
    raw_separation_mas: float  # catalogued positions, no epoch correction (for context only)
    sigma_mas: float
    normalized_separation: float
    score: float
    relative_confidence: float  # heuristic share among this query's candidates; NOT a probability
    reverse_confidence: float  # the same share, seen from the reference object's side
    factors: dict[str, float]
    flags: list[str]
    evidence: list[str]
    measurements: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "candidate": self.entry.to_dict(),
            "separation_mas": _r(self.separation_mas, 4),
            "raw_separation_mas": _r(self.raw_separation_mas, 4),
            "sigma_mas": _r(self.sigma_mas, 4),
            "normalized_separation": _r(self.normalized_separation, 4),
            "score": _g(self.score),
            "relative_confidence": _r(self.relative_confidence, 6),
            "reverse_confidence": _r(self.reverse_confidence, 6),
            "factors": {k: _g(v) for k, v in sorted(self.factors.items())},
            "flags": list(self.flags),
            "evidence": list(self.evidence),
            "measurements": self.measurements,
        }


@dataclass
class MatchResult:
    query: CatalogueEntry
    decision: str
    reasons: list[str]
    candidates: list[CandidateMatch]
    notes: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_status": VALIDATION_STATUS,
            "query": self.query.to_dict(),
            "decision": self.decision,
            "reasons": list(self.reasons),
            "candidate_count": len(self.candidates),
            "candidates": [c.to_dict() for c in self.candidates],
            "notes": list(self.notes),
            "assumptions": list(self.assumptions),
        }


@dataclass
class CrossMatchRun:
    primary: Catalogue
    reference: Catalogue
    config: MatchConfig
    resolved_reference_epoch: float
    results: list[MatchResult]

    def by_decision(self, decision: str) -> list[MatchResult]:
        return [r for r in self.results if r.decision == decision]

    def counts(self) -> dict[str, int]:
        counts = {d: 0 for d in DECISIONS}
        for r in self.results:
            counts[r.decision] += 1
        counts["total"] = len(self.results)
        return counts

    def reason_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.results:
            for reason in r.reasons:
                out[reason] = out.get(reason, 0) + 1
        return dict(sorted(out.items()))

    def result_for(self, entry_id: str) -> MatchResult:
        for r in self.results:
            if r.query.entry_id == entry_id:
                return r
        raise KeyError(entry_id)


def _r(value: float, digits: int) -> float:
    return round(float(value), digits)


def _g(value: float) -> float:
    return float(f"{value:.6g}")
