"""Catalogue loading, the BSC validator hand-off, and the output bundle (SYNTHETIC, UNVERIFIED)."""

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from astronomy_data_workbench.cli import main as adw_main
from astronomy_data_workbench.errors import SchemaError, SourceError
from astronomy_data_workbench.matching.engine import match_catalogues
from astronomy_data_workbench.matching.epoch import propagate_entry
from astronomy_data_workbench.matching.io import (
    AUDIT_NAME,
    OUTPUT_FILES,
    catalogue_from_dict,
    catalogue_to_dict,
    load_bsc_accepted_jsonl,
    load_catalogue_json,
    verify_bundle,
    write_bundle,
)
from astronomy_data_workbench.matching.models import (
    ACCEPTED,
    EPOCH_UNCORRECTED,
    REVIEW,
    Catalogue,
    CatalogueEntry,
    MatchConfig,
)
from astronomy_data_workbench.matching.synthetic import demo_catalogues

ROOT = Path(__file__).resolve().parents[2]
BSC_FIXTURE = ROOT / "tests" / "fixtures" / "bsc_synthetic.tsv"


def minimal(**over):
    data = {"format": "adw-catalogue/1", "catalogue": "C", "epoch": 2000.0, "frame": "ICRS",
            "position_error_mas": 50.0,
            "entries": [{"id": "a", "ra_deg": 10.0, "dec_deg": 5.0}]}  # fmt: skip
    data.update(over)
    return data


def test_minimal_catalogue_uses_file_level_defaults():
    cat = catalogue_from_dict(minimal(), {})
    e = cat.entries[0]
    assert (e.epoch, e.pos_err_mas, e.frame) == (2000.0, 50.0, "ICRS")
    assert e.pm_ra_cosdec_mas_yr is None and not e.has_proper_motion


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d.pop("epoch"), "no epoch"),
    (lambda d: d.pop("position_error_mas"), "no positional uncertainty"),
    (lambda d: d.pop("frame"), "no frame"),
    (lambda d: d.update(format="other/1"), "format must be"),
    (lambda d: d.update(surprise=1), "unknown catalogue keys"),
    (lambda d: d["entries"][0].update(raa_deg=1.0), "unknown keys"),
    (lambda d: d["entries"][0].update(mag=True), "expected a number"),
    (lambda d: d["entries"][0].update(mag="5.0"), "expected a number"),
    (lambda d: d["entries"][0].update(ra_deg=400.0), r"outside \[0, 360\)"),
    (lambda d: d["entries"].append(dict(d["entries"][0])), "duplicate entry id"),
    (lambda d: d["entries"][0].update(identifiers={"HR": 5}), "identifiers"),
    (lambda d: d.update(entries="nope"), "'entries' must be a list"),
])  # fmt: skip
def test_bad_catalogues_are_refused_with_a_reason(mutate, fragment):
    data = minimal()
    mutate(data)
    with pytest.raises(SchemaError, match=fragment):
        catalogue_from_dict(data, {})


def test_catalogue_round_trips_through_json(tmp_path):
    primary, reference, _ = demo_catalogues()
    for cat in (primary, reference):
        path = tmp_path / f"{cat.name}.json"
        path.write_text(json.dumps(catalogue_to_dict(cat)), encoding="utf-8")
        again = load_catalogue_json(path)
        assert again.entries == cat.entries and again.synthetic
        assert len(again.provenance["sha256"]) == 64
        assert again.provenance["origin"] == "file"


def test_unreadable_or_non_json_inputs_raise_source_errors(tmp_path):
    with pytest.raises(SourceError):
        load_catalogue_json(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SourceError):
        load_catalogue_json(bad)


# ---- BSC validator hand-off --------------------------------------------------------------------


@pytest.fixture
def bsc_bundle(tmp_path):
    out = tmp_path / "bsc"
    assert adw_main(["export", "bsc-tsv", str(BSC_FIXTURE), "--out", str(out)]) == 0
    return out


def test_bsc_loader_reads_only_validator_accepted_rows(bsc_bundle):
    cat = load_bsc_accepted_jsonl(bsc_bundle / "accepted.jsonl", position_error_mas=500.0)
    assert cat.name == "BSC" and len(cat.entries) == 5 and not cat.synthetic
    e = cat.entries[0]
    assert e.entry_id == "HR 1" and e.epoch == 2000.0 and e.frame == "FK5"
    assert e.passband == "Johnson V" and e.identifiers["HR"] == "1" and e.pos_err_mas == 500.0
    assert "500 mas was assumed" in cat.provenance["assumption"]
    assert cat.provenance["sha256"]
    with pytest.raises(SchemaError, match="only accepted rows"):
        load_bsc_accepted_jsonl(bsc_bundle / "review.jsonl", position_error_mas=500.0)


