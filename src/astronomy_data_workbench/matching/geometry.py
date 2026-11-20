"""Sky geometry helpers: unit vectors and angular separation. Pure numpy, no Astropy."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

MAS_PER_RAD = 180.0 / math.pi * 3600.0 * 1000.0
MAS_TO_RAD = 1.0 / MAS_PER_RAD

Vec = NDArray[np.float64]


def unit_vector(ra_deg: float, dec_deg: float) -> Vec:
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    return np.array(
        [math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)],
        dtype=np.float64,
    )


def tangent_basis(ra_deg: float, dec_deg: float) -> tuple[Vec, Vec, Vec]:
    """Unit vectors (position, east, north) at a point. Well defined at the poles."""
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    p = unit_vector(ra_deg, dec_deg)
    east = np.array([-math.sin(ra), math.cos(ra), 0.0], dtype=np.float64)
    north = np.array(
        [-math.sin(dec) * math.cos(ra), -math.sin(dec) * math.sin(ra), math.cos(dec)],
        dtype=np.float64,
    )
    return p, east, north


def to_ra_dec(v: Vec) -> tuple[float, float]:
    n = v / np.linalg.norm(v)
    ra = math.degrees(math.atan2(float(n[1]), float(n[0]))) % 360.0
    dec = math.degrees(math.asin(max(-1.0, min(1.0, float(n[2])))))
    return ra, dec


def separation_mas(a: Vec, b: Vec) -> float:
    """Angular separation of two unit vectors in mas (chord formula, exact at small angles)."""
    chord = float(np.linalg.norm(a - b))
    return 2.0 * math.asin(min(1.0, chord / 2.0)) * MAS_PER_RAD


def separations_mas(vectors: NDArray[np.float64], v: Vec) -> NDArray[np.float64]:
    """Separations in mas between each row of `vectors` (N x 3) and the unit vector `v`."""
    chord = np.linalg.norm(vectors - v, axis=1)
    result: NDArray[np.float64] = 2.0 * np.arcsin(np.minimum(1.0, chord / 2.0)) * MAS_PER_RAD
    return result
