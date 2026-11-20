import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import astronomy_data_workbench.identity as ident
from astronomy_data_workbench.identity.build_explorer import build

FIXTURE = Path(ident.__file__).parent / "synthetic_stars.json"


def test_fixture_is_entirely_synthetic_and_covers_all_states():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["synthetic"] is True
    assert all(r["synthetic"] is True for r in data["records"])
    assert {r["validation"]["state"] for r in data["records"]} == {"accepted", "review", "rejected"}
    assert all(r["identifiers"]["HR"].startswith("SYN-") for r in data["records"])


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_built_page_has_banner_provenance_and_valid_script(tmp_path):
    out = tmp_path / "explorer.html"
    build(FIXTURE, out)
    html = out.read_text(encoding="utf-8")
    assert "SYNTHETIC DATA" in html
    assert re.search(r"[0-9a-f]{64}", html)  # real input checksum embedded
    assert "/*DATA*/" not in html and "/*META*/" not in html
    script = re.search(r"<script>(.*)</script>", html, re.DOTALL).group(1)
    js = tmp_path / "x.js"
    js.write_text(script, encoding="utf-8")
    r = subprocess.run(["node", "--check", str(js)], check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_data_cannot_break_out_of_script_tag(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"synthetic": True, "note": "</script><b>x</b>", "records": []}))
    out = tmp_path / "o.html"
    build(bad, out)
    assert out.read_text(encoding="utf-8").count("</script>") == 1
