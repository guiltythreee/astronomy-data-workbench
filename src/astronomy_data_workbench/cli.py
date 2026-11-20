"""Command-line interface for catalogue validation and the ADW specialist tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from astronomy_data_workbench import __version__
from astronomy_data_workbench.errors import SchemaError, SourceError
from astronomy_data_workbench.export import verify_bundle, write_bundle
from astronomy_data_workbench.inspection import inspect_file
from astronomy_data_workbench.modules import MODULES
from astronomy_data_workbench.provenance import build_manifest, sha256_file
from astronomy_data_workbench.schemas import bsc as schema
from astronomy_data_workbench.sources.bsc import read_raw_table
from astronomy_data_workbench.validation.hip2 import validate_hip2_table
from astronomy_data_workbench.validation import (
    ACCEPTED,
    ValidationConfig,
    ValidationResult,
    validate_table,
)


def _config(args: argparse.Namespace) -> ValidationConfig:
    markers = ("", *(args.null_marker or []))
    return ValidationConfig(null_markers=markers)


def _run_validation(path: Path, cfg: ValidationConfig) -> ValidationResult:
    return validate_table(read_raw_table(path), cfg)


def _print_summary(result: ValidationResult) -> None:
    c = result.counts()
    print(f"rows: {c['total_rows']}  accepted: {c['accepted']}  "
          f"review: {c['review']}  rejected: {c['rejected']}")  # fmt: skip
    for i in result.file_issues:
        print(f"file {i.severity}: {i.code}: {i.message}")
    codes = result.issue_code_counts()
    if codes:
        print("issue codes: " + ", ".join(f"{k}={v}" for k, v in codes.items()))


def cmd_inspect(args: argparse.Namespace) -> int:
    info = inspect_file(args.file)
    if args.json:
        print(json.dumps(info, indent=2, sort_keys=True))
        return 0
    for key, value in info.items():
        print(f"{key}: {value}")
    return 0


def cmd_validate_hip2(args: argparse.Namespace) -> int:
    table = read_raw_table(args.file)
    result = validate_hip2_table(table)
    counts = result.counts()
    print(f"rows: {counts['total_rows']}  accepted: {counts['accepted']}  "
          f"review: {counts['review']}  rejected: {counts['rejected']}")
    print(f"catalogue: {result.metadata['catalogue']}")
    print(f"position frame: {result.metadata['frame']}  epoch: J{result.metadata['epoch_jyear']}")
    for issue in result.file_issues:
        print(f"file {issue.severity}: {issue.code}: {issue.message}")
    if result.issue_code_counts():
        print("issue codes: " + ", ".join(
            f"{key}={value}" for key, value in result.issue_code_counts().items()))
    for row in result.rows:
        if row.outcome != ACCEPTED:
            hip = row.normalized.get("HIP") if row.normalized else None
            reasons = "; ".join(issue.code for issue in row.issues)
            print(f"line {row.line_number} (HIP {hip}): {row.outcome}: {reasons}")
    if args.jsonl is not None:
        args.jsonl.write_text("\n".join(
            json.dumps(row.to_dict(), sort_keys=True) for row in result.rows) + "\n",
            encoding="utf-8")
        print(f"row results written to {args.jsonl}")
    return 1 if args.strict and counts["accepted"] != counts["total_rows"] else 0


def cmd_validate(args: argparse.Namespace) -> int:
    result = _run_validation(args.file, _config(args))
    _print_summary(result)
    for row in result.rows:
        if row.outcome != ACCEPTED:
            hr = row.record.hr if row.record else None
            why = "; ".join(f"{i.code}" + (f"[{i.field}]" if i.field else "") for i in row.issues)
            print(f"line {row.line_number} (HR {hr}): {row.outcome}: {why}")
    if args.strict and result.counts()["accepted"] != result.counts()["total_rows"]:
        return 1
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    cfg = _config(args)
    info = inspect_file(args.file)
    manifest = build_manifest(
        args.file,
        schema.SOURCE_NAME,
        catalogue_release=args.release,
        source_url=args.source_url,
        licence_status=args.licence_status,
    )
    result = _run_validation(args.file, cfg)
    audit = write_bundle(args.out, manifest, result, cfg, info, force=args.force)
    _print_summary(result)
    print(f"bundle written to {args.out}  (content checksum {audit['content_checksum'][:16]}...)")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    audit, problems = verify_bundle(args.bundle)
    src = audit["source"]
    print(f"source: {src['source_name']} ({src['file_name']})")
    print(f"input sha256: {audit['input_sha256']}")
    print(f"release: {src['catalogue_release']}; licence status: {src['licence_status']}")
    print(f"versions: adw {audit['adw_version']}, parser {audit['parser_version']}, "
          f"schema {audit['schema_version']}, config {audit['config_version']}")  # fmt: skip
    print(f"ingested: {audit['ingestion_timestamp']}")
    print(f"totals: {audit['totals']}")
    print(f"issue codes: {audit['issue_code_counts']}")
    if args.source is not None:
        actual = sha256_file(args.source)
        if actual != audit["input_sha256"]:
            problems.append("source file checksum does not match the recorded input sha256")
        else:
            print("source file checksum: OK")
    if problems:
        print("VERIFICATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("output checksums: OK")
    return 0


def cmd_modules(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps([m.to_dict() for m in MODULES], indent=2))
        return 0
    for m in MODULES:
        print(f"{m.number} {m.name}  [{m.status}, priority {m.priority}]")
        print(f"   {m.description}")
        for item in m.responsibilities:
            print(f"   - {item}")
        print(f"   command: {m.command or '(none yet)'}")
        print(f"   note: {m.status_note}")
        print()
    return 0


def cmd_coords_lab(args: argparse.Namespace) -> int:
    # Imported lazily so catalogue commands remain usable without optional astronomy deps.
    try:
        from astronomy_data_workbench.coordinates.lab import main as lab_main
    except ModuleNotFoundError as exc:
        if exc.name in {"astropy", "numpy"}:
            print(
                f"error: the coordinate lab needs NumPy and Astropy ({exc.name} missing)",
                file=sys.stderr,
            )
            return 2
        raise
    return lab_main(["--out", str(args.out)])


def cmd_explorer(args: argparse.Namespace) -> int:
    from astronomy_data_workbench.identity.build_explorer import build

    build(args.records, args.out)
    label = "bundled SYNTHETIC data" if args.records is None else str(args.records)
    print(f"wrote {args.out} from {label}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="adw", description="Astronomy Data Workbench")
    parser.add_argument("--version", action="version", version=f"adw {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="describe a file without changing it")
    p.add_argument("file", type=Path)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_inspect)

    def add_validation_options(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("file", type=Path)
        sp.add_argument("--null-marker", action="append", metavar="TEXT",
                        help="extra text to treat as null (empty cells always are); repeatable")  # fmt: skip

    p = sub.add_parser("validate", help="validate a file and print results")
    vsub = p.add_subparsers(dest="kind", required=True)
    pb = vsub.add_parser("bsc-tsv", help="BSC (V/50) VizieR TSV export")
    add_validation_options(pb)
    pb.add_argument("--strict", action="store_true", help="exit 1 unless every row is accepted")
    pb.set_defaults(func=cmd_validate)
    ph = vsub.add_parser("hip2-tsv", help="Hipparcos-2 (I/311/hip2) VizieR TSV export")
    ph.add_argument("file", type=Path)
    ph.add_argument("--strict", action="store_true", help="exit 1 unless every row is accepted")
    ph.add_argument("--jsonl", type=Path, default=None, help="write normalized row results as JSONL")
    ph.set_defaults(func=cmd_validate_hip2)

    p = sub.add_parser("export", help="validate and write an audit bundle")
    esub = p.add_subparsers(dest="kind", required=True)
    pb = esub.add_parser("bsc-tsv", help="BSC (V/50) VizieR TSV export")
    add_validation_options(pb)
    pb.add_argument("--out", type=Path, required=True, help="output directory")
    pb.add_argument("--force", action="store_true", help="allow a non-empty output directory")
    pb.add_argument("--release", default="unknown", help="catalogue release, if known")
    pb.add_argument("--source-url", default=None, help="official source URL, if known")
    pb.add_argument("--licence-status", default="unverified")
    pb.set_defaults(func=cmd_export)

    p = sub.add_parser("modules", help="list the ADW modules, descriptions and status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_modules)

    p = sub.add_parser("audit", help="show and verify an audit bundle")
    p.add_argument("bundle", type=Path)
    p.add_argument("--source", type=Path, default=None, help="also re-hash the original source file")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("coords-lab", help="run coordinate reference suites and write a JSON report")
    p.add_argument("--out", type=Path, default=Path("coords-lab-report.json"))
    p.set_defaults(func=cmd_coords_lab)

    p = sub.add_parser("explorer", help="build the local star identity explorer page")
    p.add_argument("records", type=Path, nargs="?", default=None,
                   help="records JSON (default: bundled synthetic test data)")
    p.add_argument("--out", type=Path, default=Path("identity-explorer.html"))
    p.set_defaults(func=cmd_explorer)

    from astronomy_data_workbench.matching.cli import register as register_crossmatch

    register_crossmatch(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (SourceError, SchemaError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
