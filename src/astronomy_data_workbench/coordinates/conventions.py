"""Explicit unit and convention helpers for catalogue astrometry (Phase 3).

Nothing here guesses a convention: callers must say what they have.
"""
from __future__ import annotations

ARCSEC_TO_MAS = 1000.0


def bsc_pm_arcsec_to_mas(pm_arcsec_per_yr: float) -> float:
    """Convert a BSC proper-motion component from arcsec/yr to mas/yr.

    BSC RA motion is already mu_alpha* (= mu_alpha cos(dec)); this function
    deliberately does NOT apply cos(dec). It is a pure x1000 unit conversion.
    """
    return pm_arcsec_per_yr * ARCSEC_TO_MAS


def pm_ra_to_mu_alpha_star(pm_ra_per_yr: float, dec_deg: float, *, already_cos_dec: bool) -> float:
    """Return mu_alpha* given an RA motion with a stated convention.

    The convention flag is mandatory so it can never be defaulted silently.
    """
    import math

    if already_cos_dec:
        return pm_ra_per_yr
    return pm_ra_per_yr * math.cos(math.radians(dec_deg))
