"""Synthetic cross-matching scenarios: binaries, duplicates, high proper motion, ambiguity.

Everything here is SYNTHETIC. Passing says the logic does what it is designed to do; it says
nothing about real catalogues (UNVERIFIED).
"""

from dataclasses import replace

import pytest

from astronomy_data_workbench.errors import SchemaError
from astronomy_data_workbench.matching.engine import match_catalogues
from astronomy_data_workbench.matching.models import (
    ACCEPTED,
    AMBIGUOUS_CANDIDATES,
    BLOCKING_FLAGS,
    DECISIONS,
    EPOCH_UNCORRECTED,
    POSSIBLE_DUPLICATE_REFERENCE,
    POSSIBLE_MULTIPLE,
    RECIPROCAL_CONFLICT,
    REJECTED,
    REVIEW,
    UNMATCHED,
    Catalogue,
    MatchConfig,
)
from astronomy_data_workbench.matching.synthetic import (
    PRIMARY_NAME,
    REFERENCE_NAME,
    all_scenarios,
    demo_catalogues,
    place_at_epoch,
    scenario_catalogues,
    separation_check,
    shift,
)

SCENARIOS = {s.name: s for s in all_scenarios()}


def run_alone(name, config=None):
    primary, reference = scenario_catalogues(SCENARIOS[name])
    return match_catalogues(primary, reference, config)


def top_id(result):
    return result.candidates[0].entry.entry_id if result.candidates else None


def meets(result, ex):
    return (result.decision == ex.decision and set(ex.reasons) <= set(result.reasons)
            and (ex.top is None or top_id(result) == ex.top)
            and len(result.candidates) >= ex.min_candidates)  # fmt: skip


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_each_scenario_alone_meets_its_stated_expectation(name):
    run = run_alone(name)
    for qid, ex in SCENARIOS[name].expected.items():
        assert meets(run.result_for(qid), ex), (qid, run.result_for(qid).decision,
                                                run.result_for(qid).reasons)  # fmt: skip


def test_all_scenarios_together_agree_with_each_alone():
    """Scenarios sit in separate sky patches, so merging them must not change any outcome."""
    primary, reference, expected = demo_catalogues()
    together = match_catalogues(primary, reference)
    assert len(together.results) == len(expected)
    owner = {qid: name for name, s in SCENARIOS.items() for qid in s.expected}
    for res in together.results:
        alone = run_alone(owner[res.query.entry_id]).result_for(res.query.entry_id)
        assert (res.decision, res.reasons) == (alone.decision, alone.reasons)
        assert meets(res, expected[res.query.entry_id])


def test_every_decision_state_is_exercised():
    primary, reference, _ = demo_catalogues()
    assert {r.decision for r in match_catalogues(primary, reference).results} == set(DECISIONS)


# ---- high proper motion -----------------------------------------------------------------------


def test_high_proper_motion_beats_nearest_neighbour_on_raw_positions():
    primary, reference = scenario_catalogues(SCENARIOS["high_proper_motion"])
    query = primary.entries[0]
    nearest_raw = min(reference.entries, key=lambda r: separation_check(query, r))
    assert nearest_raw.entry_id == "HPM-DECOY"  # the trap: closest if you ignore epochs
    assert separation_check(query, nearest_raw) < 1.0

    result = match_catalogues(primary, reference).result_for("HPM-P")
    assert result.decision == ACCEPTED and top_id(result) == "HPM-R"
    best = result.candidates[0]
    assert best.raw_separation_mas > 12_000  # 12.6 arcsec apart without correction ...
    assert best.separation_mas < 100  # ... tens of mas with it
    assert all(c.entry.entry_id != "HPM-DECOY" for c in result.candidates)  # outside the gate


def test_epoch_gap_is_reflected_in_the_evidence_and_uncertainty():
    best = run_alone("high_proper_motion").result_for("HPM-P").candidates[0]
    text = "\n".join(best.evidence)
    assert "propagated -8.750 yr (2000 -> 1991.25)" in text
    assert "without epoch correction the catalogued positions differ by 12.6" in text
    assert best.measurements["query_dt_years"] == -8.75
    assert best.measurements["query_sigma_mas"] > 400.0  # grew from the 400 mas catalogue error


def test_polar_and_ra_wrap_pairs_are_accepted():
    assert run_alone("polar").result_for("POLAR-P").decision == ACCEPTED
    assert run_alone("ra_wrap").result_for("WRAP-P").decision == ACCEPTED