def test_bsc_to_matching_end_to_end_on_the_synthetic_fixture(bsc_bundle):
    """validator export -> BSC loader -> matching, against a reference built from the same stars."""
    bsc = load_bsc_accepted_jsonl(bsc_bundle / "accepted.jsonl", position_error_mas=500.0,
                                  pm_error_mas_yr=10.0)  # fmt: skip
    cfg = MatchConfig()
    refs = []
    for e in bsc.entries:
        moved = propagate_entry(e, 1991.25, cfg)
        refs.append(CatalogueEntry(
            "REF", e.entry_id.replace("HR", "REF"), moved.ra_deg, moved.dec_deg, 1991.25, 5.0,
            pm_ra_cosdec_mas_yr=e.pm_ra_cosdec_mas_yr, pm_dec_mas_yr=e.pm_dec_mas_yr,
            pm_err_mas_yr=1.0, parallax_mas=e.parallax_mas, parallax_err_mas=1.0, mag=e.mag,
            passband="Hipparcos Hp", frame="ICRS", synthetic=True))  # fmt: skip
    run = match_catalogues(bsc, Catalogue("REF", tuple(refs), synthetic=True), cfg)
    assert len(run.results) == 5
    for r in run.results:
        assert r.candidates[0].entry.entry_id == r.query.entry_id.replace("HR", "REF")
        if r.query.has_proper_motion:
            assert r.decision == ACCEPTED
        else:
            assert r.decision == REVIEW and EPOCH_UNCORRECTED in r.reasons
    assert run.primary.provenance["sha256"]  # input provenance flows into the run


# ---- bundle ------------------------------------------------------------------------------------


def demo_run():
    primary, reference, _ = demo_catalogues()
    return match_catalogues(primary, reference)


def test_bundle_has_every_file_and_verifies(tmp_path):
    audit = write_bundle(tmp_path / "o", demo_run())
    assert {p.name for p in (tmp_path / "o").iterdir()} == {*OUTPUT_FILES, AUDIT_NAME}
    assert set(audit["outputs"]) == set(OUTPUT_FILES)
    again, problems = verify_bundle(tmp_path / "o")
    assert problems == [] and again["content_checksum"] == audit["content_checksum"]


def test_bundle_is_deterministic_apart_from_the_audit_timestamp(tmp_path):
    a = write_bundle(tmp_path / "a", demo_run())
    b = write_bundle(tmp_path / "b", demo_run())
    assert a["content_checksum"] == b["content_checksum"]
    for name in OUTPUT_FILES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_tampering_is_detected(tmp_path):
    write_bundle(tmp_path / "o", demo_run())
    target = tmp_path / "o" / "accepted.jsonl"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    _, problems = verify_bundle(tmp_path / "o")
    assert any("accepted.jsonl: checksum mismatch" in p for p in problems)
    (tmp_path / "o" / "review.jsonl").unlink()
    assert any("review.jsonl: missing" in p for p in verify_bundle(tmp_path / "o")[1])


def test_a_bundle_that_drops_the_unverified_status_fails_verification(tmp_path):
    write_bundle(tmp_path / "o", demo_run())
    path = tmp_path / "o" / AUDIT_NAME
    audit = json.loads(path.read_text(encoding="utf-8"))
    audit["validation_status"] = "VERIFIED"
    path.write_text(json.dumps(audit), encoding="utf-8")
    assert any("validation_status" in p for p in verify_bundle(tmp_path / "o")[1])


def test_non_empty_output_directory_needs_force(tmp_path):
    (tmp_path / "o").mkdir()
    (tmp_path / "o" / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(SourceError, match="not empty"):
        write_bundle(tmp_path / "o", demo_run())
    write_bundle(tmp_path / "o", demo_run(), force=True)
    assert (tmp_path / "o" / "keep.txt").exists()  # never deletes what it did not write


def test_verify_rejects_a_directory_that_is_not_a_bundle(tmp_path):
    with pytest.raises(SourceError):
        verify_bundle(tmp_path)


def test_unverified_is_stamped_on_every_artefact(tmp_path):
    audit = write_bundle(tmp_path / "o", demo_run())
    out = tmp_path / "o"
    assert audit["validation_status"] == "UNVERIFIED" and "BSC export" in audit["validation_gate"]
    assert audit["validation_banner"].startswith("VALIDATION STATUS: UNVERIFIED")
    report = (out / "report.md").read_text(encoding="utf-8")
    assert report.splitlines()[2].startswith("> **VALIDATION STATUS: UNVERIFIED")
    assert "## Validation gate" in report and "## Assumptions used" in report
    for name in ("accepted", "review", "rejected", "unmatched"):
        rows = [json.loads(line) for line in (out / f"{name}.jsonl").read_text("utf-8").splitlines()]
        assert rows and all(r["validation_status"] == "UNVERIFIED" for r in rows), name


def test_audit_records_inputs_config_and_provenance(tmp_path):
    audit = write_bundle(tmp_path / "o", demo_run())
    assert audit["inputs"]["primary"]["origin"] == "synthetic scenario generator"
    assert audit["inputs"]["primary"]["synthetic"] is True
    assert audit["config"]["accept_sigma"] == 3.0 and audit["resolved_reference_epoch"] == 1991.25
    assert audit["totals"]["total"] == 16 and audit["algorithm"] == "epoch-positional/1"


def test_inputs_are_not_mutated():
    primary, reference, _ = demo_catalogues()
    before = (primary.entries, reference.entries)
    match_catalogues(primary, reference)
    assert (primary.entries, reference.entries) == before
    with pytest.raises(FrozenInstanceError):
        replace(primary.entries[0]).__setattr__("ra_deg", 1.0)
