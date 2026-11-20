"""Reference comparisons with stated tolerances. Results are data, not opinions."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import astropy.units as u
from astropy.coordinates import FK5, ICRS, AltAz, EarthLocation, SkyCoord
from astropy.time import Time
from astropy.utils import iers

from .apparent import nutation_arcsec, radec_to_altaz_apparent
from .horizontal import equatorial_to_horizontal, gmst_deg, radec_to_altaz
from .propagation import SpaceMotion, propagate_linear, propagate_rigorous
from .refraction import (
    apparent_to_true_alt,
    refraction_from_apparent_arcmin,
    refraction_from_true_arcmin,
    true_to_apparent_alt,
)

# Hipparcos-catalogue-style values used only as realistic test INPUTS.
BARNARD = SpaceMotion(269.45207, 4.69337, 548.31, -798.58, 10328.12, -110.51)
SLOW_STAR = SpaceMotion(101.28716, -16.71612, 379.21, -546.01, -1223.07, -5.5)


@dataclass(frozen=True)
class Residual:
    case: str
    quantity: str
    residual: float
    unit: str
    tolerance: float
    passed: bool
    note: str = ""
    informational: bool = False


def angular_sep_mas(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    """Haversine separation in mas (independent of Astropy)."""
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    h = math.sin((d2 - d1) / 2) ** 2 + math.cos(d1) * math.cos(d2) * math.sin((r2 - r1) / 2) ** 2
    return math.degrees(2 * math.asin(min(1.0, math.sqrt(h)))) * 3.6e6


def astropy_propagate(s: SpaceMotion, from_epoch: str, to_epoch: str) -> tuple[float, float]:
    c = SkyCoord(
        ra=s.ra_deg * u.deg, dec=s.dec_deg * u.deg,
        distance=(1000.0 / s.parallax_mas) * u.pc,
        pm_ra_cosdec=s.pm_ra_cosdec_mas_yr * u.mas / u.yr,
        pm_dec=s.pm_dec_mas_yr * u.mas / u.yr,
        radial_velocity=s.rv_km_s * u.km / u.s,
        frame=ICRS(), obstime=Time(from_epoch, format="jyear_str"),
    )
    out = c.apply_space_motion(new_obstime=Time(to_epoch, format="jyear_str"))
    return float(out.ra.deg), float(out.dec.deg)


def run_reference_suite() -> list[Residual]:
    results: list[Residual] = []
    # 1. Independent rigorous propagation vs Astropy, J2000 -> Hipparcos and Gaia epochs.
    for name, star in (("barnard", BARNARD), ("sirius", SLOW_STAR)):
        for to, dt in (("J1991.25", -8.75), ("J2016.0", 16.0)):
            a = astropy_propagate(star, "J2000.0", to)
            b = propagate_rigorous(star, dt)
            r = angular_sep_mas(*a, *b)
            results.append(Residual(
                f"{name} J2000->{to}", "rigorous vs astropy", r, "mas", 0.1, r < 0.1,
                "tolerance 0.1 mas; extreme-PM star shows ~0.03 mas, cause not yet confirmed",
            ))
    # 2. Linear propagation is expected to be WORSE for high proper motion: record, don't hide.
    a = astropy_propagate(BARNARD, "J2000.0", "J2016.0")
    r = angular_sep_mas(*a, *propagate_linear(BARNARD, 16.0))
    results.append(Residual("barnard J2000->J2016.0", "linear vs astropy", r, "mas", 1.0, r < 1.0,
                            "shows why linear propagation is unsafe for high PM",
                            informational=True))
    # 3. FK5 and ICRS must not be conflated: same numbers, different frames differ by tens of mas.
    fk5 = SkyCoord(ra=101.28716 * u.deg, dec=-16.71612 * u.deg, frame=FK5(equinox="J2000"))
    icrs = fk5.transform_to(ICRS())
    r = angular_sep_mas(fk5.ra.deg, fk5.dec.deg, icrs.ra.deg, icrs.dec.deg)
    results.append(Residual("sirius FK5(J2000)->ICRS", "frame offset", r, "mas", 100.0, 0.0 < r < 100.0,
                            "sanity bound only (offset should be small but nonzero)"))
    return results


def _wrap_diff_deg(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def run_horizontal_suite() -> list[Residual]:
    """Published-reference and Astropy comparisons for horizontal coordinates."""
    out: list[Residual] = []
    # Meeus Example 12.a: GMST at 1987-04-10 0h UT = 13h10m46.3668s.
    r = abs(_wrap_diff_deg(gmst_deg(2446895.5), (13 + 10 / 60 + 46.3668 / 3600) * 15.0)) * 3600
    out.append(Residual("Meeus ex.12.a", "GMST vs published", r, "arcsec", 0.01, r < 0.01))
    # Meeus Example 13.b (Venus, Washington DC): H = 64.352133 deg, dec -6d43m11.61s,
    # lat +38d55m17s -> altitude 15.1249 deg, azimuth 68.0337 deg west of South.
    alt, az = equatorial_to_horizontal(
        64.352133, -(6 + 43 / 60 + 11.61 / 3600), 38 + 55 / 60 + 17 / 3600
    )
    ra_alt = abs(alt - 15.1249) * 3600
    ra_az = abs(_wrap_diff_deg(az, (68.0337 + 180.0) % 360.0)) * 3600
    out.append(Residual("Meeus ex.13.b", "altitude vs published", ra_alt, "arcsec", 1.0, ra_alt < 1.0))
    out.append(Residual("Meeus ex.13.b", "azimuth (N through E) vs published", ra_az, "arcsec", 1.0, ra_az < 1.0))
    # Astropy cross-check. Tolerance covers effects the independent pipeline omits:
    # nutation (~17"), annual aberration (~20"), UT1-UTC (<=0.9 s ~ 13").
    iers.conf.auto_download = False
    iers.conf.iers_degraded_accuracy = "ignore"
    lat, lon = 13.34, 77.10
    for name, ra, dec in (("sirius", 101.28716, -16.71612), ("polaris", 37.95456, 89.26411)):
        t = Time("2026-11-16T20:00:00", scale="utc")
        loc = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
        aa = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS()).transform_to(
            AltAz(obstime=t, location=loc, pressure=0 * u.hPa)
        )
        mine = radec_to_altaz(ra, dec, float(t.jd), lat, lon)
        d_alt = abs(mine[0] - float(aa.alt.deg)) * 3600
        d_az = abs(_wrap_diff_deg(mine[1], float(aa.az.deg))) * math.cos(math.radians(mine[0])) * 3600
        note = "omits nutation, aberration, UT1-UTC, refraction; Astropy refraction off"
        out.append(Residual(f"{name} altaz", "altitude vs astropy", d_alt, "arcsec", 60.0, d_alt < 60.0, note))
        out.append(Residual(f"{name} altaz", "azimuth*cos(alt) vs astropy", d_az, "arcsec", 60.0, d_az < 60.0, note))
    return out


def run_apparent_suite() -> list[Residual]:
    """Nutation and aberration included: should agree with Astropy far more tightly."""
    out: list[Residual] = []
    dpsi, deps = nutation_arcsec(2446895.5)  # Meeus example 22.a: -3.788, +9.443 arcsec
    for label, got, want in (("delta_psi", dpsi, -3.788), ("delta_epsilon", deps, 9.443)):
        r = abs(got - want)
        out.append(Residual("Meeus ex.22.a", f"{label} vs published", r, "arcsec", 0.2, r < 0.2,
                            "4-term low-accuracy series vs full-theory published value"))
    iers.conf.auto_download = False
    iers.conf.iers_degraded_accuracy = "ignore"
    lat, lon = 13.34, 77.10
    t = Time("2026-11-16T20:00:00", scale="utc")
    dut1 = float(t.delta_ut1_utc)  # taken from Astropy's IERS tables, never guessed
    loc = EarthLocation(lat=lat * u.deg, lon=lon * u.deg, height=0 * u.m)
    note = "tolerance covers low-accuracy nutation, diurnal aberration, light deflection"
    for name, ra, dec in (("sirius", 101.28716, -16.71612), ("polaris", 37.95456, 89.26411),
                          ("vega", 279.23473, 38.78369)):
        aa = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame=ICRS()).transform_to(
            AltAz(obstime=t, location=loc, pressure=0 * u.hPa))
        alt, az = radec_to_altaz_apparent(ra, dec, float(t.jd), lat, lon, dut1)
        d_alt = abs(alt - float(aa.alt.deg)) * 3600
        d_az = abs(_wrap_diff_deg(az, float(aa.az.deg))) * math.cos(math.radians(alt)) * 3600
        out.append(Residual(f"{name} apparent altaz", "altitude vs astropy", d_alt, "arcsec", 2.0, d_alt < 2.0, note))
        out.append(Residual(f"{name} apparent altaz", "azimuth*cos(alt) vs astropy", d_az, "arcsec", 2.0, d_az < 2.0, note))
    return out


def run_refraction_suite() -> list[Residual]:
    """Refraction as a separate effect: sanity values, self-consistency, Astropy comparison."""
    import random

    out: list[Residual] = []
    r = abs(refraction_from_apparent_arcmin(0.0) - 34.5)
    out.append(Residual("horizon", "refraction vs ~34.5 arcmin standard", r, "arcmin", 1.0, r < 1.0,
                        "widely quoted standard value; real horizon refraction varies with weather"))
    r = abs(refraction_from_true_arcmin(90.0))
    out.append(Residual("zenith", "refraction at 90 deg", r, "arcmin", 0.01, r < 0.01))
    worst = max(abs(apparent_to_true_alt(true_to_apparent_alt(float(h))) - h) * 3600 for h in range(5, 90))
    out.append(Residual("5-89 deg", "Saemundsson/Bennett round trip", worst, "arcsec", 5.0, worst < 5.0,
                        "two different approximate models; not an exact inverse"))
    iers.conf.auto_download = False
    iers.conf.iers_degraded_accuracy = "ignore"
    t = Time("2026-11-16T20:00:00", scale="utc")
    loc = EarthLocation(lat=13.34 * u.deg, lon=77.10 * u.deg, height=0 * u.m)
    rng = random.Random(7)
    diffs: list[float] = []
    while len(diffs) < 40:
        c = SkyCoord(ra=rng.uniform(0, 360) * u.deg,
                     dec=math.degrees(math.asin(rng.uniform(-1, 1))) * u.deg)
        a0 = float(c.transform_to(AltAz(obstime=t, location=loc, pressure=0 * u.hPa)).alt.deg)
        if 10.0 < a0 < 85.0:
            a1 = float(c.transform_to(AltAz(
                obstime=t, location=loc, pressure=1010 * u.hPa, temperature=10 * u.deg_C,
                relative_humidity=0, obswl=0.55 * u.micron)).alt.deg)
            diffs.append(abs(refraction_from_true_arcmin(a0) * 60.0 - (a1 - a0) * 3600.0))
    w = max(diffs)
    out.append(Residual("40 sky positions, alt 10-85", "refraction vs astropy (max)", w, "arcsec", 12.0, w < 12.0,
                        "mine runs ~5% larger than astropy; both models approximate; 1010 mbar, 10 C"))
    return out


def report_dict(results: list[Residual]) -> dict[str, object]:
    return {"all_passed": all(x.passed for x in results if not x.informational), "results": [asdict(x) for x in results]}
