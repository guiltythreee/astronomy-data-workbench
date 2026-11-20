"""Property-based tests: invariants must hold for any input, not just hand-picked cases."""

import math

import pytest

pytest.importorskip("hypothesis")

from hypothesis import given, settings
from hypothesis import strategies as st

from astronomy_data_workbench.sources.bsc import RawTable, parse_dec, parse_number, parse_ra
from astronomy_data_workbench.validation import ACCEPTED, REJECTED, REVIEW, validate_table
from conftest import HEADER


@given(st.floats(min_value=0, max_value=359.999999, allow_nan=False))
def test_decimal_ra_stays_in_range(value):
    got, err = parse_ra(f"{value:.6f}")
    assert err is None and got is not None and 0.0 <= got < 360.0


@given(st.integers(0, 23), st.integers(0, 59), st.floats(0, 59.99, allow_nan=False))
def test_sexagesimal_ra_stays_in_range(h, m, s):
    got, err = parse_ra(f"{h:02d} {m:02d} {s:05.2f}")
    assert err is None and got is not None and 0.0 <= got < 360.0


@given(st.integers(0, 89), st.integers(0, 59), st.integers(0, 59))
def test_dec_sign_is_symmetric_including_zero_degrees(d, m, s):
    plus, e1 = parse_dec(f"+{d:02d} {m:02d} {s:02d}")
    minus, e2 = parse_dec(f"-{d:02d} {m:02d} {s:02d}")
    assert e1 is None and e2 is None and plus is not None and minus is not None
    assert math.isclose(plus, -minus, abs_tol=1e-12)
    assert -90.0 <= minus <= plus <= 90.0


@given(st.text(max_size=30))
def test_parse_number_never_returns_nan_or_inf(text):
    value = parse_number(text)
    assert value is None or math.isfinite(value)


@given(st.text(max_size=20), st.text(max_size=20))
def test_coordinate_parsers_never_crash(a, b):
    for fn in (parse_ra, parse_dec):
        value, err = fn(a + b)
        assert (value is None) == (err is not None)


cell = st.text(alphabet=st.characters(blacklist_characters="\t\r\n\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"),
               max_size=12)  # fmt: skip


@settings(max_examples=200)
@given(st.lists(st.lists(cell, min_size=0, max_size=12), max_size=8))
def test_validator_never_crashes_and_always_classifies(rows):
    table = RawTable(
        encoding="utf-8", has_bom=False, line_endings={}, comment_line_count=0,
        blank_line_count=0, header_line="\t".join(HEADER), header=list(HEADER),
        units=None, has_dashes_row=False, rows=list(enumerate(rows, start=5)),
    )  # fmt: skip
    result = validate_table(table)
    assert len(result.rows) == len(rows)
    for r in result.rows:
        assert r.outcome in {ACCEPTED, REVIEW, REJECTED}
        if r.outcome != ACCEPTED:
            assert r.issues  # never rejected/reviewed without a stated reason
