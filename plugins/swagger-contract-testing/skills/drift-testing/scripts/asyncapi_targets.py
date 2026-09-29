from __future__ import annotations

import sys
from collections.abc import Iterable

import yaml

AsyncAPITarget = tuple[str, str | None]


def _load_operations(path: str, *, warn: bool) -> dict[str, object]:
    try:
        with open(path) as handle:
            data = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as error:
        if warn:
            print(f"WARNING: Could not read {path}: {error}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        return {}
    operations = data.get("operations", {})
    return operations if isinstance(operations, dict) else {}


def _parse_target(operation: object) -> AsyncAPITarget | None:
    if not isinstance(operation, dict):
        return None
    parts = str(operation.get("target", "")).split(":")
    if len(parts) < 2:
        return None
    return parts[1], parts[2] if len(parts) >= 3 else None


def load_asyncapi_targets(paths: Iterable[str], *, warn: bool = False) -> set[AsyncAPITarget]:
    """Return operation/message targets declared by Drift test files."""
    covered: set[AsyncAPITarget] = set()
    for path in paths:
        for operation in _load_operations(path, warn=warn).values():
            target = _parse_target(operation)
            if target:
                covered.add(target)
    return covered
