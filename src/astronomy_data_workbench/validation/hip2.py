"""Validation of VizieR I/311/hip2 TSV exports.

The source rows are preserved verbatim. Negative parallaxes are valid measurements and are
reported as informational diagnostics; unusually large proper motions are not rejected.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from astronomy_data_workbench.errors import SchemaError
from astronomy_data_workbench.sources.bsc.tsv import RawTable
from astronomy_data_workbench.sources.hipparcos import hip2 as schema
from astronomy_data_workbench.validation.issues import (
    ACCEPTED, ERROR, INFO, REJECTED, REVIEW, WARNING, Issue,
)

_INT = re.compile(r"^[0-9]+$")
_NUMERIC = ("RArad", "e_RArad", "DErad", "e_DErad", "Plx", "e_Plx", "pmRA",
            "e_pmRA", "pmDE", "e_pmDE", "Hpmag", "e_Hpmag", "B-V", "e_B-V")
_ASTROMETRIC_ERRORS = ("e_RArad", "e_DErad", "e_Plx", "e_pmRA", "e_pmDE")

@dataclass
class Hip2RowResult:
    line_number: int
    outcome: str
    issues: list[Issue]
    raw: dict[str, str]
    normalized: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {"line_number": self.line_number, "outcome": self.outcome,
                "issues": [issue.to_dict() for issue in self.issues],
                "raw": self.raw, "record": self.normalized}

@dataclass
class Hip2ValidationResult:
    rows: list[Hip2RowResult] = field(default_factory=list)
    file_issues: list[Issue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=lambda: {
        "catalogue": schema.SOURCE_NAME, "schema": schema.SCHEMA_VERSION,
        "frame": schema.FRAME, "epoch_jyear": schema.EPOCH_JYEAR,
        "position_units": schema.POSITION_UNITS,
        "astrometric_error_units": schema.ASTROMETRIC_ERROR_UNITS,
        "proper_motion_units": schema.PROPER_MOTION_UNITS,
    })

    def counts(self) -> dict[str, int]:
        c = Counter(row.outcome for row in self.rows)
        return {"total_rows": len(self.rows), "accepted": c[ACCEPTED],
                "review": c[REVIEW], "rejected": c[REJECTED]}

    def issue_code_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(i.code for r in self.rows for i in r.issues).items()))


def _number(value: str) -> float | None:
    try:
        result = float(value)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def validate_hip2_table(table: RawTable) -> Hip2ValidationResult:
    header = table.header
    duplicates = sorted({name for name in header if header.count(name) > 1})
    if duplicates:
        raise SchemaError(f"duplicate Hipparcos-2 column names: {', '.join(duplicates)}")
    missing = [name for name in schema.REQUIRED_COLUMNS if name not in header]
    if missing:
        raise SchemaError(f"missing required Hipparcos-2 columns: {', '.join(missing)}")
    col = {name: index for index, name in enumerate(header)}
    result = Hip2ValidationResult()
    for name in schema.EXPECTED_COLUMNS:
        if name not in col:
            result.file_issues.append(Issue("FILE_MISSING_COLUMN", WARNING, name,
                f"optional Hipparcos-2 field {name!r} is absent"))
    for name in header:
        if name not in schema.EXPECTED_COLUMNS:
            result.file_issues.append(Issue("FILE_EXTRA_COLUMN", INFO, name,
                f"unrecognised column {name!r} is preserved in raw fields"))

    hip_ids: Counter[int] = Counter()
    for _, cells in table.rows:
        if len(cells) == len(header):
            text = cells[col["HIP"]].strip()
            if _INT.fullmatch(text):
                hip_ids[int(text)] += 1

    for line, cells in table.rows:
        issues: list[Issue] = []
        if len(cells) != len(header):
            result.rows.append(Hip2RowResult(line, REJECTED,
                [Issue("ROW_COLUMN_COUNT", ERROR, None,
                       f"expected {len(header)} cells, found {len(cells)}")],
                {"cells": "\t".join(cells)}, None))
            continue
        raw = {name: cells[i] for i, name in enumerate(header)}
        hip_text = raw["HIP"].strip()
        hip: int | None = int(hip_text) if _INT.fullmatch(hip_text) else None
        if hip is None:
            issues.append(Issue("HIP_MISSING" if not hip_text else "HIP_MALFORMED", ERROR,
                                "HIP", "HIP must be a positive integer identifier"))
        elif hip <= 0:
            issues.append(Issue("HIP_OUT_OF_RANGE", ERROR, "HIP", "HIP must be positive"))
        elif hip_ids[hip] > 1:
            issues.append(Issue("HIP_DUPLICATE", ERROR, "HIP",
                                f"HIP identifier {hip} occurs {hip_ids[hip]} times"))

        values: dict[str, float | None] = {}
        for name in _NUMERIC:
            if name not in col:
                values[name] = None
                continue
            text = raw[name].strip()
            if not text:
                values[name] = None
                continue
            number = _number(text)
            values[name] = number
            if number is None:
                issues.append(Issue("NUMERIC_MALFORMED", WARNING, name,
                                    f"{name} is not a finite numeric value"))

        ra, dec = values["RArad"], values["DErad"]
        if ra is None:
            issues.append(Issue("RA_MISSING" if not raw["RArad"].strip() else "RA_MALFORMED",
                                ERROR, "RArad", "right ascension is required in degrees"))
        elif not 0.0 <= ra < 360.0:
            issues.append(Issue("RA_OUT_OF_RANGE", ERROR, "RArad",
                                f"right ascension {ra} is outside [0, 360) degrees"))
        if dec is None:
            issues.append(Issue("DEC_MISSING" if not raw["DErad"].strip() else "DEC_MALFORMED",
                                ERROR, "DErad", "declination is required in degrees"))
        elif not -90.0 <= dec <= 90.0:
            issues.append(Issue("DEC_OUT_OF_RANGE", ERROR, "DErad",
                                f"declination {dec} is outside [-90, 90] degrees"))

        for name in _ASTROMETRIC_ERRORS:
            value = values.get(name)
            if value is not None and value <= 0:
                issues.append(Issue("ASTROMETRIC_ERROR_NONPOSITIVE", WARNING, name,
                                    f"{name} must be positive when supplied"))
        for name in ("e_Hpmag", "e_B-V"):
            value = values.get(name)
            if value is not None and value < 0:
                issues.append(Issue("PHOTOMETRIC_ERROR_NEGATIVE", WARNING, name,
                                    f"{name} cannot be negative"))

        parallax = values.get("Plx")
        if parallax is not None and parallax < 0:
            issues.append(Issue("PARALLAX_NEGATIVE", INFO, "Plx",
                                "negative measured parallax is retained as a valid observation"))
        normalized: dict[str, Any] = {
            "HIP": hip, "position": {"ra_deg": ra, "dec_deg": dec,
                                      "frame": schema.FRAME, "epoch_jyear": schema.EPOCH_JYEAR},
            "astrometry": {name: values.get(name) for name in
                           ("Plx", "e_Plx", "pmRA", "e_pmRA", "pmDE", "e_pmDE")},
            "photometry": {name: values.get(name) for name in ("Hpmag", "e_Hpmag", "B-V", "e_B-V")},
        }
        if any(issue.severity == ERROR for issue in issues):
            outcome = REJECTED
        elif any(issue.severity == WARNING for issue in issues):
            outcome = REVIEW
        else:
            outcome = ACCEPTED
        result.rows.append(Hip2RowResult(line, outcome, issues, raw, normalized))
    return result
