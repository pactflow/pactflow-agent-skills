"""Shared helpers for plugin manifest tooling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path, repo_root: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{path.relative_to(repo_root)}: invalid JSON ({error})") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(repo_root)}: top-level JSON value must be an object")
    return data
