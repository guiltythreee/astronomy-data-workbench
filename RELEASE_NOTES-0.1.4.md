# ADW 0.1.4 release notes

Behaviour-change release on top of 0.1.3. Nothing else differs from 0.1.3.

## Change: negative measured parallax is no longer a review trigger

- `PARALLAX_NEGATIVE` changed from a *warning* to an *info* diagnostic.
- The signed value is kept exactly as measured (never clamped to zero) in `parallax_mas`.
- A row with a negative parallax is accepted unless it has other warnings or errors.
- No tolerance was added: negative values are treated uniformly, because they share one statistical
  explanation (measurement noise on a small true parallax).
- Missing, zero, malformed and implausibly large positive (`PARALLAX_SUSPICIOUS`) values keep their rules.
- Docs: `docs/validation-policy.md`. Tests: three added, one rewritten.

## Evidence: real BSC V/50 export (9,110 rows, VizieR TSV)

| | 0.1.3 | 0.1.4 |
|---|---|---|
| Accepted | 8,932 | 9,096 |
| Review | 164 | 0 |
| Rejected | 14 | 14 |

All 164 rows that moved were reviewed only because of a negative parallax (-32 to -1 mas). They are
still listed as `info` in `issues.csv`. The 14 rejections are non-stellar entries with no position
(novae, M31, 47 Tuc, M67, NGC 2281, NGC 2808).

## Verification (2026-11-20)

Ruff clean; strict MyPy clean (41 files); pytest passing; wheel installed in a clean venv and the
CLI smoke-tested; five `.pyz` rebuilt. Checksums: `SHA256SUMS-0.1.4.txt`.

## Unchanged limits

Cross-matching remains UNVERIFIED. Only BSC has been validated against real data.