def test_missing_proper_motion_is_never_auto_accepted():
    result = run_alone("missing_pm").result_for("NOPM-P")
    assert result.decision == REVIEW and EPOCH_UNCORRECTED in result.reasons
    assert top_id(result) == "NOPM-R"  # the true counterpart is still offered to the reviewer
    assert any("no proper motion" in a for a in result.assumptions)


# ---- binaries, duplicates, ambiguity: candidates are preserved --------------------------------


def test_binary_keeps_both_components_and_goes_to_review():
    result = run_alone("binary").result_for("BIN-P")
    assert result.decision == REVIEW
    assert {c.entry.entry_id for c in result.candidates} == {"BIN-A", "BIN-B"}
    assert {POSSIBLE_MULTIPLE, AMBIGUOUS_CANDIDATES} <= set(result.reasons)
    assert all(POSSIBLE_MULTIPLE in c.flags for c in result.candidates)
    assert any("consistent with an unresolved multiple" in n for n in result.notes)
    assert "not consistent" not in " ".join(result.notes)


def test_duplicate_reference_entries_are_flagged_and_both_kept():
    result = run_alone("duplicate_reference").result_for("DUPR-P")
    assert result.decision == REVIEW and POSSIBLE_DUPLICATE_REFERENCE in result.reasons
    assert {c.entry.entry_id for c in result.candidates} == {"DUPR-A", "DUPR-B"}
    assert POSSIBLE_MULTIPLE not in result.reasons  # 0.15 arcsec is a duplicate, not a binary


def test_duplicate_query_entries_both_go_to_review():
    run = run_alone("duplicate_query")
    for qid in ("DUPQ-P1", "DUPQ-P2"):
        r = run.result_for(qid)
        assert r.decision == REVIEW and RECIPROCAL_CONFLICT in r.reasons
        assert any("also claimed by other query objects" in n for n in r.notes)


def test_positional_ambiguity_keeps_every_candidate_in_rank_order():
    result = run_alone("positional_ambiguity").result_for("AMB-P")
    assert [c.entry.entry_id for c in result.candidates][2] == "AMB-R3"
    assert len(result.candidates) == 3 and [c.rank for c in result.candidates] == [1, 2, 3]
    scores = [c.score for c in result.candidates]
    assert scores == sorted(scores, reverse=True)
    assert POSSIBLE_MULTIPLE not in result.reasons  # 6 arcsec apart: ambiguous, not a binary
    assert result.decision == REVIEW and AMBIGUOUS_CANDIDATES in result.reasons
    top, second = result.candidates[:2]
    assert second.score / top.score > 0.9  # genuinely a coin toss


def test_isolated_low_confidence_match_is_not_called_a_reciprocal_conflict():
    """Regression: a low score alone must not be mislabelled as a conflict with other queries."""
    for name, qid in (("marginal", "MARG-P"), ("missing_pm", "NOPM-P")):
        assert RECIPROCAL_CONFLICT not in run_alone(name).result_for(qid).reasons


def test_no_counterpart_and_chance_neighbour():
    lone = run_alone("no_counterpart").result_for("LONE-P")
    assert lone.decision == UNMATCHED and lone.candidates == []
    near = run_alone("implausible_neighbour").result_for("NEAR-P")
    assert near.decision == REJECTED and len(near.candidates) == 1  # kept in the record
    assert near.candidates[0].normalized_separation > 8


# ---- never silently accept low confidence -----------------------------------------------------


def assert_acceptance_invariants(run):
    cfg = run.config
    for r in run.results:
        if r.decision == ACCEPTED:
            best = r.candidates[0]
            assert r.reasons == []
            assert best.normalized_separation <= cfg.accept_sigma
            assert best.relative_confidence >= cfg.accept_confidence
            assert not set(best.flags) & set(BLOCKING_FLAGS)
            if len(r.candidates) > 1:
                assert r.candidates[1].score < cfg.ambiguity_fraction * best.score
        elif r.decision == REVIEW:
            assert r.reasons, f"{r.query.entry_id} sent to review without a reason"
        elif r.decision in (REJECTED, UNMATCHED):
            assert r.reasons


def test_invariants_hold_on_the_demo():
    primary, reference, _ = demo_catalogues()
    assert_acceptance_invariants(match_catalogues(primary, reference))


DECISION_ORDER = {ACCEPTED: 0, REVIEW: 1, REJECTED: 2, UNMATCHED: 3}


