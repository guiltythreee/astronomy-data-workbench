"""Epoch correction: the first constraint. SYNTHETIC inputs only (UNVERIFIED)."""

import math

import pytest

from astronomy_data_workbench.coordinates.propagation import SpaceMotion, propagate_rigorous
from astronomy_data_workbench.matching.epoch import propagate_entry
from astronomy_data_workbench.matching.geometry import separation_mas, unit_vector
from astronomy_data_workbench.matching.models import CatalogueEntry, MatchConfig
from astronomy_data_workbench.matching.synthetic import place_at_epoch

CFG = MatchConfig()


def entry(ra=10.0, dec=20.0, epoch=2000.0, **kw):
    kw.setdefault("pos_err_mas", 100.0)
    return CatalogueEntry("T", "T1", ra, dec, epoch, **kw)


@pytest.mark.parametrize("ra,dec,pm_a,pm_d,plx,dt", [
    (10.0, 20.0, 120.0, -45.0, 25.0, -8.75),
    (200.0, -60.0, -1500.0, 900.0, 80.0, 16.0),
    (300.0, 89.95, 500.0, 200.0, 10.0, -8.75),   # next to the pole
    (0.00001, 0.0, 30.0, 30.0, 5.0, 25.0),       # RA = 0 boundary
])  # fmt: skip
def test_agrees_with_coordinate_lab_propagator(ra, dec, pm_a, pm_d, plx, dt):
    """Independent cross-check against the Coordinate Lab's numpy propagator (no Astropy needed)."""
    e = entry(ra, dec, pm_ra_cosdec_mas_yr=pm_a, pm_dec_mas_yr=pm_d, parallax_mas=plx)
    mine = propagate_entry(e, 2000.0 + dt, CFG)
    lab = propagate_rigorous(SpaceMotion(ra, dec, plx, pm_a, pm_d, 0.0), dt)
    sep = separation_mas(unit_vector(mine.ra_deg, mine.dec_deg), unit_vector(*lab))
    assert sep < 1e-4  # mas


def test_radial_velocity_term_matches_lab():
    e = entry(100.0, -30.0, pm_ra_cosdec_mas_yr=-800.0, pm_dec_mas_yr=10300.0,
              parallax_mas=547.0, radial_velocity_km_s=-110.0)  # fmt: skip
    mine = propagate_entry(e, 2030.0, CFG)
    lab = propagate_rigorous(SpaceMotion(100.0, -30.0, 547.0, -800.0, 10300.0, -110.0), 30.0)
    assert mine.radial_term_used
    assert separation_mas(unit_vector(mine.ra_deg, mine.dec_deg), unit_vector(*lab)) < 1e-4


def test_zero_gap_changes_nothing():
    p = propagate_entry(entry(pm_ra_cosdec_mas_yr=500.0, pm_dec_mas_yr=500.0), 2000.0, CFG)
    assert (p.ra_deg, p.dec_deg) == pytest.approx((10.0, 20.0), abs=1e-12)
    assert p.sigma_mas == pytest.approx(100.0) and not p.uncorrected


def test_uncertainty_grows_with_epoch_gap():
    e = entry(pm_ra_cosdec_mas_yr=10.0, pm_dec_mas_yr=10.0, pm_err_mas_yr=20.0)
    p = propagate_entry(e, 2010.0, CFG)
    assert p.sigma_mas == pytest.approx(math.hypot(100.0, 20.0 * 10.0))
    assert propagate_entry(e, 1990.0, CFG).sigma_mas == pytest.approx(p.sigma_mas)  # |dt|


def test_moves_in_the_right_direction():
    east = propagate_entry(entry(0.0, 0.0, pm_ra_cosdec_mas_yr=1000.0, pm_dec_mas_yr=0.0),
                           2010.0, CFG)  # fmt: skip
    assert east.ra_deg == pytest.approx(10.0 / 3600.0, rel=1e-6) and east.dec_deg == pytest.approx(0.0, abs=1e-9)
    north = propagate_entry(entry(0.0, 0.0, pm_ra_cosdec_mas_yr=0.0, pm_dec_mas_yr=1000.0),
                            2010.0, CFG)  # fmt: skip
    assert north.dec_deg == pytest.approx(10.0 / 3600.0, rel=1e-6)


def test_no_proper_motion_is_not_moved_inflated_and_flagged():
    p = propagate_entry(entry(), 1991.25, CFG)
    assert (p.ra_deg, p.dec_deg) == (10.0, 20.0)
    assert not p.pm_applied and p.uncorrected
    assert p.sigma_mas == pytest.approx(math.hypot(100.0, CFG.missing_pm_sigma_mas_yr * 8.75))
    assert any("no proper motion" in a for a in p.assumptions)


def test_no_proper_motion_over_a_short_gap_is_not_blocking():
    p = propagate_entry(entry(), 2000.5, CFG)
    assert not p.uncorrected  # inside max_uncorrected_dt_years


def test_missing_pm_error_uses_recorded_fallback():
    p = propagate_entry(entry(pm_ra_cosdec_mas_yr=5.0, pm_dec_mas_yr=5.0), 2010.0, CFG)
    assert any(f"{CFG.fallback_pm_err_mas_yr:g} mas/yr" in a for a in p.assumptions)


def test_place_at_epoch_inverts_the_propagation():
    ra, dec = place_at_epoch(45.0, -30.0, 2000.0, 1200.0, -800.0, 1991.25)
    p = propagate_entry(entry(ra, dec, pm_ra_cosdec_mas_yr=1200.0, pm_dec_mas_yr=-800.0), 1991.25, CFG)
    assert separation_mas(unit_vector(p.ra_deg, p.dec_deg), unit_vector(45.0, -30.0)) < 1e-3


@pytest.mark.parametrize("kw", [
    {"ra": 360.0}, {"ra": -1.0}, {"dec": 91.0}, {"pos_err_mas": 0.0},
    {"pos_err_mas": float("nan")}, {"epoch": float("inf")},
    {"pm_ra_cosdec_mas_yr": 1.0},  # only one component
    {"pm_ra_cosdec_mas_yr": 1.0, "pm_dec_mas_yr": float("nan")},
    {"pm_err_mas_yr": -1.0}, {"parallax_err_mas": 0.0},
])  # fmt: skip
def test_invalid_entries_are_refused_not_repaired(kw):
    from astronomy_data_workbench.errors import SchemaError

    args = {"ra": 10.0, "dec": 20.0, "epoch": 2000.0, "pos_err_mas": 100.0}
    args.update(kw)
    with pytest.raises(SchemaError):
        CatalogueEntry("T", "X", args.pop("ra"), args.pop("dec"), args.pop("epoch"),
                       args.pop("pos_err_mas"), **args)  # fmt: skip


def test_config_rejects_nonsense():
    for bad in ({"accept_confidence": 0.0}, {"accept_confidence": 1.5}, {"accept_sigma": -1},
                {"reject_sigma": 1.0}, {"gate_floor_arcsec": 100.0}, {"null_weight": 0.0}):  # fmt: skip
        with pytest.raises(ValueError):
            MatchConfig(**bad)
