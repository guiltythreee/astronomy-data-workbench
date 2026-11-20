"""Nutation and annual aberration, written independently from Meeus (2nd ed.).

Ch. 22 low-accuracy nutation (about 0.5 arcsec in longitude, 0.1 arcsec in
obliquity), ch. 23 annual aberration, ch. 25 low-accuracy solar longitude.
"""
from __future__ import annotations

import math

from .horizontal import (
    J2000_JD,
    equatorial_to_horizontal,
    gmst_deg,
    precess_j2000_to_date,
)

KAPPA_ARCSEC = 20.49552


def _t(jd: float) -> float:
    return (jd - J2000_JD) / 36525.0


def mean_obliquity_deg(jd: float) -> float:
    t = _t(jd)
    return 23.0 + 26.0 / 60.0 + 21.448 / 3600.0 - (46.8150 * t + 0.00059 * t**2 - 0.001813 * t**3) / 3600.0


def nutation_arcsec(jd: float) -> tuple[float, float]:
    """Return (delta_psi, delta_epsilon) in arcsec, 4-term low-accuracy series."""
    t = _t(jd)
    om = math.radians(125.04452 - 1934.136261 * t)
    ls = math.radians(280.4665 + 36000.7698 * t)
    lm = math.radians(218.3165 + 481267.8813 * t)
    dpsi = -17.20 * math.sin(om) - 1.32 * math.sin(2 * ls) - 0.23 * math.sin(2 * lm) + 0.21 * math.sin(2 * om)
    deps = 9.20 * math.cos(om) + 0.57 * math.cos(2 * ls) + 0.10 * math.cos(2 * lm) - 0.09 * math.cos(2 * om)
    return dpsi, deps


def sun_true_longitude_deg(jd: float) -> float:
    t = _t(jd)
    l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t**2
    m = math.radians(357.52911 + 35999.05029 * t - 0.0001537 * t**2)
    c = (
        (1.914602 - 0.004817 * t - 0.000014 * t**2) * math.sin(m)
        + (0.019993 - 0.000101 * t) * math.sin(2 * m)
        + 0.000289 * math.sin(3 * m)
    )
    return (l0 + c) % 360.0


def apparent_place(ra_j2000_deg: float, dec_j2000_deg: float, jd: float) -> tuple[float, float]:
    """Mean J2000 -> apparent place of date (precession + nutation + annual aberration)."""
    ra, dec = precess_j2000_to_date(ra_j2000_deg, dec_j2000_deg, jd)
    t = _t(jd)
    a, d = math.radians(ra), math.radians(dec)
    dpsi, deps = nutation_arcsec(jd)
    eps = math.radians(mean_obliquity_deg(jd) + deps / 3600.0)
    # Nutation (Meeus 23.1)
    da_n = (math.cos(eps) + math.sin(eps) * math.sin(a) * math.tan(d)) * dpsi - math.cos(a) * math.tan(d) * deps
    dd_n = math.sin(eps) * math.cos(a) * dpsi + math.sin(a) * deps
    # Annual aberration (Meeus 23.2, including the elliptical term)
    lam = math.radians(sun_true_longitude_deg(jd))
    e = 0.016708634 - 0.000042037 * t
    pi = math.radians(102.93735 + 1.71946 * t)
    k = KAPPA_ARCSEC
    da_a = (-k * (math.cos(a) * math.cos(lam) * math.cos(eps) + math.sin(a) * math.sin(lam))
            + e * k * (math.cos(a) * math.cos(pi) * math.cos(eps) + math.sin(a) * math.sin(pi))) / math.cos(d)
    dd_a = (-k * (math.cos(lam) * math.cos(eps) * (math.tan(eps) * math.cos(d) - math.sin(a) * math.sin(d))
                  + math.cos(a) * math.sin(d) * math.sin(lam))
            + e * k * (math.cos(pi) * math.cos(eps) * (math.tan(eps) * math.cos(d) - math.sin(a) * math.sin(d))
                       + math.cos(a) * math.sin(d) * math.sin(pi)))
    ra_app = (ra + (da_n + da_a) / 3600.0) % 360.0
    dec_app = dec + (dd_n + dd_a) / 3600.0
    return ra_app, dec_app


def apparent_sidereal_deg(jd_ut: float) -> float:
    """GMST plus the equation of the equinoxes (delta_psi * cos eps)."""
    dpsi, deps = nutation_arcsec(jd_ut)
    eps = math.radians(mean_obliquity_deg(jd_ut) + deps / 3600.0)
    return (gmst_deg(jd_ut) + dpsi * math.cos(eps) / 3600.0) % 360.0


def radec_to_altaz_apparent(
    ra_j2000_deg: float, dec_j2000_deg: float, jd_utc: float, lat_deg: float,
    east_lon_deg: float, dut1_s: float = 0.0,
) -> tuple[float, float]:
    """Apparent-place pipeline. dut1_s (UT1-UTC) must be supplied; it is never guessed."""
    jd_ut1 = jd_utc + dut1_s / 86400.0
    ra, dec = apparent_place(ra_j2000_deg, dec_j2000_deg, jd_utc)
    ha = (apparent_sidereal_deg(jd_ut1) + east_lon_deg - ra) % 360.0
    return equatorial_to_horizontal(ha, dec, lat_deg)
