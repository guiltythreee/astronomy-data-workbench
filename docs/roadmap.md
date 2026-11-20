# Roadmap

| Phase | Deliverable | Status |
|---|---|---|
| 0 | repository foundation, CI, docs, synthetic fixture | done |
| 1 | BSC TSV inspection, validation, manifest, audit bundle | done; real BSC export validated |
| 1b | Hipparcos-2 TSV schema and validator | implemented; real export validation pending |
| 2 | BSC-Hipparcos-Gaia cross-matching | partial, UNVERIFIED (synthetic only) |
| 3 | Coordinate Accuracy Lab | partial (reference suites exist; real-data validation pending) |
| 4 | Identity Explorer (local web UI) | partial (synthetic records only) |
| 5 | release automation | not started |

Phase 2 was started on synthetic data by decision. Its status stays UNVERIFIED until the matching
pipeline and the BSC parser pass the real-catalogue gate in `docs/crossmatching.md`.
