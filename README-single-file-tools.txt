ASTRONOMY DATA WORKBENCH — SINGLE-FILE TOOLS

Each .pyz is a single-file Python application archive. Run it with Python 3.12+.

01-catalogue-acquisition-manager.pyz
  Local-file provenance manifest + SHA-256. Automated catalogue downloads are not implemented.
  Example: python 01-catalogue-acquisition-manager.pyz catalogue.tsv --source-name BSC --out manifest.json

02-star-catalogue-validator.pyz
  BSC V/50 VizieR TSV validation. Preserves accepted/review/rejected row reporting.
  Example: python 02-star-catalogue-validator.pyz catalogue.tsv

03-astronomical-cross-matching-workbench.pyz
  UNVERIFIED: epoch-corrected positional cross-matching, tested on SYNTHETIC data only.
  Not validated against real BSC, Hipparcos or Gaia records.
  Example: python 03-astronomical-cross-matching-workbench.pyz demo --out demo-out

04-coordinate-accuracy-laboratory.pyz
  Coordinate reference suites; writes coords-lab-report.json by default.
  Requires NumPy and Astropy installed in the Python environment.
  Example: python 04-coordinate-accuracy-laboratory.pyz --out report.json

05-star-identity-explorer.pyz
  Generates a local HTML explorer. The bundled dataset is synthetic test data, not real stars.
  Example: python 05-star-identity-explorer.pyz
  Optional original interface: python 05-star-identity-explorer.pyz records.json output.html

The main `adw` CLI also exposes `adw coords-lab`, `adw explorer`, `adw modules` and
`adw crossmatch`. The .pyz archives embed the ADW package source and tool assets, but do not
vendor Python or third-party libraries. Install dependencies with: pip install numpy astropy

Source consolidation used astronomy-data-workbench.zip, adw-update-0.1.1.zip,
adw-update-0.1.2.zip, adw-phase3-backup-1.zip through -4.zip,
adw-phase3-4-backup-6.zip, files(1).zip. The duplicate backup ending in "(1)" was
byte-identical to adw-phase3-4-backup-6.zip and was not applied twice.

Integrity note: source archives were preserved unchanged. The merged source tree retains the
0.1.2 base package initializer and overlays the latest Phase 3/4 module files; earlier backups
are retained only as historical input, not overlaid over later revisions.