def test_moving_a_star_away_never_brings_acceptance_back():
    """Offset one primary star from its reference in 100 mas steps (0 to 6 arcsec).

    Outcomes must worsen monotonically: accepted, then review, then rejected/unmatched.
    """
    base = SCENARIOS["clean"]
    ref = base.reference[0]
    decisions = []
    for offset in range(0, 6001, 100):
        ra, dec = shift(ref.ra_deg, ref.dec_deg, offset, 0.0)
        pra, pdec = place_at_epoch(ra, dec, 2000.0, 80.0, -30.0)
        q = replace(base.primary[0], ra_deg=pra, dec_deg=pdec)
        run = match_catalogues(Catalogue(PRIMARY_NAME, (q,), True),
                               Catalogue(REFERENCE_NAME, base.reference, True))  # fmt: skip
        assert_acceptance_invariants(run)
        decisions.append(run.results[0].decision)
    ranks = [DECISION_ORDER[d] for d in decisions]
    assert ranks == sorted(ranks), decisions
    assert decisions[0] == ACCEPTED
    assert REVIEW in decisions and decisions[-1] == UNMATCHED


def test_raising_the_confidence_bar_only_demotes_acceptances():
    primary, reference, _ = demo_catalogues()
    loose = match_catalogues(primary, reference, MatchConfig(accept_confidence=0.5))
    strict = match_catalogues(primary, reference, MatchConfig(accept_confidence=1.0))
    assert_acceptance_invariants(loose)
    assert_acceptance_invariants(strict)
    assert strict.counts()[ACCEPTED] == 0  # 1.0 is unreachable once the null term exists
    for a, b in zip(loose.results, strict.results, strict=True):
        if a.decision != ACCEPTED:
            assert b.decision == a.decision or b.decision == REVIEW


def test_tighter_acceptance_sigma_demotes_to_review():
    cfg = MatchConfig(accept_sigma=0.05)
    primary, reference, _ = demo_catalogues()
    run = match_catalogues(primary, reference, cfg)
    assert_acceptance_invariants(run)
    assert run.result_for("WRAP-P").decision == REVIEW  # 0.88 sigma pair no longer qualifies


# ---- evidence, uncertainty, provenance --------------------------------------------------------


def test_every_candidate_records_evidence_uncertainty_and_flags():
    primary, reference, _ = demo_catalogues()
    for r in match_catalogues(primary, reference).results:
        d = r.to_dict()
        assert d["validation_status"] == "UNVERIFIED"
        for c in d["candidates"]:
            assert c["evidence"] and c["sigma_mas"] > 0
            assert {"position", "proper_motion", "parallax", "magnitude"} <= set(c["factors"])
            assert c["measurements"]["epoch"] == 1991.25
            assert any("combined 1-sigma" in e for e in c["evidence"])
            assert any("not a calibrated probability" in e for e in c["evidence"])
            assert c["candidate"]["catalogue"] == REFERENCE_NAME
        assert d["query"]["catalogue"] == PRIMARY_NAME


def test_assumed_uncertainties_are_recorded_not_silent():
    primary, reference = scenario_catalogues(SCENARIOS["missing_pm"])
    result = match_catalogues(primary, reference).result_for("NOPM-P")
    assert any("assumed sigma" in a for a in result.assumptions)


def test_results_are_deterministic():
    primary, reference, _ = demo_catalogues()
    a = [r.to_dict() for r in match_catalogues(primary, reference).results]
    b = [r.to_dict() for r in match_catalogues(primary, reference).results]
    assert a == b


def test_reference_epoch_defaults_to_median_and_can_be_overridden():
    primary, reference, _ = demo_catalogues()
    assert match_catalogues(primary, reference).resolved_reference_epoch == 1991.25
    run = match_catalogues(primary, reference, MatchConfig(reference_epoch=2000.0))
    assert run.resolved_reference_epoch == 2000.0
    assert run.result_for("HPM-P").decision == ACCEPTED  # the answer does not depend on the epoch


def test_empty_catalogue_is_refused():
    primary, reference, _ = demo_catalogues()
    with pytest.raises(SchemaError):
        match_catalogues(Catalogue("EMPTY", ()), reference)
    with pytest.raises(SchemaError):
        match_catalogues(primary, Catalogue("EMPTY", ()))


def test_duplicate_ids_within_a_catalogue_are_refused():
    e = SCENARIOS["clean"].primary[0]
    with pytest.raises(SchemaError):
        Catalogue(PRIMARY_NAME, (e, e))
