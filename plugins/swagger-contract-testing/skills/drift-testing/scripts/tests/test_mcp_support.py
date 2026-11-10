from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent

DEF = """tools:
  - name: create_note
  - name: delete_note
resources:
  - uri: notes://all
prompts:
  - name: summarize
"""
TESTS = """drift-testcase-file: v1
sources:
  - name: notes
    path: ./notes.mcp.yaml
plugins:
  - name: mcp
operations:
  d:
    target: notes:drift/all
  t:
    target: notes:tool/create_note
  r:
    target: notes:resource/notes://all
"""


def run(tmp: Path, tests: str, *extra: str) -> subprocess.CompletedProcess[str]:
    (tmp / "notes.mcp.yaml").write_text(DEF)
    (tmp / "drift.yaml").write_text(tests)
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "check_coverage.py"),
            "--spec",
            str(tmp / "notes.mcp.yaml"),
            "--test-files",
            str(tmp / "drift.yaml"),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_gaps_reported(tmp_path: Path) -> None:
    result = run(tmp_path, TESTS)
    assert result.returncode == 1
    assert "✗ tool/delete_note" in result.stdout
    assert "✗ prompt/summarize" in result.stdout
    assert "✓ resource/notes://all" in result.stdout


def test_full_coverage(tmp_path: Path) -> None:
    full = TESTS + "  x:\n    target: notes:tool/delete_note\n  y:\n    target: notes:prompt/summarize\n"
    assert run(tmp_path, full, "--json").returncode == 0
