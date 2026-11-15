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
| `cli.py` | `adw inspect / validate / export / audit` |

Planned (not built yet): `matching/` (Phase 2), `coordinates/` (Phase 3), `identity/` (Phase 4).
ADW is independent of Star Map; Star Map consumes only reviewed, versioned outputs.
