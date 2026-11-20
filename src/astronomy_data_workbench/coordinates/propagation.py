"""Independent epoch propagation (rigorous space motion) in plain numpy.

Written from the standard 3-D space-motion model so it can be compared with
Astropy's implementation. Inputs follow ADW's canonical convention:
pm_ra_cosdec_mas_yr is mu_alpha* (already includes cos dec).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

K_KM_S = 4.740470446  # km/s per (AU/yr); converts mas/yr over mas to km/s
MAS_TO_RAD = math.pi / 180.0 / 3600.0 / 1000.0


@dataclass(frozen=True)
class SpaceMotion:
    ra_deg: float
    dec_deg: float
    parallax_mas: float
    pm_ra_cosdec_mas_yr: float
    pm_dec_mas_yr: float
    rv_km_s: float


def _basis(ra: float, dec: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    e_ra = np.array([-math.sin(ra), math.cos(ra), 0.0])
    e_dec = np.array(
        [-math.sin(dec) * math.cos(ra), -math.sin(dec) * math.sin(ra), math.cos(dec)]
    )
    return p, e_ra, e_dec


def propagate_rigorous(s: SpaceMotion, dt_years: float) -> tuple[float, float]:
    """Propagate (ra, dec) in degrees by dt_years using full space motion.

    Requires a positive parallax; otherwise use propagate_linear and treat
    the result as lower quality.
    """
    if s.parallax_mas <= 0:
        raise ValueError("rigorous propagation needs parallax > 0")
    ra, dec = math.radians(s.ra_deg), math.radians(s.dec_deg)
    p, e_ra, e_dec = _basis(ra, dec)
    plx_rad = s.parallax_mas * MAS_TO_RAD
    rv_scaled = s.rv_km_s * plx_rad / K_KM_S  # radial speed in units of r0 per year
    v = (
        s.pm_ra_cosdec_mas_yr * MAS_TO_RAD * e_ra
        + s.pm_dec_mas_yr * MAS_TO_RAD * e_dec
        + rv_scaled * p
    )
    q = p + dt_years * v
    q = q / np.linalg.norm(q)
    return math.degrees(math.atan2(q[1], q[0])) % 360.0, math.degrees(math.asin(q[2]))


def propagate_linear(s: SpaceMotion, dt_years: float) -> tuple[float, float]:
    """Naive linear propagation; ignores parallax, radial velocity and curvature."""
    dec = math.radians(s.dec_deg)
    dra = s.pm_ra_cosdec_mas_yr * dt_years / 3.6e6 / math.cos(dec)
    ddec = s.pm_dec_mas_yr * dt_years / 3.6e6
    return (s.ra_deg + dra) % 360.0, s.dec_deg + ddec
