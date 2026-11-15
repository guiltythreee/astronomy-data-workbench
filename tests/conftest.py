from __future__ import annotations

from pathlib import Path

import pytest

HEADER = ["HR", "Name", "HD", "RAJ2000", "DEJ2000", "Vmag", "pmRA", "pmDE", "Parallax", "RadVel"]
FIXTURE = Path(__file__).parent / "fixtures" / "bsc_synthetic.tsv"


def row(hr="1", name="X", hd="1", ra="01 00 00.0", dec="+10 00 00", vmag="5.0",
        pmra="0.0", pmde="0.0", plx="0.01", rv="1.0"):  # fmt: skip
    return [hr, name, hd, ra, dec, vmag, pmra, pmde, plx, rv]


@pytest.fixture
def make_tsv(tmp_path: Path):
    """Build a VizieR-style TSV in tmp_path. Options cover BOM and line endings."""

    def _make(rows, header=HEADER, newline="\n", bom=False, name="t.tsv", units=True):
        lines = ["# synthetic test file"]
        lines.append("\t".join(header))
        if units:
            lines.append("\t".join([""] * len(header)))
            lines.append("\t".join(["----"] * len(header)))
        lines += ["\t".join(r) for r in rows]
        data = (newline.join(lines) + newline).encode("utf-8")
        if bom:
            data = b"\xef\xbb\xbf" + data
        path = tmp_path / name
        path.write_bytes(data)
        return path

    return _make
