"""Build a single-file local explorer page from a records JSON file.

Usage: python -m astronomy_data_workbench.identity.build_explorer [records.json] [out.html]
Default input is the bundled SYNTHETIC fixture. Opening the output needs no server.
"""
from __future__ import annotations

import hashlib
import json
import sys
from importlib.resources import files
from pathlib import Path


def build(records_path: Path | None, out_path: Path) -> None:
    if records_path is None:
        resource = files(__package__).joinpath("synthetic_stars.json")
        raw = resource.read_bytes()
        source_name = "bundled synthetic fixture"
    else:
        raw = records_path.read_bytes()
        source_name = records_path.name
    data = json.loads(raw)
    meta = {
        "source": "synthetic fixture" if data.get("synthetic") else source_name,
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "schema": "adw-identity-records/0 (draft)",
    }
    html = files(__package__).joinpath("explorer_template.html").read_text(encoding="utf-8")

    def enc(o: object) -> str:
        # "</" is escaped so embedded data can never close the script element.
        return json.dumps(o, ensure_ascii=False).replace("</", "<\\/")

    html = html.replace("/*DATA*/null", enc(data)).replace("/*META*/null", enc(meta))
    out_path.write_text(html, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = (sys.argv[1:] if argv is None else argv)
    src = Path(args[0]) if args else None
    out = Path(args[1]) if len(args) > 1 else Path("identity-explorer.html")
    build(src, out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
