"""Describe a file without changing it and without validating row contents."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from astronomy_data_workbench.provenance import sha256_file
from astronomy_data_workbench.schemas import bsc as schema
from astronomy_data_workbench.sources.bsc import coordinate_style, parse_number, read_raw_table

_DELIMITERS = {"tab": "\t", "comma": ",", "semicolon": ";", "pipe": "|"}


def _detect_delimiter(header_line: str) -> str:
    counts = {name: header_line.count(ch) for name, ch in _DELIMITERS.items()}
    best = max(counts, key=lambda k: counts[k])
    return best if counts[best] > 0 else "none"


def inspect_file(path: Path) -> dict[str, Any]:
    table = read_raw_table(path)
    header = table.header
    col = {name: i for i, name in enumerate(header)}

    width_hist = Counter(len(cells) for _, cells in table.rows)

    # Non-numeric tokens in numeric columns: candidates for null markers (never auto-applied).
    token_counts: Counter[str] = Counter()
    for _, cells in table.rows:
        if len(cells) != len(header):
            continue
        for name in schema.NUMERIC_OPTIONAL:
            if name in col:
                text = cells[col[name]].strip()
                if text != "" and parse_number(text) is None:
                    token_counts[text] += 1
    empty_cells = sum(
        1
        for _, cells in table.rows
        if len(cells) == len(header)
        for name in schema.NUMERIC_OPTIONAL
        if name in col and cells[col[name]].strip() == ""
    )

    styles: dict[str, str] = {}
    for name in ("RAJ2000", "DEJ2000"):
        if name in col:
            seen = {
                coordinate_style(cells[col[name]])
                for _, cells in table.rows
                if len(cells) == len(header) and cells[col[name]].strip()
            }
            styles[name] = (
                "unknown" if not seen else next(iter(seen)) if len(seen) == 1 else "mixed"
            )

    missing_required = [c for c in schema.REQUIRED_COLUMNS if c not in header]
    probable = (
        schema.SCHEMA_VERSION
        if not missing_required and set(header) <= set(schema.EXPECTED_COLUMNS)
        else "unknown"
    )
    return {
        "file_name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "encoding": table.encoding,
        "has_bom": table.has_bom,
        "line_endings": table.line_endings,
        "delimiter": _detect_delimiter(table.header_line),
        "comment_lines": table.comment_line_count,
        "blank_lines": table.blank_line_count,
        "header": header,
        "units_row": table.units,
        "has_dashes_row": table.has_dashes_row,
        "data_row_count": len(table.rows),
        "row_width_histogram": {str(k): v for k, v in sorted(width_hist.items())},
        "missing_required_columns": missing_required,
        "missing_expected_columns": [c for c in schema.EXPECTED_COLUMNS if c not in header],
        "unexpected_columns": [c for c in header if c not in schema.EXPECTED_COLUMNS],
        "empty_numeric_cells": empty_cells,
        "non_numeric_tokens_in_numeric_columns": dict(sorted(token_counts.items())),
        "coordinate_styles": styles,
        "probable_schema": probable,
    }
