"""Astronomical Cross-Matching Workbench (module 03).

Status: PARTIAL and UNVERIFIED. Epoch-corrected positional matching with preserved candidates,
manual-review routing and recorded evidence is implemented and tested on SYNTHETIC data only. It
has not been validated against real BSC, Hipparcos or Gaia records; that is a separate gate.

Import the engine from `matching.engine` (it needs numpy); this package initialiser stays light
so the rest of the `adw` CLI works without numpy.
"""

from astronomy_data_workbench.matching.models import (
    UNVERIFIED_BANNER,
    VALIDATION_GATE,
    VALIDATION_STATUS,
)

__all__ = ["UNVERIFIED_BANNER", "VALIDATION_GATE", "VALIDATION_STATUS"]
