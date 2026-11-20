# Architecture

ADW is a pipeline; each stage has one job and passes explicit typed data on.

`source file -> manifest (SHA-256) -> inspection -> raw table -> validation -> export + audit`

| Package | Responsibility |
|---|---|
| `provenance/` | SourceManifest, SHA-256 |
| `inspection/` | describe a file (encoding, delimiter, header, null-marker candidates) |
| `sources/bsc/` | TSV reader, strict scalar parsers, typed `BscRecord` |
| `schemas/` | expected columns, frame/epoch/units conventions |
| `validation/` | issues, config, row-level classification |
| `export/` | audit bundle writer and verifier |
| `cli.py` | `adw inspect / validate / export / audit / modules / coords-lab / explorer / crossmatch` |

Also present, none validated on real catalogues: `matching/` (Phase 2, partial, UNVERIFIED, `adw crossmatch`),
`coordinates/` (Phase 3, partial) and `identity/` (Phase 4, partial, synthetic
records only). See `docs/modules.md` for the current status of each.
ADW is independent of Star Map; Star Map consumes only reviewed, versioned outputs.
