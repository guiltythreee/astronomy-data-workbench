# Local BSC workflow

1. Export the BSC (CDS V/50) from VizieR as **TSV** with these columns: HR, Name, HD, RAJ2000,
   DEJ2000, Vmag, pmRA, pmDE, Parallax, RadVel. Keep the file outside the repo (e.g. `~/data/`).
2. `adw inspect ~/data/bsc.tsv`. Check the delimiter is `tab`, the header matches, and look at
   `non_numeric_tokens_in_numeric_columns` for null markers other than empty cells.
3. `adw validate bsc-tsv ~/data/bsc.tsv` (add `--null-marker TEXT` for real null markers).
4. `adw export bsc-tsv ~/data/bsc.tsv --out ~/adw-out --release "<release>" --source-url "<url>"`
5. `adw audit ~/adw-out --source ~/data/bsc.tsv`
