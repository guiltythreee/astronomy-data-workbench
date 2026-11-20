# Cross-Matching Workbench (module 03)

> **VALIDATION STATUS: UNVERIFIED.** Cross-matching has only been tested on synthetic data. It
> has not been validated against real BSC, Hipparcos or Gaia records. Every output, the CLI and the
> Identity Explorer say so, and none of the numbers below is a validated constant.

## What exists

Epoch-corrected positional matching that keeps every plausible candidate, routes anything
ambiguous to manual review, never silently accepts a low-confidence pair, and records the evidence,
uncertainty and provenance behind each decision.

Not built yet: identifier-based matching, colour comparison, a manual-review resolution workflow,
Hipparcos/Gaia converters, and use of a candidate's proper motion to correct a query that has none.

## Commands

```bash
adw crossmatch demo   --out demo-out                      # built-in SYNTHETIC scenarios
adw crossmatch run    PRIMARY REFERENCE --out out         # your catalogues
adw crossmatch verify out                                 # re-hash the bundle
```

Inputs are `adw-catalogue/1` JSON (see `demo-out/inputs/`) or the `accepted.jsonl` that
`adw export bsc-tsv` writes (add `--bsc-position-error-mas`; BSC publishes none, so it is recorded
as an assumption). Epoch, frame and positional uncertainty must be stated; unknown keys are errors.

## Method

1. **Epoch correction.** Both catalogues are moved to one epoch (default: median reference epoch)
   with the proper motion mu_alpha* (includes cos dec) in a unit-vector model, safe at the poles.
   Uncertainty grows as sigma^2 = sigma_pos^2 + (sigma_pm * |dt|)^2. An entry without proper motion
   is not moved, its sigma is inflated by an assumed value, and it is flagged `EPOCH_UNCORRECTED`.
2. **Candidates.** Every reference object inside the gate `max(3 arcsec, 5 sigma)` (capped at 60
   arcsec) is kept, ranked, and scored: position x proper motion x parallax x magnitude agreement.
3. **Confidence.** A heuristic share of the total score, with a small "no counterpart" term. It is
   not a calibrated probability.
4. **Decision.**

| Decision | When |
|---|---|
| `accepted` | every check passes: <= 3 sigma, share >= 0.90, no rival candidate, no rival query, no blocking flag |
| `review` | anything else with a plausible candidate; reasons are listed |
| `rejected` | every candidate is > 8 sigma and no epoch problem could explain it (kept in the record) |
| `unmatched` | no candidate inside the gate |

Reason codes: `POSITION_INCONSISTENT`, `LOW_CONFIDENCE`, `AMBIGUOUS_CANDIDATES`,
`POSSIBLE_MULTIPLE` (binary), `POSSIBLE_DUPLICATE_REFERENCE`, `RECIPROCAL_CONFLICT` (duplicate
query entries), `EPOCH_UNCORRECTED`, `PM_INCONSISTENT`, `PARALLAX_INCONSISTENT`,
`MAG_INCONSISTENT`, `NO_CANDIDATES`, `ALL_CANDIDATES_IMPLAUSIBLE`.

## Output bundle

`accepted.jsonl`, `review.jsonl`, `rejected.jsonl`, `unmatched.jsonl`, `report.md`,
`crossmatch-audit.json`. Outputs hold no timestamps, so identical input, config and version give
identical files. Each row lists all candidates with separation, combined sigma, factors, flags and
plain-language evidence. The audit file records the thresholds, input checksums and provenance.

## Synthetic tests

Scenarios cover a clean match, high proper motion (with a decoy at the uncorrected position),
a pole-adjacent star, RA wrap-around, missing proper motion, an unresolved binary, duplicate
reference entries, duplicate query entries, positional ambiguity, a marginal match, no
counterpart, a chance neighbour, and proper-motion, parallax and magnitude conflicts. Passing them
shows the logic behaves as designed. It says nothing about real catalogues.

## Validation gate (UNVERIFIED until passed)

1. Run `adw export bsc-tsv` on a real, licence-permitted BSC export and check the parser on it.
2. Match real BSC against real Hipparcos, then Gaia, and review the `review.jsonl` queue by hand.
3. Replace the default thresholds and `null_weight` with values justified by that evidence.
4. Only then change the status text in `matching/models.py`, the Explorer and these documents.
