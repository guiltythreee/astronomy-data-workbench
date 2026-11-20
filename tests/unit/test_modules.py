import json
from pathlib import Path

import pytest

from astronomy_data_workbench.cli import main
from astronomy_data_workbench.modules import AVAILABLE, MODULES, PARTIAL, PLANNED

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "src" / "astronomy_data_workbench"


def test_five_modules_in_spec_order():
    assert [m.number for m in MODULES] == ["01", "02", "03", "04", "05"]
    assert [m.priority for m in MODULES] == [1, 1, 2, 2, 3]


def test_every_module_has_description_and_responsibilities():
    for m in MODULES:
        assert m.description and len(m.responsibilities) >= 3 and m.status_note


def test_docs_list_every_module_name_and_status():
    text = (ROOT / "docs" / "modules.md").read_text(encoding="utf-8")
    for m in MODULES:
        assert m.name in text, m.name


def test_module_implementation_status_matches_source():
    # Module 03 is now built (synthetic-tested only); nothing is left merely planned.
    assert [m.package for m in MODULES if m.status == PLANNED] == []
    matching = next(m for m in MODULES if m.package == "matching")
    assert matching.status == PARTIAL and "UNVERIFIED" in matching.status_note
    assert any(m.status == AVAILABLE for m in MODULES)
    assert (PKG / "coordinates" / "lab.py").is_file()
    assert (PKG / "identity" / "build_explorer.py").is_file()
    assert (PKG / "matching" / "__init__.py").is_file()


def test_modules_command(capsys):
    assert main(["modules"]) == 0
    out = capsys.readouterr().out
    assert "Star Catalogue Validator" in out and "[partial, priority 3]" in out
    assert main(["modules", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 5


def test_module_commands_are_real_cli_subcommands():
    from astronomy_data_workbench.cli import build_parser

    choices = build_parser()._subparsers._group_actions[0].choices  # type: ignore[union-attr]
    for module in MODULES:
        if module.command and module.command.startswith("adw "):
            command = module.command.split()[1]
            assert command in choices, (module.name, command)


def test_explorer_command_builds_synthetic_page(tmp_path, capsys):
    out = tmp_path / "explorer.html"
    assert main(["explorer", "--out", str(out)]) == 0
    assert "SYNTHETIC DATA" in out.read_text(encoding="utf-8")
    assert "bundled SYNTHETIC data" in capsys.readouterr().out


def test_coords_lab_command_writes_report(tmp_path):
    pytest.importorskip("astropy")
    out = tmp_path / "coords.json"
    assert main(["coords-lab", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["all_passed"] is True
