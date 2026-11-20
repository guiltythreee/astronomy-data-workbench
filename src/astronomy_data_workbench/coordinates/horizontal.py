"""Independent equatorial-to-horizontal pieces, written from published formulas.

Sources: Meeus, Astronomical Algorithms (2nd ed.): ch. 12 (sidereal time),
ch. 13 (horizontal coordinates), ch. 21 (precession, IAU 1976 angles).
Refraction is NOT applied here; it is a separate effect.
"""
from __future__ import annotations

import math

J2000_JD = 2451545.0


def gmst_deg(jd_ut: float) -> float:
    """Mean sidereal time at Greenwich in degrees (Meeus 12.4)."""
    t = (jd_ut - J2000_JD) / 36525.0
    g = (
        280.46061837
        + 360.98564736629 * (jd_ut - J2000_JD)
        + 0.000387933 * t**2
        - t**3 / 38710000.0
    )
    return g % 360.0


def precess_j2000_to_date(ra_deg: float, dec_deg: float, jd_tt: float) -> tuple[float, float]:
    """Precess mean J2000 equatorial coordinates to the mean equator of date."""
    t = (jd_tt - J2000_JD) / 36525.0
    arc = math.pi / 180.0 / 3600.0
    zeta = (2306.2181 * t + 0.30188 * t**2 + 0.017998 * t**3) * arc
    z = (2306.2181 * t + 1.09468 * t**2 + 0.018203 * t**3) * arc
    theta = (2004.3109 * t - 0.42665 * t**2 - 0.041833 * t**3) * arc
    a0, d0 = math.radians(ra_deg), math.radians(dec_deg)
    a = math.cos(d0) * math.sin(a0 + zeta)
    b = math.cos(theta) * math.cos(d0) * math.cos(a0 + zeta) - math.sin(theta) * math.sin(d0)
    c = math.sin(theta) * math.cos(d0) * math.cos(a0 + zeta) + math.cos(theta) * math.sin(d0)
    ra = (math.degrees(math.atan2(a, b) + z)) % 360.0
    return ra, math.degrees(math.asin(max(-1.0, min(1.0, c))))


def equatorial_to_horizontal(
    hour_angle_deg: float, dec_deg: float, lat_deg: float
) -> tuple[float, float]:
    """Return (altitude, azimuth) in degrees; azimuth measured from North through East.

    Meeus measures azimuth westward from South; that convention is converted here.
    """
    h, d, p = map(math.radians, (hour_angle_deg, dec_deg, lat_deg))
    sin_alt = math.sin(p) * math.sin(d) + math.cos(p) * math.cos(d) * math.cos(h)
    alt = math.asin(max(-1.0, min(1.0, sin_alt)))
    az_south = math.atan2(math.sin(h), math.cos(h) * math.sin(p) - math.tan(d) * math.cos(p))
    return math.degrees(alt), (math.degrees(az_south) + 180.0) % 360.0


def radec_to_altaz(
    ra_j2000_deg: float, dec_j2000_deg: float, jd_ut: float, lat_deg: float, east_lon_deg: float
) -> tuple[float, float]:
    """Mean-place pipeline: precess, form hour angle from GMST, convert.

    Ignores nutation, aberration, UT1-UTC and refraction (see reference tolerances).
    """
    ra, dec = precess_j2000_to_date(ra_j2000_deg, dec_j2000_deg, jd_ut)
    ha = (gmst_deg(jd_ut) + east_lon_deg - ra) % 360.0
    return equatorial_to_horizontal(ha, dec, lat_deg)
