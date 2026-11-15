"""Write the audit bundle: accepted/review/rejected outputs, issues, report, audit.json.

Output files contain no timestamps, so identical input + config + version gives identical
files and an identical content_checksum. Only audit.json carries the ingestion timestamp.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from astronomy_data_workbench import __version__
from astronomy_data_workbench.errors import SourceError
from astronomy_data_workbench.provenance import SourceManifest, sha256_bytes
from astronomy_data_workbench.schemas import bsc as schema
from astronomy_data_workbench.validation import (
    ACCEPTED,
    CONFIG_VERSION,
    REJECTED,
    REVIEW,
    ValidationConfig,
    ValidationResult,
)

PARSER_VERSION = f"bsc-tsv-parser/1 (adw {__version__})"
AUDIT_NAME = "audit.json"


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(_dump(r) + "\n" for r in rows).encode("utf-8")


def _issues_csv(result: ValidationResult) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["line_number", "hr", "outcome", "severity", "code", "field", "message"])
    for row in result.rows:
        hr = row.record.hr if row.record else ""
        for i in row.issues:
            writer.writerow([row.line_number, hr, row.outcome, i.severity, i.code, i.field or "", i.message])
    return buf.getvalue().encode("utf-8")


def _report_md(manifest: SourceManifest, result: ValidationResult, cfg: ValidationConfig) -> bytes:
    c = result.counts()
    lines = [
        "# ADW validation report",
        "",
        f"- Source: {manifest.source_name} (`{manifest.file_name}`)",
        f"- SHA-256: `{manifest.sha256}`",
        f"- Release: {manifest.catalogue_release}; licence status: {manifest.licence_status}",
        f"- Schema: {schema.SCHEMA_VERSION}; config version {CONFIG_VERSION}",
        "",
        "## Totals",
        "",
        "| Outcome | Rows |",
        "|---|---|",
        f"| Accepted | {c['accepted']} |",
        f"| Review | {c['review']} |",
        f"| Rejected | {c['rejected']} |",
        f"| Total | {c['total_rows']} |",
        "",
        "## Issue codes",
        "",
    ]
    counts = result.issue_code_counts()
    lines += [f"- `{k}`: {v}" for k, v in counts.items()] or ["- none"]
    if result.file_issues:
        lines += ["", "## File-level notes", ""]
        lines += [f"- `{i.code}` ({i.severity}): {i.message}" for i in result.file_issues]
    for title, outcome in (("Rejected rows", REJECTED), ("Rows needing review", REVIEW)):
        rows = [r for r in result.rows if r.outcome == outcome]
        if rows:
            lines += ["", f"## {title}", ""]
            for r in rows[:50]:
                why = "; ".join(f"{i.code}" + (f" ({i.field})" if i.field else "") for i in r.issues)
                lines.append(f"- line {r.line_number}: {why}")
            if len(rows) > 50:
                lines.append(f"- ... and {len(rows) - 50} more (see issues.csv)")
    lines += ["", "## Conventions", "",
              f"- Position frame {schema.FRAME}, equinox {schema.EQUINOX}, epoch {schema.EPOCH}",
              f"- Proper motion: {schema.PM_RA_CONVENTION}; arcsec/yr -> mas/yr by x1000 only",
              f"- Photometry passband: {schema.PASSBAND}", ""]  # fmt: skip
    return "\n".join(lines).encode("utf-8")


def _content_checksum(outputs: dict[str, str]) -> str:
    joined = "\n".join(f"{name}:{sha}" for name, sha in sorted(outputs.items()))
    return sha256_bytes(joined.encode("utf-8"))


def write_bundle(
    out_dir: Path,
    manifest: SourceManifest,
    result: ValidationResult,
    config: ValidationConfig,
    inspection: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise SourceError(f"output directory {out_dir} is not empty (use --force to overwrite)")
    out_dir.mkdir(parents=True, exist_ok=True)

    by_outcome = {o: [r.to_dict() for r in result.rows if r.outcome == o]
                  for o in (ACCEPTED, REVIEW, REJECTED)}  # fmt: skip
    files: dict[str, bytes] = {
        "accepted.jsonl": _jsonl(by_outcome[ACCEPTED]),
        "review.jsonl": _jsonl(by_outcome[REVIEW]),
        "rejected.jsonl": _jsonl(by_outcome[REJECTED]),
        "issues.csv": _issues_csv(result),
        "report.md": _report_md(manifest, result, config),
    }
    for name, data in files.items():
        (out_dir / name).write_bytes(data)
    outputs = {name: sha256_bytes(data) for name, data in files.items()}

    audit: dict[str, Any] = {
        "adw_version": __version__,
        "parser_version": PARSER_VERSION,
        "schema_version": schema.SCHEMA_VERSION,
        "config_version": CONFIG_VERSION,
        "config": config.to_dict(),
        "ingestion_timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": manifest.to_dict(),
        "input_sha256": manifest.sha256,
        "inspection": {k: inspection[k] for k in
                       ("encoding", "has_bom", "line_endings", "delimiter", "header",
                        "units_row", "coordinate_styles")},
        "totals": result.counts(),
        "issue_code_counts": result.issue_code_counts(),
        "file_issues": [i.to_dict() for i in result.file_issues],
        "outputs": outputs,
        "content_checksum": _content_checksum(outputs),
    }
    (out_dir / AUDIT_NAME).write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def verify_bundle(bundle_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Load audit.json and re-hash every output. Returns (audit, list of problems)."""
    audit_path = bundle_dir / AUDIT_NAME
    if not audit_path.is_file():
        raise SourceError(f"{audit_path} not found; is this an ADW audit bundle?")
    audit: dict[str, Any] = json.loads(audit_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    actual: dict[str, str] = {}
    for name, expected in audit["outputs"].items():
        path = bundle_dir / name
        if not path.is_file():
            problems.append(f"{name}: missing")
            continue
        actual[name] = sha256_bytes(path.read_bytes())
        if actual[name] != expected:
            problems.append(f"{name}: checksum mismatch")
    if not problems and _content_checksum(actual) != audit["content_checksum"]:
        problems.append("content_checksum mismatch")
    return audit, problems
