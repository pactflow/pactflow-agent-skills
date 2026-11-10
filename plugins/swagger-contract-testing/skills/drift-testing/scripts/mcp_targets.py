"""MCP definition + Drift test-file helpers for coverage checking.

The SmartBear Studio MCP definition format is not publicly documented, so the
parser is deliberately tolerant: tools/resources/prompts may be lists of objects
or maps keyed by name/uri, at the top level or nested under `mcp`/`server`.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from typing import Any

import yaml

MCP_SUFFIXES = (".mcp.yaml", ".mcp.yml", ".mcp.json")
DRIFT_CHECKS = ("tools", "resources", "resourceTemplates", "prompts", "capabilities", "discover")
KINDS = {"tool": "tools", "resource": "resources", "prompt": "prompts"}
ID_KEYS = {"tools": "name", "prompts": "name", "resources": "uri"}


def is_mcp_path(path: str) -> bool:
    return path.lower().endswith(MCP_SUFFIXES)


def _load(path: str) -> Any:
    with open(path) as handle:
        return json.load(handle) if path.lower().endswith(".json") else yaml.safe_load(handle)


def _names(section: Any, id_key: str) -> list[str]:
    if isinstance(section, dict):
        return [str(k) for k in section]
    if isinstance(section, list):
        out = []
        for item in section:
            if isinstance(item, dict):
                value = item.get(id_key) or item.get("name") or item.get("uri")
                if value:
                    out.append(str(value))
            elif isinstance(item, str):
                out.append(item)
        return out
    return []


def load_mcp_items(path: str) -> dict[str, list[str]]:
    """Return {'tools': [...], 'resources': [...], 'prompts': [...], 'resourceTemplates': [...]}."""
    raw = _load(path)
    if not isinstance(raw, dict):
        raise ValueError("MCP definition must be a mapping")
    roots = [raw] + [raw[k] for k in ("mcp", "server") if isinstance(raw.get(k), dict)]
    items: dict[str, list[str]] = {"tools": [], "resources": [], "prompts": [], "resourceTemplates": []}
    for root in roots:
        for section, id_key in ID_KEYS.items():
            items[section] += _names(root.get(section), id_key)
        items["resourceTemplates"] += _names(root.get("resourceTemplates"), "uriTemplate")
    return items


def load_mcp_targets(paths: Iterable[str], *, warn: bool = False) -> set[tuple[str, str]]:
    """Return covered (kind, name) pairs, e.g. ('tool', 'create_note'), ('drift', 'all')."""
    covered: set[tuple[str, str]] = set()
    for path in paths:
        try:
            data = _load(path)
        except (OSError, yaml.YAMLError, ValueError) as error:
            if warn:
                print(f"WARNING: Could not read {path}: {error}", file=sys.stderr)
            continue
        operations = data.get("operations") if isinstance(data, dict) else None
        if not isinstance(operations, dict):
            continue
        for op in operations.values():
            target = str(op.get("target", "")) if isinstance(op, dict) else ""
            _, sep, rest = target.partition(":")  # drop source name; resource URIs contain ':'
            kind, slash, name = rest.partition("/")
            if sep and slash and name:
                covered.add((kind, name))
    return covered


def required_targets(items: dict[str, list[str]]) -> list[tuple[str, str]]:
    req: list[tuple[str, str]] = [("drift", "all")]
    for kind, section in KINDS.items():
        req += [(kind, n) for n in items[section]]
    return req


def is_covered(target: tuple[str, str], covered: set[tuple[str, str]]) -> bool:
    if target in covered:
        return True
    if target == ("drift", "all"):  # satisfied by the individual checks, too
        return all(("drift", c) in covered for c in DRIFT_CHECKS)
    return False


def describe(path: str) -> str:
    return os.path.basename(path)
