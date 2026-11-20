import json
from pathlib import Path

from astronomy_data_workbench.cli import main
from astronomy_data_workbench.provenance import sha256_file
from conftest import FIXTURE


def export(out: Path, *extra: str) -> int:
    return main(["export", "bsc-tsv", str(FIXTURE), "--out", str(out), *extra])


def test_fixture_is_classified_as_designed(capsys):
    assert main(["validate", "bsc-tsv", str(FIXTURE)]) == 0
    out = capsys.readouterr().out
    assert "accepted: 5  review: 2  rejected: 5" in out
    assert "line 14 (HR 8): rejected: RA_OUT_OF_RANGE" in out


def test_strict_exit_code():
    assert main(["validate", "bsc-tsv", str(FIXTURE), "--strict"]) == 1


def test_source_file_is_never_modified(tmp_path):
    before = sha256_file(FIXTURE)
    export(tmp_path / "b")
    main(["inspect", str(FIXTURE)])
    assert sha256_file(FIXTURE) == before


def test_bundle_contents_and_audit_fields(tmp_path):
    out = tmp_path / "b"
    assert export(out, "--release", "test-1") == 0
    names = {p.name for p in out.iterdir()}
    assert names == {"accepted.jsonl", "review.jsonl", "rejected.jsonl", "issues.csv",
                     "report.md", "audit.json"}  # fmt: skip
    audit = json.loads((out / "audit.json").read_text())
    assert audit["input_sha256"] == sha256_file(FIXTURE)
    assert audit["totals"] == {"total_rows": 12, "accepted": 5, "rejected": 5, "review": 2}
    for key in ("parser_version", "schema_version", "config_version", "config",
                "ingestion_timestamp", "issue_code_counts", "outputs", "content_checksum"):  # fmt: skip
        assert key in audit
    assert audit["source"]["catalogue_release"] == "test-1"
    assert audit["source"]["licence_status"] == "unverified"
    rejected = [json.loads(x) for x in (out / "rejected.jsonl").read_text().splitlines()]
    assert all(r["issues"] for r in rejected) and len(rejected) == 5


def test_reproducible_outputs(tmp_path):
    export(tmp_path / "a")
    export(tmp_path / "b")
    a = json.loads((tmp_path / "a" / "audit.json").read_text())
    b = json.loads((tmp_path / "b" / "audit.json").read_text())
    assert a["content_checksum"] == b["content_checksum"]
    for name in a["outputs"]:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_audit_verifies_and_detects_tampering(tmp_path, capsys):
    out = tmp_path / "b"
    export(out)
    assert main(["audit", str(out), "--source", str(FIXTURE)]) == 0
    (out / "accepted.jsonl").write_text("tampered\n")
    assert main(["audit", str(out)]) == 1
    assert "checksum mismatch" in capsys.readouterr().out


def test_export_refuses_non_empty_directory(tmp_path, capsys):
    out = tmp_path / "b"
    export(out)
    assert export(out) == 2
    assert "not empty" in capsys.readouterr().err
    assert export(out, "--force") == 0


def test_inspect_reports_facts(capsys):
    assert main(["inspect", str(FIXTURE), "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["delimiter"] == "tab" and info["data_row_count"] == 12
    assert info["probable_schema"] == "bsc-vizier-tsv/1"
    assert info["non_numeric_tokens_in_numeric_columns"] == {"abc": 1}


def test_bad_input_gives_clean_error(tmp_path, capsys):
    p = tmp_path / "x.csv"
    p.write_text("a,b,c\n1,2,3\n")
    assert main(["validate", "bsc-tsv", str(p)]) == 2
    assert "missing required columns" in capsys.readouterr().err


def test_hip2_validator_cli_writes_jsonl(tmp_path, capsys):
    from tests.unit.test_hip2_validation import HEADER, valid_row, make_file

    source = make_file(tmp_path, [valid_row()])
    output = tmp_path / "hip2.jsonl"
    assert main(["validate", "hip2-tsv", str(source), "--jsonl", str(output)]) == 0
    assert "accepted: 1" in capsys.readouterr().out
    import json
    record = json.loads(output.read_text(encoding="utf-8"))
    assert record["record"]["position"]["epoch_jyear"] == 1991.25
