"""Read a VizieR-style TSV into a raw table without interpreting any values.

Layout handled: optional '#' comment lines, one header row, then optionally a units row
and/or a dashes row (`----`), then data rows. Raw cell text is kept exactly as found.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from astronomy_data_workbench.errors import SchemaError, SourceError

_DASHES = re.compile(r"^-+$")
_LINE_SPLIT = re.compile(r"\r\n|\r|\n")
_LINE_ENDING = re.compile(r"\r\n|\r|\n")


@dataclass
class RawTable:
    encoding: str
    has_bom: bool
    line_endings: dict[str, int]
    comment_line_count: int
    blank_line_count: int
    header_line: str
    header: list[str]
    units: list[str] | None
    has_dashes_row: bool
    rows: list[tuple[int, list[str]]] = field(default_factory=list)  # (file line no., cells)


def _decode(data: bytes) -> tuple[str, str, bool]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8", True
    try:
        return data.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError as exc:
        raise SourceError(
            f"file is not valid UTF-8 ({exc.reason} at byte {exc.start}); "
            "ADW will not guess another encoding. Re-export or convert the file explicitly."
        ) from exc


def _is_dashes_row(cells: list[str]) -> bool:
    return len(cells) > 0 and all(_DASHES.match(c.strip()) for c in cells)


def read_raw_table(path: Path) -> RawTable:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise SourceError(f"cannot read {path}: {exc}") from exc
    text, encoding, has_bom = _decode(data)

    endings = {"CRLF": 0, "LF": 0, "CR": 0}
    for match in _LINE_ENDING.finditer(text):
        token = match.group(0)
        endings["CRLF" if token == "\r\n" else "LF" if token == "\n" else "CR"] += 1

    lines = _LINE_SPLIT.split(text)
    if lines and lines[-1] == "":
        lines.pop()  # text ended with a line ending

    comments = 0
    blanks = 0
    content: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if line.startswith("#"):
            comments += 1
        elif line.strip() == "":
            blanks += 1
        else:
            content.append((number, line))
    if not content:
        raise SchemaError("no header row found (file is empty or only comments)")

    header_line = content[0][1]
    header = [c.strip() for c in header_line.split("\t")]
    rest = content[1:]

    units: list[str] | None = None
    has_dashes = False
    start = 0
    if len(rest) >= 2 and _is_dashes_row(rest[1][1].split("\t")):
        units = [c.strip() for c in rest[0][1].split("\t")]
        has_dashes = True
        start = 2
    elif rest and _is_dashes_row(rest[0][1].split("\t")):
        has_dashes = True
        start = 1

    return RawTable(
        encoding=encoding,
        has_bom=has_bom,
        line_endings=endings,
        comment_line_count=comments,
        blank_line_count=blanks,
        header_line=header_line,
        header=header,
        units=units,
        has_dashes_row=has_dashes,
        rows=[(n, line.split("\t")) for n, line in rest[start:]],
    )
