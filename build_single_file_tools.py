from __future__ import annotations

import shutil
import zipapp
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'src'
PKG = SRC / 'astronomy_data_workbench'
OUT = ROOT / 'dist'
OUT.mkdir(exist_ok=True)

wrappers = {
    '01-catalogue-acquisition-manager': '''from __future__ import annotations\nimport argparse, json\nfrom pathlib import Path\nfrom astronomy_data_workbench.provenance import build_manifest\n\ndef main():\n p=argparse.ArgumentParser(description="Create a provenance manifest and SHA-256 for a local catalogue file.")\n p.add_argument("file",type=Path)\n p.add_argument("--source-name",default="unknown")\n p.add_argument("--release",default="unknown")\n p.add_argument("--source-url")\n p.add_argument("--licence-status",default="unverified")\n p.add_argument("--out",type=Path)\n a=p.parse_args()\n m=build_manifest(a.file,a.source_name,catalogue_release=a.release,source_url=a.source_url,licence_status=a.licence_status).to_dict()\n s=json.dumps(m,indent=2,sort_keys=True)\n if a.out: a.out.write_text(s+"\\n",encoding="utf-8")\n else: print(s)\n return 0\nif __name__=="__main__": raise SystemExit(main())\n''',
    '02-star-catalogue-validator': '''from __future__ import annotations\nimport sys\nfrom astronomy_data_workbench.cli import main\nif __name__=="__main__": raise SystemExit(main(["validate","bsc-tsv",*sys.argv[1:]]))\n''',
    '03-astronomical-cross-matching-workbench': '''from __future__ import annotations\nimport sys\nfrom astronomy_data_workbench.matching.cli import main\nif __name__=="__main__": raise SystemExit(main(sys.argv[1:]))\n''',
    '04-coordinate-accuracy-laboratory': '''from __future__ import annotations\nimport sys\ntry:\n from astronomy_data_workbench.coordinates.lab import main\nexcept ModuleNotFoundError as exc:\n if exc.name in {"astropy", "numpy"}:\n  print(f"Missing dependency: {exc.name}. Install with: pip install numpy astropy", file=sys.stderr)\n  raise SystemExit(2)\n raise\nif __name__=="__main__": raise SystemExit(main(sys.argv[1:]))\n''',
    '05-star-identity-explorer': '''from __future__ import annotations\nimport sys\nfrom astronomy_data_workbench.identity.build_explorer import main\nif __name__=="__main__": raise SystemExit(main(sys.argv[1:]))\n''',
}
for name, code in wrappers.items():
    stage = OUT / (name + '-stage')
    if stage.exists(): shutil.rmtree(stage)
    shutil.copytree(PKG, stage / 'astronomy_data_workbench')
    (stage / '__main__.py').write_text(code, encoding='utf-8')
    target = OUT / (name + '.pyz')
    if target.exists(): target.unlink()
    zipapp.create_archive(stage, target=target, interpreter='/usr/bin/env python3', compressed=True)
    shutil.rmtree(stage)
    print(target.name, target.stat().st_size)
