"""Validation configuration. It is written into every audit bundle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

CONFIG_VERSION = "1"


@dataclass(frozen=True)
class ValidationConfig:
    # Only an empty cell is a null by default. Add others explicitly, e.g. ("", "--").
    null_markers: tuple[str, ...] = ("",)
    vmag_min: float = -2.0
    vmag_max: float = 8.5
    pm_total_max_mas_yr: float = 11000.0
    parallax_max_mas: float = 1000.0
    radial_velocity_abs_max_km_s: float = 500.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["null_markers"] = list(self.null_markers)
        return data
