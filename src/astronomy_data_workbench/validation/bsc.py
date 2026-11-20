"""Row-level validation of a BSC VizieR TSV table.

Outcome rules: any error -> rejected; otherwise any warning -> review; otherwise accepted.
Nothing is silently repaired: a malformed numeric field is kept as raw text, the normalized value
is left empty, and a NUMERIC_MALFORMED warning sends the row to manual review.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from astronomy_data_workbench.errors import SchemaError
from astronomy_data_workbench.schemas import bsc as schema
from astronomy_data_workbench.sources.bsc import (
    BscRecord,
    RawTable,
    parse_dec,
    parse_number,
    parse_ra,
)

from .config import ValidationConfig
from .issues import ACCEPTED, ERROR, INFO, REJECTED, REVIEW, WARNING, Issue

_DIGITS = re.compile(r"^\d+$")


@dataclass
class RowResult:
    line_number: int
    outcome: str
    issues: list[Issue]
    raw: dict[str, str] | list[str]
    record: BscRecord | None = None

    def to_dict(self) -> dict[str, Any]:
        raw: Any = self.raw if isinstance(self.raw, dict) else {"cells": self.raw}
        return {
            "line_number": self.line_number,
            "outcome": self.outcome,
            "issues": [i.to_dict() for i in self.issues],
            "raw": raw,
            "record": self.record.to_dict() if self.record else None,
        }


@dataclass
class ValidationResult:
    rows: list[RowResult] = field(default_factory=list)
    file_issues: list[Issue] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        c = Counter(r.outcome for r in self.rows)
        return {
            "total_rows": len(self.rows),
            "accepted": c[ACCEPTED],
            "rejected": c[REJECTED],
            "review": c[REVIEW],
        }

    def issue_code_counts(self) -> dict[str, int]:
        c = Counter(i.code for r in self.rows for i in r.issues)
        return dict(sorted(c.items()))


def check_header(header: list[str]) -> list[Issue]:
    """Fatal schema problems raise SchemaError; softer ones come back as file-level issues."""
    dupes = sorted({h for h in header if header.count(h) > 1})
    if dupes:
        raise SchemaError(f"duplicate column names in header: {', '.join(dupes)}")
    missing = [c for c in schema.REQUIRED_COLUMNS if c not in header]
    if missing:
        raise SchemaError(
            f"missing required columns: {', '.join(missing)}. Header found: {header!r}. "
            "Is this a tab-separated VizieR export? (Run `adw inspect` to see what was detected.)"
        )
    issues: list[Issue] = []
    for col in schema.EXPECTED_COLUMNS:
        if col not in header:
            issues.append(
                Issue("FILE_MISSING_COLUMN", WARNING, col,
                      f"expected column {col!r} is absent; its values are unavailable")
            )  # fmt: skip
    for col in header:
        if col not in schema.EXPECTED_COLUMNS:
            issues.append(
                Issue("FILE_EXTRA_COLUMN", INFO, col,
                      f"column {col!r} is not part of the expected schema; kept in raw fields only")
            )  # fmt: skip
    return issues


def validate_table(table: RawTable, config: ValidationConfig | None = None) -> ValidationResult:
    cfg = config or ValidationConfig()
    result = ValidationResult(file_issues=check_header(table.header))
    header = table.header
    col = {name: i for i, name in enumerate(header)}
    nulls = {m.strip() for m in cfg.null_markers}

    def cell(cells: list[str], name: str) -> str | None:
        """Stripped cell text, or None if the column is absent or the cell is a null marker."""
        if name not in col:
            return None
        text = cells[col[name]].strip()
        return None if text in nulls else text

    # Pass 1: find duplicate HR numbers (every occurrence is rejected).
    hr_counts: Counter[int] = Counter()
    for _, cells in table.rows:
        if len(cells) == len(header):
            text = cell(cells, "HR")
            if text is not None and _DIGITS.match(text):
                hr_counts[int(text)] += 1

    for line_number, cells in table.rows:
        if len(cells) != len(header):
            issue = Issue("ROW_COLUMN_COUNT", ERROR, None,
                          f"row has {len(cells)} fields, header has {len(header)}")  # fmt: skip
            result.rows.append(RowResult(line_number, REJECTED, [issue], list(cells)))
            continue
        raw = dict(zip(header, cells, strict=True))
        record = BscRecord(line_number=line_number, raw=raw)
        issues: list[Issue] = []

        # Identity
        hr_text = cell(cells, "HR")
        if hr_text is None:
            issues.append(Issue("HR_MISSING", ERROR, "HR", "HR number is empty"))
        elif not _DIGITS.match(hr_text):
            issues.append(Issue("HR_MALFORMED", ERROR, "HR", f"HR {hr_text!r} is not an integer"))
        else:
            record.hr = int(hr_text)
            if hr_counts[record.hr] > 1:
                issues.append(Issue("HR_DUPLICATE", ERROR, "HR",
                                    f"HR {record.hr} appears {hr_counts[record.hr]} times"))  # fmt: skip
        record.hd = cell(cells, "HD")
        record.name = cell(cells, "Name")

        # Position (required)
        for name, parser, attr in (("RAJ2000", parse_ra, "ra_deg"), ("DEJ2000", parse_dec, "dec_deg")):
            label = "RA" if name == "RAJ2000" else "DEC"
            text = cell(cells, name)
            if text is None:
                issues.append(Issue(f"{label}_MISSING", ERROR, name, f"{name} is empty"))
                continue
            value, err = parser(text)
            if err == "malformed":
                issues.append(Issue(f"{label}_MALFORMED", ERROR, name, f"cannot parse {text!r}"))
            elif err == "out_of_range":
                issues.append(Issue(f"{label}_OUT_OF_RANGE", ERROR, name, f"{text!r} is out of range"))
            else:
                setattr(record, attr, value)

        # Optional numerics (explicit status, no silent coercion)
        values: dict[str, float | None] = {}
        status: dict[str, str] = {}
        for name in schema.NUMERIC_OPTIONAL:
            if name not in col:
                status[name] = "absent"
                values[name] = None
                continue
            text = cell(cells, name)
            if text is None:
                status[name], values[name] = "null", None
                continue
            number = parse_number(text)
            if number is None:
                status[name], values[name] = "malformed", None
                issues.append(Issue("NUMERIC_MALFORMED", WARNING, name,
                                    f"cannot parse {text!r} as a number; raw value kept"))  # fmt: skip
            else:
                status[name], values[name] = "ok", number

        vmag = values["Vmag"]
        record.vmag = vmag
        if status["Vmag"] == "null":
            issues.append(Issue("VMAG_MISSING", WARNING, "Vmag",
                                "no V magnitude (possibly a non-stellar entry)"))  # fmt: skip
        elif vmag is not None and not cfg.vmag_min <= vmag <= cfg.vmag_max:
            issues.append(Issue("VMAG_OUT_OF_RANGE", WARNING, "Vmag",
                                f"Vmag {vmag} outside [{cfg.vmag_min}, {cfg.vmag_max}]"))  # fmt: skip

        # Proper motion: arcsec/yr -> mas/yr by explicit x1000; RA component already has cos(dec).
        pm_ra, pm_de = values["pmRA"], values["pmDE"]
        if pm_ra is not None:
            record.pm_ra_cosdec_mas_yr = pm_ra * schema.ARCSEC_TO_MAS
        if pm_de is not None:
            record.pm_dec_mas_yr = pm_de * schema.ARCSEC_TO_MAS
        if (status["pmRA"], status["pmDE"]) in (("ok", "null"), ("null", "ok")):
            issues.append(Issue("PM_INCOMPLETE", WARNING, None,
                                "only one proper-motion component is present"))  # fmt: skip
        if record.pm_ra_cosdec_mas_yr is not None and record.pm_dec_mas_yr is not None:
            total = math.hypot(record.pm_ra_cosdec_mas_yr, record.pm_dec_mas_yr)
            if total > cfg.pm_total_max_mas_yr:
                issues.append(Issue("PM_SUSPICIOUS", WARNING, None,
                                    f"total proper motion {total:.0f} mas/yr exceeds "
                                    f"{cfg.pm_total_max_mas_yr:.0f}"))  # fmt: skip

        # Parallax: arcsec -> mas.
        plx = values["Parallax"]
        if plx is not None:
            record.parallax_mas = plx * schema.ARCSEC_TO_MAS
            if record.parallax_mas < 0:
                # A negative measured parallax is a valid astrometric measurement (noise on
                # a small true parallax), not a data-quality fault: keep the signed value
                # and record an informational diagnostic that does not affect the outcome.
                issues.append(Issue("PARALLAX_NEGATIVE", INFO, "Parallax",
                                    f"negative measured parallax {record.parallax_mas:.1f} mas "
                                    "(kept as measured; not a validation failure)"))  # fmt: skip
            elif record.parallax_mas > cfg.parallax_max_mas:
                issues.append(Issue("PARALLAX_SUSPICIOUS", WARNING, "Parallax",
                                    f"parallax {record.parallax_mas:.1f} mas exceeds "
                                    f"{cfg.parallax_max_mas:.0f}"))  # fmt: skip

        # Radial velocity (km/s, unchanged).
        rv = values["RadVel"]
        record.radial_velocity_km_s = rv
        if rv is not None and abs(rv) > cfg.radial_velocity_abs_max_km_s:
            issues.append(Issue("RADVEL_SUSPICIOUS", WARNING, "RadVel",
                                f"|RadVel| {abs(rv)} km/s exceeds "
                                f"{cfg.radial_velocity_abs_max_km_s}"))  # fmt: skip

        if any(i.severity == ERROR for i in issues):
            outcome = REJECTED
        elif any(i.severity == WARNING for i in issues):
            outcome = REVIEW
        else:
            outcome = ACCEPTED
        result.rows.append(RowResult(line_number, outcome, issues, raw, record))

    return result
