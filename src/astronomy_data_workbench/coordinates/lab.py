"""Run the Coordinate Accuracy Laboratory suites and write a JSON audit report."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import astropy
import numpy

from .reference import (
    Residual,
    report_dict,
    run_apparent_suite,
    run_horizontal_suite,
    run_reference_suite,
    run_refraction_suite,
)

LAB_VERSION = "0.1.0"
SUITES = {
    "propagation_and_frames": run_reference_suite,
    "horizontal_mean_place": run_horizontal_suite,
    "apparent_place": run_apparent_suite,
    "refraction": run_refraction_suite,
}


def run_all() -> dict[str, object]:
    """Run every suite. Content is deterministic; only run_timestamp_utc varies."""
    suites: dict[str, object] = {}
    all_passed = True
    for name, fn in SUITES.items():
        results: list[Residual] = fn()
        rep = report_dict(results)
        suites[name] = rep
        all_passed = all_passed and bool(rep["all_passed"])
    return {
        "lab_version": LAB_VERSION,
        "all_passed": all_passed,
        "environment": {
            "python": platform.python_version(),
            "astropy": astropy.__version__,
            "numpy": numpy.__version__,
        },
        "run_timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "suites": suites,
    }


def content_checksum(report: dict[str, object]) -> str:
    """SHA-256 of the report excluding the run timestamp, for reproducibility checks."""
    stable = {k: v for k, v in report.items() if k != "run_timestamp_utc"}
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="adw coords-lab", description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("coords-lab-report.json"))
    args = ap.parse_args(argv)
    report = run_all()
    report["content_sha256"] = content_checksum(report)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    for name, rep in report["suites"].items():  # type: ignore[attr-defined]
        results = rep["results"]
        bad = [r for r in results if not r["passed"] and not r["informational"]]
        print(f"{name:26s} {len(results):2d} checks, {len(bad)} gated failures")
    print(f"all_passed={report['all_passed']}  report={args.out}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
