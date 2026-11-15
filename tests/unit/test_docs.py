from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_required_docs_exist():
    for name in ("architecture", "data-sources", "scientific-conventions",
                 "validation-policy", "roadmap"):  # fmt: skip
        assert (ROOT / "docs" / f"{name}.md").is_file(), name
    assert (ROOT / "README.md").is_file() and (ROOT / "LICENSE").is_file()
