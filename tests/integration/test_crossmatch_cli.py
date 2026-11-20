"""`adw crossmatch` end to end (SYNTHETIC, UNVERIFIED)."""

import json
from pathlib import Path

import pytest

from astronomy_data_workbench.cli import main
from astronomy_data_workbench.matching.cli import main as standalone_main

ROOT = Path(__file__).resolve().parents[2]
BANNER = "VALIDATION STATUS: UNVERIFIED"


def test_demo_prints_the_banner_first_and_meets_its_synthetic_expectations(tmp_path, capsys):
    assert main(["crossmatch", "demo", "--out", str(tmp_path / "d")]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith(BANNER)
    out = "\n".join(lines)
    assert "synthetic expectations met: 16/16" in out
    assert "10 object(s) need MANUAL REVIEW" in out
    assert "validation status: UNVERIFIED" in out
    assert (tmp_path / "d" / "inputs" / "syn-primary.json").is_file()


def test_run_on_files_then_verify(tmp_path, capsys):
    main(["crossmatch", "demo", "--out", str(tmp_path / "d")])
    capsys.readouterr()
    inputs = tmp_path / "d" / "inputs"
    code = main(["crossmatch", "run", str(inputs / "syn-primary.json"),
                 str(inputs / "syn-reference.json"), "--out", str(tmp_path / "r")])  # fmt: skip
    out = capsys.readouterr().out
    assert code == 0 and out.startswith(BANNER) and "accepted: 4  review: 10" in out
    assert main(["crossmatch", "verify", str(tmp_path / "r")]) == 0
    verified = capsys.readouterr().out
    assert verified.startswith(BANNER) and "output checksums: OK" in verified
    for name in ("accepted", "review", "rejected", "unmatched"):
        assert (tmp_path / "d" / f"{name}.jsonl").read_bytes() == (tmp_path / "r" / f"{name}.jsonl").read_bytes()


def test_run_options_are_recorded_and_validated(tmp_path, capsys):
    main(["crossmatch", "demo", "--out", str(tmp_path / "d")])
    inputs = tmp_path / "d" / "inputs"
    args = ["crossmatch", "run", str(inputs / "syn-primary.json"), str(inputs / "syn-reference.json")]
    assert main([*args, "--out", str(tmp_path / "e"), "--reference-epoch", "2000",
                 "--accept-confidence", "0.99"]) == 0  # fmt: skip
    audit = json.loads((tmp_path / "e" / "crossmatch-audit.json").read_text(encoding="utf-8"))
    assert audit["config"]["reference_epoch"] == 2000.0 and audit["config"]["accept_confidence"] == 0.99
    capsys.readouterr()
    assert main([*args, "--out", str(tmp_path / "f"), "--accept-confidence", "7"]) == 2
    assert "invalid matching option" in capsys.readouterr().err


def test_errors_exit_2_with_a_message(tmp_path, capsys):
    good = tmp_path / "g.json"
    good.write_text(json.dumps({"format": "adw-catalogue/1", "catalogue": "C", "epoch": 2000.0,
                                "frame": "ICRS", "position_error_mas": 10.0,
                                "entries": [{"id": "a", "ra_deg": 1.0, "dec_deg": 1.0}]}))  # fmt: skip
    no_epoch = tmp_path / "n.json"
    no_epoch.write_text(json.dumps({"format": "adw-catalogue/1", "catalogue": "D", "frame": "ICRS",
                                    "position_error_mas": 10.0,
                                    "entries": [{"id": "b", "ra_deg": 1.0, "dec_deg": 1.0}]}))  # fmt: skip
    assert main(["crossmatch", "run", str(no_epoch), str(good), "--out", str(tmp_path / "o")]) == 2
    assert "no epoch" in capsys.readouterr().err
    assert main(["crossmatch", "run", str(tmp_path / "nope.json"), str(good),
                 "--out", str(tmp_path / "o")]) == 2  # fmt: skip
    bsc = tmp_path / "accepted.jsonl"
    bsc.write_text("")
    assert main(["crossmatch", "run", str(bsc), str(good), "--out", str(tmp_path / "o")]) == 2
    assert "--bsc-position-error-mas" in capsys.readouterr().err


def test_bsc_validator_output_can_be_matched_from_the_cli(tmp_path, capsys):
    bsc_out = tmp_path / "bsc"
    assert main(["export", "bsc-tsv", str(ROOT / "tests/fixtures/bsc_synthetic.tsv"),
                 "--out", str(bsc_out)]) == 0  # fmt: skip
    main(["crossmatch", "demo", "--out", str(tmp_path / "d")])
    capsys.readouterr()
    code = main(["crossmatch", "run", str(bsc_out / "accepted.jsonl"),
                 str(tmp_path / "d" / "inputs" / "syn-reference.json"), "--out", str(tmp_path / "m"),
                 "--bsc-position-error-mas", "500"])  # fmt: skip
    assert code == 0
    audit = json.loads((tmp_path / "m" / "crossmatch-audit.json").read_text(encoding="utf-8"))
    assert audit["inputs"]["primary"]["origin"] == "bsc-validator-accepted"
    assert "500 mas was assumed" in audit["inputs"]["primary"]["assumption"]
    assert audit["validation_status"] == "UNVERIFIED"


def test_verify_fails_on_a_tampered_bundle(tmp_path, capsys):
    main(["crossmatch", "demo", "--out", str(tmp_path / "d")])
    (tmp_path / "d" / "report.md").write_text("changed", encoding="utf-8")
    capsys.readouterr()
    assert main(["crossmatch", "verify", str(tmp_path / "d")]) == 1
    assert "VERIFICATION FAILED" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["crossmatch", "--help"], ["crossmatch", "run", "--help"],
                                  ["crossmatch", "demo", "--help"], ["crossmatch", "verify", "--help"]])  # fmt: skip
def test_help_screens_carry_the_unverified_status(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 0
    assert "UNVERIFIED" in capsys.readouterr().out


def test_modules_command_shows_module_03_as_unverified(capsys):
    assert main(["modules"]) == 0
    out = capsys.readouterr().out
    block = out.split("03 Astronomical Cross-Matching Workbench")[1].split("04 Coordinate")[0]
    assert "[partial, priority 2]" in block and "UNVERIFIED" in block
    assert "adw crossmatch run | demo | verify" in block
    assert main(["modules", "--json"]) == 0
    mod = json.loads(capsys.readouterr().out)[2]
    assert mod["status"] == "partial" and "UNVERIFIED" in mod["status_note"]


def test_standalone_entry_point_used_by_the_single_file_tool(tmp_path, capsys):
    assert standalone_main(["demo", "--out", str(tmp_path / "s")]) == 0
    assert capsys.readouterr().out.startswith(BANNER)
    assert standalone_main(["verify", str(tmp_path / "missing")]) == 2
