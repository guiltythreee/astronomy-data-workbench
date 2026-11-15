"""Typed BSC record. Raw cells are kept alongside normalized values."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from astronomy_data_workbench.schemas import bsc as schema


@dataclass
class BscRecord:
    line_number: int
    raw: dict[str, str]
    hr: int | None = None
    hd: str | None = None
    name: str | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    vmag: float | None = None
    pm_ra_cosdec_mas_yr: float | None = None
    pm_dec_mas_yr: float | None = None
    parallax_mas: float | None = None
    radial_velocity_km_s: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": {
                "source_catalogue": "BSC",
                "source_catalogue_id": "V/50",
                "hr": self.hr,
                "hd": self.hd,
                "name": self.name,
            },
            "position": {
                "ra_deg": self.ra_deg,
                "dec_deg": self.dec_deg,
                "frame": schema.FRAME,
                "equinox": schema.EQUINOX,
                "epoch": schema.EPOCH,
            },
            "astrometry": {
                "pm_ra_cosdec_mas_yr": self.pm_ra_cosdec_mas_yr,
                "pm_dec_mas_yr": self.pm_dec_mas_yr,
                "pm_ra_convention": schema.PM_RA_CONVENTION,
                "parallax_mas": self.parallax_mas,
                "radial_velocity_km_s": self.radial_velocity_km_s,
            },
            "photometry": {"vmag": self.vmag, "passband": schema.PASSBAND},
        }
