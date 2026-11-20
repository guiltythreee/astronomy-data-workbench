"""Atmospheric refraction as a separate, explicit effect (never folded into geometry).

Formulas: Saemundsson (true -> apparent) and Bennett (apparent -> true), as given in
Meeus, Astronomical Algorithms (2nd ed.), ch. 16. Valid for roughly 0 to 90 degrees
altitude; accuracy degrades near the horizon where real refraction varies with weather.
"""
from __future__ import annotations

import math


def _scale(pressure_mbar: float, temp_c: float) -> float:
    return (pressure_mbar / 1010.0) * (283.0 / (273.0 + temp_c))


def refraction_from_true_arcmin(
    true_alt_deg: float, pressure_mbar: float = 1010.0, temp_c: float = 10.0
) -> float:
    """Refraction in arcminutes to ADD to a true altitude (Saemundsson)."""
    h = true_alt_deg
    r = 1.02 / math.tan(math.radians(h + 10.3 / (h + 5.11)))
    r += 0.0019279  # makes the formula vanish at the zenith
    return r * _scale(pressure_mbar, temp_c)


def refraction_from_apparent_arcmin(
    apparent_alt_deg: float, pressure_mbar: float = 1010.0, temp_c: float = 10.0
) -> float:
    """Refraction in arcminutes to SUBTRACT from an apparent altitude (Bennett)."""
    h = apparent_alt_deg
    r = 1.0 / math.tan(math.radians(h + 7.31 / (h + 4.4)))
    return r * _scale(pressure_mbar, temp_c)


def true_to_apparent_alt(true_alt_deg: float, pressure_mbar: float = 1010.0, temp_c: float = 10.0) -> float:
    return true_alt_deg + refraction_from_true_arcmin(true_alt_deg, pressure_mbar, temp_c) / 60.0


def apparent_to_true_alt(app_alt_deg: float, pressure_mbar: float = 1010.0, temp_c: float = 10.0) -> float:
    return app_alt_deg - refraction_from_apparent_arcmin(app_alt_deg, pressure_mbar, temp_c) / 60.0
