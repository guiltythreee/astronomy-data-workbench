import math

import pytest

from astronomy_data_workbench.sources.bsc import parse_dec, parse_number, parse_ra


def test_ra_sexagesimal_to_degrees():
    value, err = parse_ra("01 08 23.2")
    assert err is None
    assert value == pytest.approx((1 + 8 / 60 + 23.2 / 3600) * 15)


def test_ra_colon_separated_and_decimal():
    assert parse_ra("12:00:00")[0] == pytest.approx(180.0)
    assert parse_ra("180.5")[0] == pytest.approx(180.5)


@pytest.mark.parametrize("text", ["24 00 00", "-01 00 00", "12 60 00", "12 00 60", "360", "-1.0"])
def test_ra_out_of_range(text):
    assert parse_ra(text) == (None, "out_of_range")


@pytest.mark.parametrize("text", ["abc", "12 ab 00", "1_0", "nan", "inf", "1e", "--"])
def test_ra_malformed(text):
    assert parse_ra(text) == (None, "malformed")


def test_dec_signed_and_negative_zero_degrees():
    assert parse_dec("-00 30 12")[0] == pytest.approx(-(30 / 60 + 12 / 3600))
    assert parse_dec("+86 15 25")[0] == pytest.approx(86 + 15 / 60 + 25 / 3600)
    assert parse_dec("-90 00 00")[0] == -90.0


@pytest.mark.parametrize("text", ["+90 00 01", "+95 00 00", "10 60 00", "91.0", "-90.5"])
def test_dec_out_of_range(text):
    assert parse_dec(text) == (None, "out_of_range")


def test_parse_number_is_strict():
    assert parse_number(" -0.25 ") == -0.25
    assert parse_number("1e3") == 1000.0
    for bad in ("nan", "inf", "1_000", "", "1,5", "abc"):
        assert parse_number(bad) is None
    assert not math.isnan(parse_number("0") or 0.0)
