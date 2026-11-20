from __future__ import annotations

import pytest

from astronomy_data_workbench.errors import SchemaError
from astronomy_data_workbench.sources.bsc.tsv import read_raw_table
from astronomy_data_workbench.validation.hip2 import validate_hip2_table
from astronomy_data_workbench.validation.issues import ACCEPTED, REJECTED, REVIEW, INFO

HEADER = ["HIP", "RArad", "e_RArad", "DErad", "e_DErad", "Plx", "e_Plx", "pmRA",
          "e_pmRA", "pmDE", "e_pmDE", "Hpmag", "e_Hpmag", "B-V", "e_B-V", "HIP1"]


def make_file(tmp_path, rows, header=HEADER):
    units = ["", "deg", "mas", "deg", "mas", "mas", "mas", "mas/yr", "mas/yr",
             "mas/yr", "mas/yr", "mag", "mag", "mag", "mag", ""]
    dashes = ["----"] * len(header)
    lines = ["# Coosys J2000_1991.250: eq_FK5 J2000", "\t".join(header),
             "\t".join(units[:len(header)]), "\t".join(dashes)]
    lines.extend("\t".join(row) for row in rows)
    path = tmp_path / "hip2.tsv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def valid_row(**overrides):
    row = {name: "1.0" for name in HEADER}
    row.update({"HIP": "1", "RArad": "359.9", "e_RArad": "0.5", "DErad": "-90",
                "e_DErad": "0.6", "Plx": "-5.0", "e_Plx": "1.0", "pmRA": "6768",
                "e_pmRA": "1.0", "pmDE": "10328", "e_pmDE": "1.0", "Hpmag": "8.0",
                "e_Hpmag": "0.01", "B-V": "0.5", "e_B-V": "0.0", "HIP1": "HIP1"})
    row.update(overrides)
    return [row[name] for name in HEADER]


def validate(tmp_path, rows, header=HEADER):
    return validate_hip2_table(read_raw_table(make_file(tmp_path, rows, header)))


def test_realistic_extremes_and_negative_parallax_are_accepted(tmp_path):
    result = validate(tmp_path, [valid_row()])
    row = result.rows[0]
    assert row.outcome == ACCEPTED
    assert row.normalized["position"] == {
        "ra_deg": 359.9, "dec_deg": -90.0, "frame": "ICRS", "epoch_jyear": 1991.25}
    assert row.normalized["astrometry"]["Plx"] == -5.0
    diagnostic = next(issue for issue in row.issues if issue.code == "PARALLAX_NEGATIVE")
    assert diagnostic.severity == INFO


def test_zero_colour_uncertainty_is_valid(tmp_path):
    assert validate(tmp_path, [valid_row(**{"e_B-V": "0.0"})]).rows[0].outcome == ACCEPTED


def test_large_proper_motion_is_not_rejected(tmp_path):
    result = validate(tmp_path, [valid_row(pmRA="6768", pmDE="10328")])
    assert result.rows[0].outcome == ACCEPTED


def test_missing_vmag_equivalent_photometry_does_not_get_hidden(tmp_path):
    result = validate(tmp_path, [valid_row(RArad="", Hpmag="")])
    assert result.rows[0].outcome == REJECTED
    assert "RA_MISSING" in {issue.code for issue in result.rows[0].issues}


def test_duplicate_hip_rejects_every_occurrence(tmp_path):
    result = validate(tmp_path, [valid_row(), valid_row()])
    assert [row.outcome for row in result.rows] == [REJECTED, REJECTED]
    assert all("HIP_DUPLICATE" in {i.code for i in row.issues} for row in result.rows)


def test_invalid_positions_rejected(tmp_path):
    result = validate(tmp_path, [valid_row(RArad="360"), valid_row(HIP="2", DErad="90.1")])
    assert [row.outcome for row in result.rows] == [REJECTED, REJECTED]


def test_missing_required_column_is_fatal(tmp_path):
    with pytest.raises(SchemaError, match="RArad"):
        validate(tmp_path, [["1", "10"]], ["HIP", "DErad"])
