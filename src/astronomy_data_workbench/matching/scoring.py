"""Score one (query, reference) pair and record the evidence behind the score.

score = p_position * f_proper_motion * f_parallax * f_magnitude

* p_position = exp(-z^2 / 2) with z = separation / combined 1-sigma, both positions propagated to
  the common epoch (the upper-tail probability of a 2-D Gaussian error circle).
* Each f_* is exp(-z^2 / 2) of that quantity's agreement, floored at `factor_floor` so a single
  disagreement lowers the score and raises a flag but cannot erase the evidence.

The score is a heuristic likelihood-like number, not a calibrated probability. It is UNVERIFIED.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from astronomy_data_workbench.matching.epoch import PropagatedPosition
from astronomy_data_workbench.matching.geometry import separation_mas, unit_vector
from astronomy_data_workbench.matching.models import (
    EPOCH_UNCORRECTED,
    MAG_INCONSISTENT,
    PARALLAX_INCONSISTENT,
    PM_INCONSISTENT,
    MatchConfig,
)


@dataclass
class PairEvaluation:
    separation_mas: float
    raw_separation_mas: float
    sigma_mas: float
    z: float
    score: float
    factors: dict[str, float]
    flags: list[str]
    evidence: list[str]
    measurements: dict[str, Any]
    assumptions: list[str]


def _gauss(z: float) -> float:
    return math.exp(-0.5 * z * z) if z < 38.0 else 0.0


def _floored(z: float, floor: float) -> float:
    return max(floor, _gauss(z))


def evaluate_pair(
    q: PropagatedPosition, r: PropagatedPosition, sep_mas: float, cfg: MatchConfig
) -> PairEvaluation:
    qe, re = q.entry, r.entry
    sigma = math.hypot(q.sigma_mas, r.sigma_mas)
    z = sep_mas / sigma
    raw_sep = separation_mas(unit_vector(qe.ra_deg, qe.dec_deg), unit_vector(re.ra_deg, re.dec_deg))
    p_pos = _gauss(z)

    flags: list[str] = []
    evidence: list[str] = [
        (
            f"separation at epoch {q.target_epoch:g}: {sep_mas:.1f} mas "
            f"(combined 1-sigma {sigma:.1f} mas, {z:.2f} sigma)"
        ),
        f"without epoch correction the catalogued positions differ by {raw_sep / 1000.0:.3f} arcsec",
        q.describe("query"),
        r.describe("reference"),
    ]
    assumptions = [*q.assumptions, *r.assumptions]
    factors: dict[str, float] = {"position": p_pos}
    measurements: dict[str, Any] = {
        "epoch": q.target_epoch,
        "query_dt_years": round(q.dt_years, 6),
        "reference_dt_years": round(r.dt_years, 6),
        "query_sigma_mas": round(q.sigma_mas, 4),
        "reference_sigma_mas": round(r.sigma_mas, 4),
    }

    if q.uncorrected or r.uncorrected:
        flags.append(EPOCH_UNCORRECTED)
        side = "query" if q.uncorrected else "reference"
        if q.uncorrected and r.uncorrected:
            side = "query and reference"
        evidence.append(
            f"EPOCH_UNCORRECTED: {side} has no proper motion over a gap above "
            f"{cfg.max_uncorrected_dt_years:g} yr, so this pair cannot be accepted automatically"
        )

    if qe.frame != re.frame:
        evidence.append(
            f"frames differ ({qe.frame} vs {re.frame}); no frame transformation applied "
            "(difference assumed small against the positional uncertainty)"
        )

    # Proper motion agreement.
    f_pm = 1.0
    if qe.has_proper_motion and re.has_proper_motion:
        dpa = float(qe.pm_ra_cosdec_mas_yr or 0.0) - float(re.pm_ra_cosdec_mas_yr or 0.0)
        dpd = float(qe.pm_dec_mas_yr or 0.0) - float(re.pm_dec_mas_yr or 0.0)
        err_q = qe.pm_err_mas_yr or cfg.fallback_pm_err_mas_yr
        err_r = re.pm_err_mas_yr or cfg.fallback_pm_err_mas_yr
        z_pm = math.hypot(dpa, dpd) / math.hypot(err_q, err_r)
        f_pm = _floored(z_pm, cfg.factor_floor)
        measurements["pm_difference_mas_yr"] = round(math.hypot(dpa, dpd), 4)
        measurements["pm_z"] = round(z_pm, 4)
        evidence.append(
            f"proper motion differs by {math.hypot(dpa, dpd):.1f} mas/yr ({z_pm:.2f} sigma)"
        )
        if z_pm > cfg.consistency_sigma:
            flags.append(PM_INCONSISTENT)
    else:
        evidence.append("proper motion not compared (missing on at least one side)")
    factors["proper_motion"] = f_pm

    # Parallax agreement.
    f_plx = 1.0
    if qe.parallax_mas is not None and re.parallax_mas is not None:
        err_q = qe.parallax_err_mas or cfg.fallback_parallax_err_mas
        err_r = re.parallax_err_mas or cfg.fallback_parallax_err_mas
        if qe.parallax_err_mas is None or re.parallax_err_mas is None:
            assumptions.append(
                f"{qe.catalogue}/{qe.entry_id} vs {re.catalogue}/{re.entry_id}: parallax error "
                f"not given on at least one side; assumed {cfg.fallback_parallax_err_mas:g} mas"
            )
        dplx = qe.parallax_mas - re.parallax_mas
        z_plx = abs(dplx) / math.hypot(err_q, err_r)
        f_plx = _floored(z_plx, cfg.factor_floor)
        measurements["parallax_difference_mas"] = round(dplx, 4)
        measurements["parallax_z"] = round(z_plx, 4)
        evidence.append(f"parallax differs by {dplx:+.2f} mas ({z_plx:.2f} sigma)")
        if z_plx > cfg.consistency_sigma:
            flags.append(PARALLAX_INCONSISTENT)
    else:
        evidence.append("parallax not compared (missing on at least one side)")
    factors["parallax"] = f_plx

    # Magnitude agreement: loose, because the catalogues use different passbands.
    f_mag = 1.0
    if qe.mag is not None and re.mag is not None:
        dmag = qe.mag - re.mag
        f_mag = _floored(abs(dmag) / cfg.mag_tolerance, cfg.factor_floor)
        measurements["mag_difference"] = round(dmag, 4)
        same_band = qe.passband is not None and qe.passband == re.passband
        band_note = (
            f"same passband {qe.passband}"
            if same_band
            else f"passbands differ ({qe.passband or 'unknown'} vs {re.passband or 'unknown'}); "
            "compared loosely, not merged"
        )
        evidence.append(f"magnitude differs by {dmag:+.2f} ({band_note})")
        if abs(dmag) > cfg.max_mag_diff:
            flags.append(MAG_INCONSISTENT)
    else:
        evidence.append("magnitude not compared (missing on at least one side)")
    factors["magnitude"] = f_mag

    score = p_pos * f_pm * f_plx * f_mag
    measurements["separation_mas"] = round(sep_mas, 4)
    measurements["combined_sigma_mas"] = round(sigma, 4)
    measurements["normalized_separation"] = round(z, 4)
    return PairEvaluation(
        separation_mas=sep_mas,
        raw_separation_mas=raw_sep,
        sigma_mas=sigma,
        z=z,
        score=score,
        factors=factors,
        flags=flags,
        evidence=evidence,
        measurements=measurements,
        assumptions=assumptions,
    )
