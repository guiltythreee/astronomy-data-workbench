"""Read catalogues for matching and write the cross-match bundle.

Input formats
* `adw-catalogue/1` JSON: a small, explicit interchange format (epoch, frame, units, uncertainty).
  Hipparcos / Gaia converters will target it once their schemas exist.
* BSC `accepted.jsonl` produced by `adw export bsc-tsv` (only rows the validator accepted).

Nothing is guessed: a missing epoch or positional uncertainty is an error, and unknown keys are
rejected so a typo cannot silently drop a field.

Output files hold no timestamps, so identical input + config + version gives identical files and
an identical content checksum. Only `crossmatch-audit.json` carries the run timestamp.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from astronomy_data_workbench import __version__
from astronomy_data_workbench.errors import SchemaError, SourceError
from astronomy_data_workbench.matching.models import (
    ACCEPTED,
    ALGORITHM,
    REJECTED,
    REVIEW,
    UNMATCHED,
    UNVERIFIED_BANNER,
    VALIDATION_GATE,
    VALIDATION_STATUS,
    Catalogue,
    CatalogueEntry,
    CrossMatchRun,
    MatchResult,
)
from astronomy_data_workbench.provenance import sha256_bytes, sha256_file

CATALOGUE_FORMAT = "adw-catalogue/1"
AUDIT_NAME = "crossmatch-audit.json"
OUTPUT_FILES = ("accepted.jsonl", "review.jsonl", "rejected.jsonl", "unmatched.jsonl", "report.md")

_FILE_KEYS = {"format", "catalogue", "synthetic", "frame", "epoch", "position_error_mas",
              "description", "entries"}  # fmt: skip
_ENTRY_KEYS = {"id", "ra_deg", "dec_deg", "epoch", "pos_err_mas", "pm_ra_cosdec_mas_yr",
               "pm_dec_mas_yr", "pm_err_mas_yr", "parallax_mas", "parallax_err_mas",
               "radial_velocity_km_s", "mag", "passband", "frame", "identifiers",
               "synthetic"}  # fmt: skip


def _num(value: Any, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"{where}: expected a number, got {value!r}")
    if not math.isfinite(value):
        raise SchemaError(f"{where}: number must be finite")
    return float(value)


def _required_num(value: Any, where: str) -> float:
    result = _num(value, where)
    if result is None:
        raise SchemaError(f"{where}: required")
    return result


def catalogue_from_dict(data: dict[str, Any], provenance: dict[str, Any]) -> Catalogue:
    unknown = set(data) - _FILE_KEYS
    if unknown:
        raise SchemaError(f"unknown catalogue keys: {sorted(unknown)}")
    if data.get("format") != CATALOGUE_FORMAT:
        raise SchemaError(f"format must be {CATALOGUE_FORMAT!r}, got {data.get('format')!r}")
    name = data.get("catalogue")
    if not isinstance(name, str) or not name:
        raise SchemaError("'catalogue' (a name) is required")
    entries_raw = data.get("entries")
    if not isinstance(entries_raw, list):
        raise SchemaError("'entries' must be a list")
    default_epoch = _num(data.get("epoch"), "epoch")
    default_err = _num(data.get("position_error_mas"), "position_error_mas")
    default_frame = data.get("frame")
    synthetic = data.get("synthetic", False)
    if not isinstance(synthetic, bool):
        raise SchemaError("'synthetic' must be true or false")

    entries: list[CatalogueEntry] = []
    for index, raw in enumerate(entries_raw):
        if not isinstance(raw, dict):
            raise SchemaError(f"entries[{index}] must be an object")
        bad = set(raw) - _ENTRY_KEYS
        if bad:
            raise SchemaError(f"entries[{index}]: unknown keys {sorted(bad)}")
        eid = raw.get("id")
        if not isinstance(eid, str) or not eid:
            raise SchemaError(f"entries[{index}]: 'id' must be a non-empty string")
        where = f"{name}/{eid}"
        epoch = _num(raw.get("epoch"), f"{where}.epoch")
        epoch = default_epoch if epoch is None else epoch
        err = _num(raw.get("pos_err_mas"), f"{where}.pos_err_mas")
        err = default_err if err is None else err
        if epoch is None:
            raise SchemaError(f"{where}: no epoch (give 'epoch' on the entry or the file)")
        if err is None:
            raise SchemaError(f"{where}: no positional uncertainty (give 'pos_err_mas' or "
                              "'position_error_mas')")  # fmt: skip
        frame = raw.get("frame", default_frame)
        if not isinstance(frame, str) or not frame:
            raise SchemaError(f"{where}: no frame (give 'frame' on the entry or the file)")
        identifiers = raw.get("identifiers", {})
        if not isinstance(identifiers, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in identifiers.items()):
            raise SchemaError(f"{where}: identifiers must map strings to strings")
        passband = raw.get("passband")
        if passband is not None and not isinstance(passband, str):
            raise SchemaError(f"{where}: passband must be text")
        entries.append(CatalogueEntry(
            catalogue=name, entry_id=eid,
            ra_deg=_required_num(raw.get("ra_deg"), f"{where}.ra_deg"),
            dec_deg=_required_num(raw.get("dec_deg"), f"{where}.dec_deg"),
            epoch=epoch, pos_err_mas=err, frame=frame,
            pm_ra_cosdec_mas_yr=_num(raw.get("pm_ra_cosdec_mas_yr"), f"{where}.pm_ra"),
            pm_dec_mas_yr=_num(raw.get("pm_dec_mas_yr"), f"{where}.pm_dec"),
            pm_err_mas_yr=_num(raw.get("pm_err_mas_yr"), f"{where}.pm_err"),
            parallax_mas=_num(raw.get("parallax_mas"), f"{where}.parallax"),
            parallax_err_mas=_num(raw.get("parallax_err_mas"), f"{where}.parallax_err"),
            radial_velocity_km_s=_num(raw.get("radial_velocity_km_s"), f"{where}.rv"),
            mag=_num(raw.get("mag"), f"{where}.mag"), passband=passband,
            identifiers=dict(identifiers),
            synthetic=bool(raw.get("synthetic", synthetic)),
        ))  # fmt: skip
    return Catalogue(name, tuple(entries), synthetic=synthetic, provenance=provenance)


def catalogue_to_dict(catalogue: Catalogue) -> dict[str, Any]:
    """Serialise a catalogue to `adw-catalogue/1` with every value explicit (no file defaults)."""
    entries: list[dict[str, Any]] = []
    for e in catalogue.entries:
        row = {k: v for k, v in e.to_dict().items() if k not in ("catalogue",) and v is not None}
        row["frame"] = e.frame
        if not e.identifiers:
            row.pop("identifiers", None)
        entries.append(row)
    return {
        "format": CATALOGUE_FORMAT,
        "catalogue": catalogue.name,
        "synthetic": catalogue.synthetic,
        "description": catalogue.provenance.get("note") or catalogue.provenance.get("description"),
        "entries": entries,
    }


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SourceError(f"cannot read {path}: {exc}") from exc


def load_catalogue_json(path: Path) -> Catalogue:
    raw = _read_bytes(path)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"{path}: top level must be an object")
    provenance = {"origin": "file", "file_name": path.name, "size_bytes": len(raw),
                  "sha256": sha256_bytes(raw), "format": CATALOGUE_FORMAT,
                  "description": data.get("description")}  # fmt: skip
    return catalogue_from_dict(data, provenance)


def load_bsc_accepted_jsonl(
    path: Path, *, position_error_mas: float, pm_error_mas_yr: float | None = None
) -> Catalogue:
    """Load rows the BSC validator ACCEPTED (from `adw export bsc-tsv`) as a catalogue.

    BSC publishes no positional uncertainty, so the caller must state one; it is recorded as an
    assumption. Rows that are not `accepted` are refused rather than silently used.
    """
    raw = _read_bytes(path)
    entries: list[CatalogueEntry] = []
    for number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            rec = row["record"]
            ident, pos, ast, phot = (rec["identity"], rec["position"], rec["astrometry"],
                                     rec["photometry"])  # fmt: skip
            outcome = row["outcome"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SchemaError(f"{path}:{number}: not a BSC validator output row ({exc})") from exc
        if outcome != ACCEPTED:
            raise SchemaError(f"{path}:{number}: outcome is {outcome!r}; only accepted rows may "
                              "be matched")  # fmt: skip
        if pos.get("epoch") != "J2000.0" or pos.get("frame") != "FK5":
            raise SchemaError(f"{path}:{number}: expected FK5 / J2000.0, got "
                              f"{pos.get('frame')!r} / {pos.get('epoch')!r}")  # fmt: skip
        hr = ident.get("hr")
        if hr is None:
            raise SchemaError(f"{path}:{number}: record has no HR number")
        identifiers = {"HR": str(hr)}
        if ident.get("hd"):
            identifiers["HD"] = str(ident["hd"])
        if ident.get("name"):
            identifiers["Name"] = str(ident["name"])
        pm_a = _num(ast.get("pm_ra_cosdec_mas_yr"), f"line {number} pm_ra")
        pm_d = _num(ast.get("pm_dec_mas_yr"), f"line {number} pm_dec")
        has_pm = pm_a is not None and pm_d is not None
        entries.append(CatalogueEntry(
            catalogue="BSC", entry_id=f"HR {hr}",
            ra_deg=_required_num(pos.get("ra_deg"), f"line {number} ra"),
            dec_deg=_required_num(pos.get("dec_deg"), f"line {number} dec"),
            epoch=2000.0, frame="FK5", pos_err_mas=position_error_mas,
            pm_ra_cosdec_mas_yr=pm_a if has_pm else None,
            pm_dec_mas_yr=pm_d if has_pm else None,
            pm_err_mas_yr=pm_error_mas_yr if has_pm else None,
            parallax_mas=_num(ast.get("parallax_mas"), f"line {number} parallax"),
            radial_velocity_km_s=_num(ast.get("radial_velocity_km_s"), f"line {number} rv"),
            mag=_num(phot.get("vmag"), f"line {number} vmag"), passband=phot.get("passband"),
            identifiers=identifiers,
        ))  # fmt: skip
    provenance = {
        "origin": "bsc-validator-accepted", "file_name": path.name, "size_bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "assumption": f"BSC publishes no position error; {position_error_mas:g} mas was assumed",
    }  # fmt: skip
    return Catalogue("BSC", tuple(entries), synthetic=False, provenance=provenance)


# ---------------------------------------------------------------------------------------------
# Output bundle
# ---------------------------------------------------------------------------------------------


def _dump(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _jsonl(results: list[MatchResult]) -> bytes:
    return "".join(_dump(r.to_dict()) + "\n" for r in results).encode("utf-8")


def _describe_top(result: MatchResult) -> str:
    if not result.candidates:
        return "no candidates"
    c = result.candidates[0]
    more = f" (+{len(result.candidates) - 1} more candidate(s))" if len(result.candidates) > 1 else ""
    return (f"best {c.entry.entry_id}: {c.separation_mas:.1f} mas, {c.normalized_separation:.2f} "
            f"sigma, relative confidence {c.relative_confidence:.3f}{more}")  # fmt: skip


def render_report(run: CrossMatchRun, limit: int = 100) -> str:
    counts = run.counts()
    cfg = run.config.to_dict()
    lines = [
        "# ADW cross-match report", "", f"> **{UNVERIFIED_BANNER}**", "",
        f"- Primary: {run.primary.name} ({len(run.primary.entries)} objects)",
        f"- Reference: {run.reference.name} ({len(run.reference.entries)} objects)",
        f"- Common epoch: {run.resolved_reference_epoch:g}",
        f"- Algorithm: {ALGORITHM}; ADW {__version__}",
        f"- Synthetic inputs: primary {run.primary.synthetic}, reference {run.reference.synthetic}",
        "", "## Outcomes", "", "| Decision | Objects |", "|---|---|",
        f"| Accepted | {counts[ACCEPTED]} |", f"| Review (manual) | {counts[REVIEW]} |",
        f"| Rejected | {counts[REJECTED]} |", f"| Unmatched | {counts[UNMATCHED]} |",
        f"| Total | {counts['total']} |", "", "## Reason codes", "",
    ]  # fmt: skip
    reasons = run.reason_counts()
    lines += [f"- `{k}`: {v}" for k, v in reasons.items()] or ["- none"]
    for title, decision in (("Needs manual review", REVIEW), ("Rejected", REJECTED)):
        rows = run.by_decision(decision)
        if not rows:
            continue
        lines += ["", f"## {title}", ""]
        for r in rows[:limit]:
            lines.append(f"- **{r.query.entry_id}**: {', '.join(r.reasons)}; {_describe_top(r)}")
            lines += [f"  - {n}" for n in r.notes]
        if len(rows) > limit:
            lines.append(f"- ... and {len(rows) - limit} more (see {decision}.jsonl)")
    assumptions = sorted({a for r in run.results for a in r.assumptions})
    lines += ["", "## Assumptions used", ""]
    lines += [f"- {a}" for a in assumptions[:limit]] or ["- none recorded"]
    if len(assumptions) > limit:
        lines.append(f"- ... and {len(assumptions) - limit} more (see the .jsonl files)")
    lines += ["", "## Configuration (all thresholds are UNVERIFIED defaults)", "",
              "| Setting | Value |", "|---|---|"]  # fmt: skip
    lines += [f"| {k} | {v} |" for k, v in cfg.items()]
    lines += ["", "## Validation gate", "", VALIDATION_GATE, ""]
    return "\n".join(lines)


def _content_checksum(outputs: dict[str, str]) -> str:
    joined = "\n".join(f"{name}:{sha}" for name, sha in sorted(outputs.items()))
    return sha256_bytes(joined.encode("utf-8"))


def _input_provenance(catalogue: Catalogue) -> dict[str, Any]:
    return {"name": catalogue.name, "entries": len(catalogue.entries),
            "synthetic": catalogue.synthetic, **catalogue.provenance}  # fmt: skip


def write_bundle(out_dir: Path, run: CrossMatchRun, *, force: bool = False) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise SourceError(f"output directory {out_dir} is not empty (use --force to overwrite)")
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {
        "accepted.jsonl": _jsonl(run.by_decision(ACCEPTED)),
        "review.jsonl": _jsonl(run.by_decision(REVIEW)),
        "rejected.jsonl": _jsonl(run.by_decision(REJECTED)),
        "unmatched.jsonl": _jsonl(run.by_decision(UNMATCHED)),
        "report.md": render_report(run).encode("utf-8"),
    }
    for name, data in files.items():
        (out_dir / name).write_bytes(data)
    outputs = {name: sha256_bytes(data) for name, data in files.items()}
    audit: dict[str, Any] = {
        "validation_status": VALIDATION_STATUS,
        "validation_banner": UNVERIFIED_BANNER,
        "validation_gate": VALIDATION_GATE,
        "adw_version": __version__,
        "algorithm": ALGORITHM,
        "run_timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "resolved_reference_epoch": run.resolved_reference_epoch,
        "config": run.config.to_dict(),
        "inputs": {
            "primary": _input_provenance(run.primary),
            "reference": _input_provenance(run.reference),
        },
        "totals": run.counts(),
        "reason_counts": run.reason_counts(),
        "outputs": outputs,
        "content_checksum": _content_checksum(outputs),
    }
    (out_dir / AUDIT_NAME).write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")  # fmt: skip
    return audit


def verify_bundle(bundle_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Load the audit file and re-hash every output. Returns (audit, problems)."""
    path = bundle_dir / AUDIT_NAME
    if not path.is_file():
        raise SourceError(f"{path} not found; is this a cross-match bundle?")
    audit: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    actual: dict[str, str] = {}
    for name, expected in audit["outputs"].items():
        target = bundle_dir / name
        if not target.is_file():
            problems.append(f"{name}: missing")
            continue
        actual[name] = sha256_file(target)
        if actual[name] != expected:
            problems.append(f"{name}: checksum mismatch")
    if not problems and _content_checksum(actual) != audit["content_checksum"]:
        problems.append("content_checksum mismatch")
    if audit.get("validation_status") != VALIDATION_STATUS:
        problems.append(f"validation_status is {audit.get('validation_status')!r}, expected "
                        f"{VALIDATION_STATUS!r}")  # fmt: skip
    return audit, problems
