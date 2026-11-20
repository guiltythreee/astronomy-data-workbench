from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_required_docs_exist():
    for name in ("architecture", "data-sources", "scientific-conventions",
                 "validation-policy", "roadmap"):  # fmt: skip
        assert (ROOT / "docs" / f"{name}.md").is_file(), name
    assert (ROOT / "README.md").is_file() and (ROOT / "LICENSE").is_file()


def test_crossmatching_is_marked_unverified_everywhere():
    doc = ROOT / "docs" / "crossmatching.md"
    assert doc.is_file()
    for path in (doc, ROOT / "README.md", ROOT / "docs" / "modules.md", ROOT / "docs" / "roadmap.md",
                 ROOT / "CHANGELOG.md"):  # fmt: skip
        assert "UNVERIFIED" in path.read_text(encoding="utf-8"), path.name
    template = ROOT / "src" / "astronomy_data_workbench" / "identity" / "explorer_template.html"
    assert template.read_text(encoding="utf-8").count("UNVERIFIED") >= 3  # banner, heading, badge
