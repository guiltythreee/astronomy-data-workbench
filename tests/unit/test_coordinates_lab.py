import math

import pytest

pytest.importorskip("astropy")

from astronomy_data_workbench.coordinates.conventions import (
    bsc_pm_arcsec_to_mas,
    pm_ra_to_mu_alpha_star,
)
from astronomy_data_workbench.coordinates.propagation import (
    SpaceMotion,
    propagate_linear,
    propagate_rigorous,
)
from astronomy_data_workbench.coordinates.reference import run_reference_suite


def test_bsc_pm_is_plain_times_1000_no_cos_dec():
    assert bsc_pm_arcsec_to_mas(0.5) == 500.0
    assert bsc_pm_arcsec_to_mas(-0.0123) == pytest.approx(-12.3)


def test_cos_dec_only_when_convention_says_so():
    assert pm_ra_to_mu_alpha_star(100.0, 60.0, already_cos_dec=True) == 100.0
    assert pm_ra_to_mu_alpha_star(100.0, 60.0, already_cos_dec=False) == pytest.approx(50.0)


def test_zero_motion_is_identity():
    s = SpaceMotion(10.0, 20.0, 5.0, 0.0, 0.0, 0.0)
    assert propagate_rigorous(s, 50.0) == pytest.approx((10.0, 20.0))


def test_rigorous_needs_parallax():
    with pytest.raises(ValueError):
        propagate_rigorous(SpaceMotion(1.0, 1.0, 0.0, 1.0, 1.0, 0.0), 1.0)


def test_ra_wraps_into_range():
    s = SpaceMotion(359.99999, 0.0, 100.0, 5000.0, 0.0, 0.0)
    ra, _ = propagate_rigorous(s, 100.0)
    assert 0.0 <= ra < 360.0
    ra2, _ = propagate_linear(s, 100.0)
    assert 0.0 <= ra2 < 360.0


def test_round_trip_back_and_forth():
    s = SpaceMotion(269.45, 4.69, 548.31, -798.58, 10328.12, -110.51)
    ra, dec = propagate_rigorous(s, 16.0)
    back = SpaceMotion(ra, dec, 548.31, -798.58, 10328.12, -110.51)
    ra0, dec0 = propagate_rigorous(back, -16.0)
    # Not exact (velocity is re-expressed at the new position); stay within 1 arcsec.
    assert abs(ra0 - 269.45) * math.cos(math.radians(4.69)) * 3600 < 1.0
    assert abs(dec0 - 4.69) * 3600 < 1.0


def test_reference_suite_passes_and_reports_tolerances():
    results = run_reference_suite()
    assert results
    gated = [r for r in results if not r.informational]
    assert all(r.passed for r in gated), [r for r in gated if not r.passed]
    linear = [r for r in results if r.informational]
    assert linear and not linear[0].passed  # linear propagation must visibly fail for high PM
    assert all(r.tolerance > 0 and r.unit for r in results)


def test_horizontal_suite_matches_published_and_astropy():
    from astronomy_data_workbench.coordinates.reference import run_horizontal_suite

    results = run_horizontal_suite()
    assert len(results) == 7
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_horizontal_edge_cases():
    from astronomy_data_workbench.coordinates.horizontal import equatorial_to_horizontal

    alt, _ = equatorial_to_horizontal(0.0, 30.0, 30.0)  # on meridian, dec == lat -> zenith
    assert alt == pytest.approx(90.0)
    alt, az = equatorial_to_horizontal(123.0, 89.999, 45.0)  # near pole: alt ~ latitude
    assert alt == pytest.approx(45.0, abs=0.01)
    assert 0.0 <= az < 360.0


def test_apparent_suite_is_tight_against_astropy():
    from astronomy_data_workbench.coordinates.reference import run_apparent_suite

    results = run_apparent_suite()
    assert len(results) == 8
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_apparent_place_stays_in_range_and_moves_a_little():
    from astronomy_data_workbench.coordinates.apparent import apparent_place
    from astronomy_data_workbench.coordinates.horizontal import precess_j2000_to_date

    jd = 2461360.0
    ra_m, dec_m = precess_j2000_to_date(10.0, 20.0, jd)
    ra_a, dec_a = apparent_place(10.0, 20.0, jd)
    assert 0.0 <= ra_a < 360.0 and -90.0 <= dec_a <= 90.0
    assert abs(ra_a - ra_m) * 3600 < 60 and abs(dec_a - dec_m) * 3600 < 60


def test_refraction_suite():
    from astronomy_data_workbench.coordinates.reference import run_refraction_suite

    results = run_refraction_suite()
    assert len(results) == 4
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_refraction_raises_altitude_and_shrinks_with_height():
    from astronomy_data_workbench.coordinates.refraction import (
        refraction_from_true_arcmin,
        true_to_apparent_alt,
    )

    vals = [refraction_from_true_arcmin(float(h)) for h in (5, 15, 30, 60, 85)]
    assert vals == sorted(vals, reverse=True) and all(v > 0 for v in vals)
    assert true_to_apparent_alt(30.0) > 30.0
    assert refraction_from_true_arcmin(30.0, pressure_mbar=505.0) == pytest.approx(
        refraction_from_true_arcmin(30.0) / 2, rel=1e-9
    )


def test_lab_cli_writes_report_and_is_reproducible(tmp_path):
    import json

    from astronomy_data_workbench.coordinates.lab import content_checksum, main, run_all

    out = tmp_path / "report.json"
    assert main(["--out", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["all_passed"] is True
    assert set(data["suites"]) == {
        "propagation_and_frames", "horizontal_mean_place", "apparent_place", "refraction",
    }
    assert data["content_sha256"] == content_checksum(run_all())
