"""Epoch correction for matching: move each catalogue position to a common epoch.

Space-motion model: p(t) = normalise(p0 + dt * v) with v = mu_alpha* e_east + mu_delta e_north
(+ a radial term when parallax > 0 and a radial velocity are both given). Proper motion uses the
convention mu_alpha* (already includes cos dec); the unit-vector form is safe at the poles.

Uncertainty grows with the epoch gap: sigma^2 = sigma_pos^2 + (sigma_pm * |dt|)^2. If an entry has
no proper motion it cannot be corrected: its position is left where it is, its uncertainty is
inflated by an assumed proper-motion sigma, and it is flagged so it can never be auto-accepted.

This module is independent of the Coordinate Laboratory (no Astropy); a test cross-checks it
against the laboratory's numpy propagator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from astronomy_data_workbench.matching.geometry import (
    MAS_TO_RAD,
    Vec,
    tangent_basis,
    to_ra_dec,
)
from astronomy_data_workbench.matching.models import CatalogueEntry, MatchConfig

K_KM_S = 4.740470446  # km/s per (AU/yr)


@dataclass(frozen=True)
class PropagatedPosition:
    entry: CatalogueEntry
    target_epoch: float
    dt_years: float
    ra_deg: float
    dec_deg: float
    vector: Vec
    sigma_mas: float
    inflation_mas: float
    pm_applied: bool
    radial_term_used: bool
    uncorrected: bool  # needs an epoch correction it cannot get (no proper motion, large gap)
    assumptions: list[str] = field(default_factory=list)

    def describe(self, label: str) -> str:
        e = self.entry
        if self.dt_years == 0.0:
            return f"{label} {e.entry_id}: already at epoch {self.target_epoch:g}, no correction"
        if self.pm_applied:
            how = (
                f"proper motion ({e.pm_ra_cosdec_mas_yr:g}, {e.pm_dec_mas_yr:g}) mas/yr"
                + (" + radial velocity" if self.radial_term_used else "")
            )
            return (
                f"{label} {e.entry_id}: propagated {self.dt_years:+.3f} yr "
                f"({e.epoch:g} -> {self.target_epoch:g}) using {how}; "
                f"sigma {e.pos_err_mas:g} -> {self.sigma_mas:.1f} mas"
            )
        verdict = "NOT epoch-corrected (no proper motion)"
        return (
            f"{label} {e.entry_id}: {verdict} over {self.dt_years:+.3f} yr "
            f"({e.epoch:g} -> {self.target_epoch:g}); sigma inflated "
            f"{e.pos_err_mas:g} -> {self.sigma_mas:.1f} mas by an assumed proper-motion sigma"
        )


def propagate_entry(entry: CatalogueEntry, target_epoch: float, cfg: MatchConfig) -> PropagatedPosition:
    dt = target_epoch - entry.epoch
    p, east, north = tangent_basis(entry.ra_deg, entry.dec_deg)
    assumptions: list[str] = []
    radial_used = False

    if entry.has_proper_motion:
        mu_a = float(entry.pm_ra_cosdec_mas_yr or 0.0)
        mu_d = float(entry.pm_dec_mas_yr or 0.0)
        v = (mu_a * east + mu_d * north) * MAS_TO_RAD
        plx = entry.parallax_mas
        rv = entry.radial_velocity_km_s
        if plx is not None and plx > 0.0 and rv is not None:
            v = v + (rv * (plx * MAS_TO_RAD) / K_KM_S) * p
            radial_used = True
        q = p + dt * v
        ra, dec = to_ra_dec(q)
        if entry.pm_err_mas_yr is not None:
            pm_err = entry.pm_err_mas_yr
        else:
            pm_err = cfg.fallback_pm_err_mas_yr
            assumptions.append(
                f"{entry.catalogue}/{entry.entry_id}: proper-motion error not given; "
                f"assumed {pm_err:g} mas/yr"
            )
        inflation = pm_err * abs(dt)
        pm_applied = True
    else:
        q = p
        ra, dec = entry.ra_deg, entry.dec_deg
        inflation = cfg.missing_pm_sigma_mas_yr * abs(dt)
        pm_applied = False
        if dt != 0.0:
            assumptions.append(
                f"{entry.catalogue}/{entry.entry_id}: no proper motion; assumed sigma "
                f"{cfg.missing_pm_sigma_mas_yr:g} mas/yr over {abs(dt):.3f} yr"
            )

    uncorrected = (not pm_applied) and abs(dt) > cfg.max_uncorrected_dt_years
    return PropagatedPosition(
        entry=entry,
        target_epoch=target_epoch,
        dt_years=dt,
        ra_deg=ra,
        dec_deg=dec,
        vector=q / math.sqrt(float(q @ q)),
        sigma_mas=math.hypot(entry.pos_err_mas, inflation),
        inflation_mas=inflation,
        pm_applied=pm_applied,
        radial_term_used=radial_used,
        uncorrected=uncorrected,
        assumptions=assumptions,
    )
