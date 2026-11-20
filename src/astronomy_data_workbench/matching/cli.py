"""`adw crossmatch` commands (module 03). Status: UNVERIFIED, synthetic-tested only.

numpy is imported lazily so the rest of the `adw` CLI keeps working without it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from astronomy_data_workbench.errors import SchemaError, SourceError
from astronomy_data_workbench.matching.models import (
    ACCEPTED,
    REJECTED,
    REVIEW,
    UNMATCHED,
    UNVERIFIED_BANNER,
    VALIDATION_GATE,
    Catalogue,
    CrossMatchRun,
    MatchConfig,
)


def _banner() -> None:
    print(UNVERIFIED_BANNER)
    print()


def _load(path: Path, args: argparse.Namespace) -> Catalogue:
    from astronomy_data_workbench.matching.io import load_bsc_accepted_jsonl, load_catalogue_json

    if path.suffix.lower() == ".jsonl":
        if args.bsc_position_error_mas is None:
            raise SchemaError(
                f"{path.name} looks like BSC validator output; BSC publishes no position error, "
                "so give --bsc-position-error-mas (it is recorded as an assumption)"
            )
        return load_bsc_accepted_jsonl(path, position_error_mas=args.bsc_position_error_mas,
                                       pm_error_mas_yr=args.bsc_pm_error_mas_yr)  # fmt: skip
    return load_catalogue_json(path)


def _config(args: argparse.Namespace) -> MatchConfig:
    overrides: dict[str, Any] = {}
    for name in ("reference_epoch", "accept_sigma", "accept_confidence", "gate_floor_arcsec"):
        value = getattr(args, name)
        if value is not None:
            overrides[name] = value
    try:
        return MatchConfig(**overrides)
    except ValueError as exc:
        raise SchemaError(f"invalid matching option: {exc}") from exc


def _summary(run: CrossMatchRun, out_dir: Path) -> None:
    counts = run.counts()
    print(f"primary: {run.primary.name} ({len(run.primary.entries)})  "
          f"reference: {run.reference.name} ({len(run.reference.entries)})  "
          f"common epoch: {run.resolved_reference_epoch:g}")  # fmt: skip
    print(f"accepted: {counts[ACCEPTED]}  review: {counts[REVIEW]}  "
          f"rejected: {counts[REJECTED]}  unmatched: {counts[UNMATCHED]}")  # fmt: skip
    reasons = run.reason_counts()
    if reasons:
        print("reasons: " + ", ".join(f"{k}={v}" for k, v in reasons.items()))
    if counts[REVIEW]:
        print(f"{counts[REVIEW]} object(s) need MANUAL REVIEW: see {out_dir / 'review.jsonl'}")
    print(f"bundle written to {out_dir}")
    print("validation status: UNVERIFIED (see report.md for the validation gate)")


def cmd_run(args: argparse.Namespace) -> int:
    from astronomy_data_workbench.matching.engine import match_catalogues
    from astronomy_data_workbench.matching.io import write_bundle

    _banner()
    primary = _load(args.primary, args)
    reference = _load(args.reference, args)
    run = match_catalogues(primary, reference, _config(args))
    write_bundle(args.out, run, force=args.force)
    _summary(run, args.out)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from astronomy_data_workbench.matching.engine import match_catalogues
    from astronomy_data_workbench.matching.io import catalogue_to_dict, write_bundle
    from astronomy_data_workbench.matching.synthetic import demo_catalogues

    _banner()
    print("DEMO on SYNTHETIC scenarios (invented values, not real catalogue data).")
    primary, reference, expected = demo_catalogues()
    run = match_catalogues(primary, reference, MatchConfig())
    write_bundle(args.out, run, force=args.force)
    inputs = args.out / "inputs"
    inputs.mkdir(exist_ok=True)
    for cat in (primary, reference):
        (inputs / f"{cat.name.lower()}.json").write_text(
            json.dumps(catalogue_to_dict(cat), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    met = 0
    for r in run.results:
        ex = expected[r.query.entry_id]
        top = r.candidates[0].entry.entry_id if r.candidates else None
        ok = (r.decision == ex.decision and set(ex.reasons) <= set(r.reasons)
              and (ex.top is None or ex.top == top)
              and len(r.candidates) >= ex.min_candidates)  # fmt: skip
        met += ok
        print(f"  {'ok  ' if ok else 'FAIL'} {r.query.entry_id:<9} {r.decision:<9} "
              f"{', '.join(r.reasons) or '-'}")  # fmt: skip
    print(f"synthetic expectations met: {met}/{len(run.results)}")
    _summary(run, args.out)
    print(f"synthetic inputs written to {inputs} (try: adw crossmatch run ...)")
    return 0 if met == len(run.results) else 1


def cmd_verify(args: argparse.Namespace) -> int:
    from astronomy_data_workbench.matching.io import verify_bundle

    _banner()
    audit, problems = verify_bundle(args.bundle)
    print(f"validation status recorded in bundle: {audit.get('validation_status')}")
    print(f"decisions: {audit.get('totals')}")
    if problems:
        print("VERIFICATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("output checksums: OK")
    return 0


def _add_run_options(p: argparse.ArgumentParser) -> None:
    p.add_argument("primary", type=Path, help="query catalogue: adw-catalogue/1 .json or BSC "
                   "validator accepted .jsonl")  # fmt: skip
    p.add_argument("reference", type=Path, help="reference catalogue (same formats)")
    p.add_argument("--out", type=Path, required=True, help="output directory")
    p.add_argument("--force", action="store_true", help="allow a non-empty output directory")
    p.add_argument("--reference-epoch", type=float, default=None, metavar="YEAR",
                   help="common Julian-year epoch (default: median reference epoch)")  # fmt: skip
    p.add_argument("--accept-sigma", type=float, default=None)
    p.add_argument("--accept-confidence", type=float, default=None)
    p.add_argument("--gate-floor-arcsec", type=float, default=None)
    p.add_argument("--bsc-position-error-mas", type=float, default=None,
                   help="assumed BSC 1-sigma position error (required for .jsonl inputs)")  # fmt: skip
    p.add_argument("--bsc-pm-error-mas-yr", type=float, default=None)
    p.set_defaults(func=cmd_run)


def register(sub: Any) -> None:
    """Attach `crossmatch` to the main parser's subparsers."""
    p = sub.add_parser("crossmatch", help="cross-match catalogues (UNVERIFIED, synthetic-tested)",
                       description=UNVERIFIED_BANNER, epilog=VALIDATION_GATE)  # fmt: skip
    csub = p.add_subparsers(dest="crossmatch_command", required=True)
    pr = csub.add_parser("run", help="match a primary catalogue against a reference",
                         description=UNVERIFIED_BANNER)  # fmt: skip
    _add_run_options(pr)
    pd = csub.add_parser("demo", help="run the built-in SYNTHETIC scenarios",
                         description=UNVERIFIED_BANNER)  # fmt: skip
    pd.add_argument("--out", type=Path, required=True)
    pd.add_argument("--force", action="store_true")
    pd.set_defaults(func=cmd_demo)
    pv = csub.add_parser("verify", help="re-hash a cross-match bundle",
                         description=UNVERIFIED_BANNER)  # fmt: skip
    pv.add_argument("bundle", type=Path)
    pv.set_defaults(func=cmd_verify)


def main(argv: list[str] | None = None) -> int:
    """Stand-alone entry point (used by the single-file module 03 tool)."""
    parser = argparse.ArgumentParser(prog="adw-crossmatch", description=UNVERIFIED_BANNER)
    sub = parser.add_subparsers(dest="command", required=True)
    register(sub)
    args = parser.parse_args(["crossmatch", *(argv if argv is not None else sys.argv[1:])])
    try:
        return int(args.func(args))
    except (SourceError, SchemaError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
