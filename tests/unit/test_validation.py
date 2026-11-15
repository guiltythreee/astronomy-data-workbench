import pytest

from astronomy_data_workbench.errors import SchemaError, SourceError
from astronomy_data_workbench.sources.bsc import read_raw_table
from astronomy_data_workbench.validation import (
    ACCEPTED,
    REJECTED,
    REVIEW,
    ValidationConfig,
    validate_table,
)  # fmt: skip
from conftest import HEADER, row


def run(make_tsv, rows, cfg=None, **kw):
    return validate_table(read_raw_table(make_tsv(rows, **kw)), cfg)


def codes(result, i=0):
    return {x.code for x in result.rows[i].issues}


def test_valid_row_is_accepted_with_normalized_values(make_tsv):
    r = run(make_tsv, [row(ra="06 45 08.9", dec="-16 42 58", pmra="-0.546", pmde="-1.223",
                           plx="0.379", rv="-7.6")])  # fmt: skip
    res = r.rows[0]
    assert res.outcome == ACCEPTED and res.record is not None
    assert res.record.hr == 1
    assert res.record.raw["RAJ2000"] == "06 45 08.9"  # raw preserved
    assert res.record.parallax_mas == pytest.approx(379.0)
    assert res.record.radial_velocity_km_s == -7.6


def test_pm_is_x1000_only_and_cos_dec_not_applied_again(make_tsv):
    r = run(make_tsv, [row(dec="+60 00 00", pmra="0.1", pmde="0.2")])
    rec = r.rows[0].record
    assert rec is not None
    assert rec.pm_ra_cosdec_mas_yr == pytest.approx(100.0)  # not 100*cos(60deg)=50
    assert rec.pm_dec_mas_yr == pytest.approx(200.0)


def test_metadata_is_explicit_in_record(make_tsv):
    rec = run(make_tsv, [row()]).rows[0].record
    assert rec is not None
    d = rec.to_dict()
    assert d["position"]["frame"] == "FK5"
    assert d["position"]["equinox"] == "J2000"
    assert d["position"]["epoch"] == "J2000.0"
    assert "cos(dec)" in d["astrometry"]["pm_ra_convention"]
    assert d["photometry"]["passband"] == "Johnson V"


def test_duplicate_hr_rejects_every_occurrence(make_tsv):
    r = run(make_tsv, [row(hr="5"), row(hr="5"), row(hr="6")])
    assert [x.outcome for x in r.rows] == [REJECTED, REJECTED, ACCEPTED]
    assert "HR_DUPLICATE" in codes(r, 0)


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"hr": ""}, "HR_MISSING"),
        ({"hr": "1x"}, "HR_MALFORMED"),
        ({"ra": ""}, "RA_MISSING"),
        ({"ra": "zz"}, "RA_MALFORMED"),
        ({"ra": "24 00 00"}, "RA_OUT_OF_RANGE"),
        ({"dec": ""}, "DEC_MISSING"),
        ({"dec": "+91 00 00"}, "DEC_OUT_OF_RANGE"),
    ],
)
def test_hard_errors_reject(make_tsv, kwargs, code):
    r = run(make_tsv, [row(**kwargs)])
    assert r.rows[0].outcome == REJECTED
    assert code in codes(r)


def test_wrong_column_count_is_rejected_with_line_number(make_tsv):
    path = make_tsv([row(hr="1"), ["2", "short"]])
    r = validate_table(read_raw_table(path))
    bad = r.rows[1]
    assert bad.outcome == REJECTED and "ROW_COLUMN_COUNT" in {i.code for i in bad.issues}
    assert bad.line_number == 6  # comment, header, units, dashes, data row 1, data row 2


def test_malformed_optional_numeric_goes_to_review_not_null(make_tsv):
    r = run(make_tsv, [row(pmra="abc")])
    res = r.rows[0]
    assert res.outcome == REVIEW and "NUMERIC_MALFORMED" in codes(r)
    assert res.record is not None and res.record.pm_ra_cosdec_mas_yr is None
    assert res.raw["pmRA"] == "abc"  # original kept


def test_nan_is_malformed_not_a_number(make_tsv):
    assert run(make_tsv, [row(vmag="NaN")]).rows[0].outcome == REVIEW


def test_custom_null_marker_is_explicit(make_tsv):
    rows = [row(rv="--")]
    assert run(make_tsv, rows).rows[0].outcome == REVIEW  # '--' is malformed by default
    cfg = ValidationConfig(null_markers=("", "--"))
    assert run(make_tsv, rows, cfg).rows[0].outcome == ACCEPTED


def test_suspicious_values_go_to_review(make_tsv):
    cases = {
        "VMAG_MISSING": row(vmag=""),
        "VMAG_OUT_OF_RANGE": row(vmag="15"),
        "PM_INCOMPLETE": row(pmra="0.1", pmde=""),
        "PM_SUSPICIOUS": row(pmra="9.0", pmde="9.0"),
        "PARALLAX_NEGATIVE": row(plx="-0.01"),
        "PARALLAX_SUSPICIOUS": row(plx="2.0"),
        "RADVEL_SUSPICIOUS": row(rv="900"),
    }
    for code, r_ in cases.items():
        res = run(make_tsv, [r_])
        assert res.rows[0].outcome == REVIEW and code in codes(res), code


def test_missing_required_column_is_fatal(make_tsv):
    path = make_tsv([["1", "1.0"]], header=["HR", "Vmag"])
    with pytest.raises(SchemaError, match="RAJ2000"):
        validate_table(read_raw_table(path))


def test_duplicate_header_is_fatal(make_tsv):
    path = make_tsv([["1"] * 4], header=["HR", "HR", "RAJ2000", "DEJ2000"])
    with pytest.raises(SchemaError, match="duplicate"):
        validate_table(read_raw_table(path))


def test_missing_optional_column_is_reported_not_hidden(make_tsv):
    header = [h for h in HEADER if h != "Parallax"]
    r = run(make_tsv, [[c for c, h in zip(row(), HEADER, strict=True) if h != "Parallax"]],
            header=header)  # fmt: skip
    assert any(i.code == "FILE_MISSING_COLUMN" and i.field == "Parallax" for i in r.file_issues)
    assert r.rows[0].outcome == ACCEPTED


def test_bom_and_crlf_are_handled(make_tsv):
    path = make_tsv([row()], newline="\r\n", bom=True)
    table = read_raw_table(path)
    assert table.has_bom and table.line_endings["CRLF"] > 0
    assert validate_table(table).rows[0].outcome == ACCEPTED


def test_non_utf8_is_refused_not_guessed(tmp_path):
    p = tmp_path / "latin.tsv"
    p.write_bytes("HR\tRAJ2000\tDEJ2000\n1\t01 00 00\t+10 00 00 \xe9\n".encode("latin-1"))
    with pytest.raises(SourceError, match="UTF-8"):
        read_raw_table(p)


def test_no_units_or_dashes_rows(make_tsv):
    r = run(make_tsv, [row(), row(hr="2")], units=False)
    assert [x.outcome for x in r.rows] == [ACCEPTED, ACCEPTED]
