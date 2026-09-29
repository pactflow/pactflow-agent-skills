from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

GENERATOR_DIR = Path(__file__).resolve().parent.parent
GENERATOR_SCRIPTS = sorted(GENERATOR_DIR.glob("dsl_*.py"))


def load_common() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generator_common", GENERATOR_DIR / "_common.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_common = load_common()


def test_temporary_clone_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    cloned_paths: list[Path] = []

    def fake_clone(_repo_url: str, _ref: str, destination: Path) -> None:
        destination.mkdir()
        cloned_paths.append(destination)

    monkeypatch.setattr(_common, "clone_shallow", fake_clone)

    with _common.temporary_clone("https://example.test/repo.git", "v1", "repo") as repo:
        assert repo.is_dir()

    assert len(cloned_paths) == 1
    assert not cloned_paths[0].exists()


def test_checked_in_generated_documents_have_required_structure() -> None:
    for path in _common.REFERENCES_DIR.glob("dsl.*.md"):
        _common.validate_generated_document(path.read_text())


@pytest.mark.parametrize("content", ["", "## Heading\n", "```text\nvalue\n```\n"])
def test_generated_document_validation_rejects_incomplete_output(content: str) -> None:
    with pytest.raises(ValueError, match="generated document"):
        _common.validate_generated_document(content)


@pytest.mark.parametrize("script", GENERATOR_SCRIPTS, ids=lambda path: path.stem)
def test_generator_cli_help(script: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
