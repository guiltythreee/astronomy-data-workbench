"""Issue and outcome definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ERROR = "error"      # hard failure -> row rejected
WARNING = "warning"  # suspicious / needs judgement -> row goes to manual review
INFO = "info"        # file-level note only

ACCEPTED = "accepted"
REJECTED = "rejected"
REVIEW = "review"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    field: str | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
        }
