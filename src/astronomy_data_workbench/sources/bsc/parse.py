"""Strict scalar parsers. Each returns (value, error) and never guesses.

error is None, "malformed" (cannot be parsed) or "out_of_range" (parsed but impossible).
Coordinates: 'HH MM SS.s' / 'HH:MM:SS.s' sexagesimal (RA in hours) or a plain decimal number
(degrees). A bare integer such as '12' is read as decimal degrees, not hours.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
_SEXAGESIMAL = re.compile(
    r"^(?P<sign>[+-])?(?P<a>\d{1,3})[ :]+(?P<b>\d{1,2})(?:[ :]+(?P<c>\d{1,2}(?:\.\d*)?))?$"
)


def parse_number(text: str) -> float | None:
    """Plain decimal number, or None. Rejects NaN/inf, underscores and anything odd."""
    s = text.strip()
    if not _NUMBER.match(s):
        return None
    return float(s)


def _sexagesimal(s: str) -> tuple[float, float, float, float] | None:
    m = _SEXAGESIMAL.match(s)
    if m is None:
        return None
    sign = -1.0 if m.group("sign") == "-" else 1.0
    c = m.group("c")
    return sign, float(m.group("a")), float(m.group("b")), float(c) if c else 0.0


def coordinate_style(text: str) -> str:
    s = text.strip()
    if _sexagesimal(s) is not None:
        return "sexagesimal"
    if parse_number(s) is not None:
        return "decimal"
    return "unparseable"


def parse_ra(text: str) -> tuple[float | None, str | None]:
    """Right ascension -> degrees in [0, 360)."""
    s = text.strip()
    parts = _sexagesimal(s)
    if parts is not None:
        sign, h, m, sec = parts
        if sign < 0 or h >= 24 or m >= 60 or sec >= 60:
            return None, "out_of_range"
        return (h + m / 60.0 + sec / 3600.0) * 15.0, None
    value = parse_number(s)
    if value is None:
        return None, "malformed"
    if not 0.0 <= value < 360.0:
        return None, "out_of_range"
    return value, None


def parse_dec(text: str) -> tuple[float | None, str | None]:
    """Declination -> degrees in [-90, +90]. The sign applies to the whole value ('-00 30 12')."""
    s = text.strip()
    parts = _sexagesimal(s)
    if parts is not None:
        sign, d, m, sec = parts
        if m >= 60 or sec >= 60:
            return None, "out_of_range"
        total = d + m / 60.0 + sec / 3600.0
        if total > 90.0:
            return None, "out_of_range"
        return sign * total, None
    value = parse_number(s)
    if value is None:
        return None, "malformed"
    if not -90.0 <= value <= 90.0:
        return None, "out_of_range"
    return value, None
