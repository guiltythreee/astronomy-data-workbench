"""Epoch-corrected positional cross-matching with preserved candidates and manual-review routing.

Pipeline
1. Propagate both catalogues to one epoch (epoch.py), carrying the growth of uncertainty.
2. For each query object find every reference object inside the search gate (nothing is dropped
   because it is not the nearest) and score it (scoring.py).
3. Convert scores to a heuristic relative confidence that includes a "no counterpart" term, from
   the query's side and from the reference object's side.
4. Decide. A match is ACCEPTED only if every check passes. Anything ambiguous, multiple,
   duplicated, conflicting, uncorrected or inconsistent goes to REVIEW with its reasons.
   REJECTED needs every candidate to be implausible; no candidates at all is UNMATCHED.

Status: UNVERIFIED. Exercised on synthetic data only.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from numpy.typing import NDArray

from astronomy_data_workbench.errors import SchemaError
from astronomy_data_workbench.matching.epoch import PropagatedPosition, propagate_entry
from astronomy_data_workbench.matching.geometry import separation_mas, separations_mas
from astronomy_data_workbench.matching.models import (
    ACCEPTED,
    ALL_CANDIDATES_IMPLAUSIBLE,
    AMBIGUOUS_CANDIDATES,
    BLOCKING_FLAGS,
    EPOCH_UNCORRECTED,
    LOW_CONFIDENCE,
    NEARBY_REFERENCE_OBJECT,
    NO_CANDIDATES,
    POSITION_INCONSISTENT,
    POSSIBLE_DUPLICATE_REFERENCE,
    POSSIBLE_MULTIPLE,
    RECIPROCAL_CONFLICT,
    REJECTED,
    REVIEW,
    UNMATCHED,
    CandidateMatch,
    Catalogue,
    CrossMatchRun,
    MatchConfig,
    MatchResult,
)
from astronomy_data_workbench.matching.scoring import PairEvaluation, evaluate_pair

MAS_PER_ARCSEC = 1000.0
MAS_PER_DEG = 3.6e6


@dataclass
class _Pair:
    ref_index: int
    evaluation: PairEvaluation
    flags: list[str]
    extra_evidence: list[str]


def resolve_reference_epoch(primary: Catalogue, reference: Catalogue, cfg: MatchConfig) -> float:
    if cfg.reference_epoch is not None:
        return cfg.reference_epoch
    return float(statistics.median(e.epoch for e in reference.entries))


def _find_pairs(
    q: PropagatedPosition,
    ref_pos: list[PropagatedPosition],
    order: list[int],
    dec_sorted: NDArray[np.float64],
    vectors: NDArray[np.float64],
    sigma_ref_max: float,
    cfg: MatchConfig,
) -> list[_Pair]:
    floor_mas = cfg.gate_floor_arcsec * MAS_PER_ARCSEC
    cap_mas = cfg.max_gate_arcsec * MAS_PER_ARCSEC
    window_mas = min(cap_mas, max(floor_mas, cfg.gate_sigma * (q.sigma_mas + sigma_ref_max)))
    window_deg = window_mas / MAS_PER_DEG
    lo = int(np.searchsorted(dec_sorted, q.dec_deg - window_deg, side="left"))
    hi = int(np.searchsorted(dec_sorted, q.dec_deg + window_deg, side="right"))
    if hi <= lo:
        return []
    seps = separations_mas(vectors[lo:hi], q.vector)
    pairs: list[_Pair] = []
    for k in range(hi - lo):
        j = order[lo + k]
        r = ref_pos[j]
        sep = float(seps[k])
        gate = min(cap_mas, max(floor_mas, cfg.gate_sigma * math.hypot(q.sigma_mas, r.sigma_mas)))
        if sep <= gate:
            pairs.append(_Pair(j, evaluate_pair(q, r, sep, cfg), [], []))
    # Deterministic order: best score first, then closest, then id.
    pairs.sort(key=lambda p: (-p.evaluation.score, p.evaluation.separation_mas,
                              ref_pos[p.ref_index].entry.entry_id))  # fmt: skip
    return pairs


def _combined_magnitude(mags: list[float]) -> float:
    return -2.5 * math.log10(sum(10.0 ** (-0.4 * m) for m in mags))


def match_catalogues(
    primary: Catalogue, reference: Catalogue, config: MatchConfig | None = None
) -> CrossMatchRun:
    """Match every `primary` object against `reference`. Never mutates its inputs."""
    cfg = config or MatchConfig()
    if not primary.entries or not reference.entries:
        raise SchemaError("both catalogues need at least one entry to be cross-matched")
    epoch = resolve_reference_epoch(primary, reference, cfg)

    q_pos = [propagate_entry(e, epoch, cfg) for e in primary.entries]
    ref_pos = [propagate_entry(e, epoch, cfg) for e in reference.entries]
    order = sorted(range(len(ref_pos)), key=lambda i: (ref_pos[i].dec_deg, i))
    dec_sorted = np.array([ref_pos[i].dec_deg for i in order], dtype=np.float64)
    vectors = np.array([ref_pos[i].vector for i in order], dtype=np.float64)
    sigma_ref_max = max(p.sigma_mas for p in ref_pos)

    all_pairs = [_find_pairs(q, ref_pos, order, dec_sorted, vectors, sigma_ref_max, cfg)
                 for q in q_pos]  # fmt: skip

    # Reference-side totals, so one reference object claimed by several queries is detected.
    reverse_total: dict[int, float] = {}
    for pairs in all_pairs:
        for p in pairs:
            reverse_total[p.ref_index] = reverse_total.get(p.ref_index, 0.0) + p.evaluation.score

    results = [
        _decide(q_pos[i], all_pairs[i], ref_pos, reverse_total, cfg)
        for i in range(len(q_pos))
    ]
    return CrossMatchRun(primary, reference, cfg, epoch, results)


def _decide(
    q: PropagatedPosition,
    pairs: list[_Pair],
    ref_pos: list[PropagatedPosition],
    reverse_total: dict[int, float],
    cfg: MatchConfig,
) -> MatchResult:
    query = q.entry
    assumptions: list[str] = list(q.assumptions)
    if not pairs:
        return MatchResult(
            query, UNMATCHED, [NO_CANDIDATES], [],
            notes=[(f"no reference object within the search gate "
                    f"(floor {cfg.gate_floor_arcsec:g} arcsec, {cfg.gate_sigma:g} sigma)")],
            assumptions=assumptions,
        )  # fmt: skip

    total = sum(p.evaluation.score for p in pairs)
    top = pairs[0]
    top_score = top.evaluation.score
    notes: list[str] = []

    # Multiplicity / duplicates among candidates that fit the query about as well as the best.
    if top_score > 0.0:
        significant = [p for p in pairs
                       if p.evaluation.score >= cfg.multiplicity_score_fraction * top_score]  # fmt: skip
        dup_mas = cfg.duplicate_radius_arcsec * MAS_PER_ARCSEC
        mult_mas = cfg.multiplicity_radius_arcsec * MAS_PER_ARCSEC
        for a, b in combinations(significant, 2):
            ea, eb = ref_pos[a.ref_index], ref_pos[b.ref_index]
            d = separation_mas(ea.vector, eb.vector)
            if d > mult_mas:
                continue
            flag = POSSIBLE_DUPLICATE_REFERENCE if d <= dup_mas else POSSIBLE_MULTIPLE
            what = ("possible duplicate catalogue entries" if flag == POSSIBLE_DUPLICATE_REFERENCE
                    else "possible binary / multiple system")  # fmt: skip
            text = (f"{flag}: reference objects {ea.entry.entry_id} and {eb.entry.entry_id} are "
                    f"{d / MAS_PER_ARCSEC:.3f} arcsec apart and both fit the query ({what})")  # fmt: skip
            for p in (a, b):
                if flag not in p.flags:
                    p.flags.append(flag)
                p.extra_evidence.append(text)
        # Informational: weaker neighbours close to the best candidate.
        sig_ids = {p.ref_index for p in significant}
        for p in pairs[1:]:
            if p.ref_index in sig_ids:
                continue
            d = separation_mas(ref_pos[top.ref_index].vector, ref_pos[p.ref_index].vector)
            if d <= mult_mas:
                if NEARBY_REFERENCE_OBJECT not in top.flags:
                    top.flags.append(NEARBY_REFERENCE_OBJECT)
                top.extra_evidence.append(
                    f"{NEARBY_REFERENCE_OBJECT}: {ref_pos[p.ref_index].entry.entry_id} lies "
                    f"{d / MAS_PER_ARCSEC:.3f} arcsec from the best candidate but fits the query "
                    f"far worse (informational)"
                )

    candidates: list[CandidateMatch] = []
    for rank, p in enumerate(pairs, start=1):
        ev = p.evaluation
        ref = ref_pos[p.ref_index]
        rel = ev.score / (cfg.null_weight + total)
        rev = ev.score / (cfg.null_weight + reverse_total[p.ref_index])
        flags = [*ev.flags, *(f for f in p.flags if f not in ev.flags)]
        evidence = [
            *ev.evidence,
            *p.extra_evidence,
            (
                f"ranked {rank} of {len(pairs)} candidates inside the search gate; relative "
                f"confidence {rel:.3f} (query side), {rev:.3f} (reference side); heuristic "
                "score, not a calibrated probability"
            ),
        ]
        assumptions.extend(a for a in ev.assumptions if a not in assumptions)
        measurements = dict(ev.measurements)
        measurements["rank"] = rank
        candidates.append(CandidateMatch(
            rank=rank, entry=ref.entry, separation_mas=ev.separation_mas,
            raw_separation_mas=ev.raw_separation_mas, sigma_mas=ev.sigma_mas,
            normalized_separation=ev.z, score=ev.score, relative_confidence=rel,
            reverse_confidence=rev, factors=ev.factors, flags=flags, evidence=evidence,
            measurements=measurements,
        ))  # fmt: skip

    best = candidates[0]
    reasons: list[str] = []

    # Rejection needs certainty that nothing is plausible and that no epoch problem is hiding it.
    if (all(c.normalized_separation > cfg.reject_sigma for c in candidates)
            and not any(EPOCH_UNCORRECTED in c.flags for c in candidates)):  # fmt: skip
        notes.append(
            f"every candidate is more than {cfg.reject_sigma:g} sigma from the query; "
            "kept in the record, not matched"
        )
        return MatchResult(query, REJECTED, [ALL_CANDIDATES_IMPLAUSIBLE], candidates,
                           notes=notes, assumptions=assumptions)  # fmt: skip

    if best.normalized_separation > cfg.accept_sigma:
        reasons.append(POSITION_INCONSISTENT)
    if best.relative_confidence < cfg.accept_confidence:
        reasons.append(LOW_CONFIDENCE)
    if len(candidates) > 1 and top_score > 0.0 and (
            candidates[1].score >= cfg.ambiguity_fraction * top_score):
        reasons.append(AMBIGUOUS_CANDIDATES)
        notes.append(
            f"second candidate {candidates[1].entry.entry_id} scores "
            f"{candidates[1].score / top_score:.2f} x the best; the choice is not safe to automate"
        )
    # Reciprocal conflict: other query objects genuinely compete for the same reference object.
    rival = reverse_total[top.ref_index] - top_score
    if top_score > 0.0 and rival >= cfg.ambiguity_fraction * top_score:
        reasons.append(RECIPROCAL_CONFLICT)
        notes.append(
            f"reference object {best.entry.entry_id} is also claimed by other query objects "
            f"(their combined score is {rival / top_score:.2f} x this one's): possible "
            "duplicate query entries or a mis-association"
        )
    for flag in BLOCKING_FLAGS:
        if flag in best.flags and flag not in reasons:
            reasons.append(flag)

    if POSSIBLE_MULTIPLE in reasons:
        mags = [c.entry.mag for c in candidates if c.entry.mag is not None and c.score > 0.0
                and POSSIBLE_MULTIPLE in c.flags]  # fmt: skip
        if query.mag is not None and len(mags) >= 2:
            combined = _combined_magnitude(mags)
            verdict = "consistent" if abs(combined - query.mag) <= 0.3 else "not consistent"
            notes.append(
                f"combined magnitude of the {len(mags)} candidate components is {combined:.2f} "
                f"vs query {query.mag:.2f}: {verdict} with an unresolved multiple "
                "(indicative only; passbands differ)"
            )

    decision = REVIEW if reasons else ACCEPTED
    return MatchResult(query, decision, reasons, candidates, notes=notes, assumptions=assumptions)
