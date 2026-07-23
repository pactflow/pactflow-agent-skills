#!/usr/bin/env python3
"""Structural validation for plugins/ and .claude-plugin/marketplace.json.

Dependency-free (stdlib only) so it runs anywhere python3 is available, no
uv/pip install needed. Checks:

  1. Every plugins/*/.claude-plugin/plugin.json is valid JSON with the
     required keys (name, description, version).
  2. If a sibling .codex-plugin/plugin.json exists, it is byte-identical
     to the .claude-plugin one.
  3. .claude-plugin/marketplace.json is valid JSON; every entry's `source`
     directory exists and its plugin.json `name` matches the entry's `name`.
  4. Every plugins/*/ directory with a .claude-plugin/plugin.json has a
     corresponding marketplace entry (no unregistered plugin directories).
  5. Every SKILL.md under plugins/*/skills/**/SKILL.md (or
     plugins/*/**/SKILL.md more generally) has a frontmatter block
     (--- ... ---) containing a `name:` line.

Exits 1 with a list of every failure found (not just the first), 0 if clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_PLUGIN_KEYS = ("name", "description", "version")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_plugin_jsons(errors: list[str]) -> dict[str, Path]:
    """Validate every plugins/*/.claude-plugin/plugin.json. Returns {name: plugin_dir}."""
    plugin_dirs: dict[str, Path] = {}
    plugins_root = REPO_ROOT / "plugins"
    if not plugins_root.is_dir():
        fail(errors, f"no plugins/ directory found at {plugins_root}")
        return plugin_dirs

    for plugin_dir in sorted(p for p in plugins_root.iterdir() if p.is_dir()):
        claude_json = plugin_dir / ".claude-plugin" / "plugin.json"
        if not claude_json.is_file():
            fail(errors, f"{plugin_dir.relative_to(REPO_ROOT)}: missing .claude-plugin/plugin.json")
            continue

        try:
            data = json.loads(claude_json.read_text())
        except json.JSONDecodeError as e:
            fail(errors, f"{claude_json.relative_to(REPO_ROOT)}: invalid JSON ({e})")
            continue

        for key in REQUIRED_PLUGIN_KEYS:
            if key not in data:
                fail(errors, f"{claude_json.relative_to(REPO_ROOT)}: missing required key '{key}'")

        name = data.get("name")
        if name:
            plugin_dirs[name] = plugin_dir

        codex_json = plugin_dir / ".codex-plugin" / "plugin.json"
        if codex_json.is_file():
            try:
                codex_data = json.loads(codex_json.read_text())
            except json.JSONDecodeError as e:
                fail(errors, f"{codex_json.relative_to(REPO_ROOT)}: invalid JSON ({e})")
                continue
            if codex_data != data:
                fail(
                    errors,
                    f"{codex_json.relative_to(REPO_ROOT)} does not match "
                    f"{claude_json.relative_to(REPO_ROOT)} (should be identical)",
                )

    return plugin_dirs


def check_marketplace(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        fail(errors, f"missing {marketplace_path.relative_to(REPO_ROOT)}")
        return

    try:
        marketplace = json.loads(marketplace_path.read_text())
    except json.JSONDecodeError as e:
        fail(errors, f"{marketplace_path.relative_to(REPO_ROOT)}: invalid JSON ({e})")
        return

    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        fail(errors, f"{marketplace_path.relative_to(REPO_ROOT)}: 'plugins' must be a list")
        return

    registered_names: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source")
        if not name or not source:
            fail(errors, f"{marketplace_path.relative_to(REPO_ROOT)}: entry missing 'name' or 'source': {entry}")
            continue
        registered_names.add(name)

        source_dir = (REPO_ROOT / source.lstrip("./")).resolve()
        if not source_dir.is_dir():
            fail(errors, f"marketplace entry '{name}': source directory does not exist: {source}")
            continue

        entry_plugin_json = source_dir / ".claude-plugin" / "plugin.json"
        if not entry_plugin_json.is_file():
            fail(errors, f"marketplace entry '{name}': no plugin.json at {source}/.claude-plugin/plugin.json")
            continue

        try:
            plugin_data = json.loads(entry_plugin_json.read_text())
        except json.JSONDecodeError:
            continue  # already reported by check_plugin_jsons

        if plugin_data.get("name") != name:
            fail(
                errors,
                f"marketplace entry '{name}' points at {source}, whose plugin.json "
                f"declares name '{plugin_data.get('name')}' instead",
            )

    for name, plugin_dir in plugin_dirs.items():
        if name not in registered_names:
            fail(
                errors,
                f"plugin '{name}' at {plugin_dir.relative_to(REPO_ROOT)} has a plugin.json "
                f"but no entry in {marketplace_path.relative_to(REPO_ROOT)}",
            )


def check_skill_frontmatter(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    for name, plugin_dir in plugin_dirs.items():
        for skill_md in sorted(plugin_dir.rglob("SKILL.md")):
            text = skill_md.read_text()
            lines = text.split("\n")
            if not lines or lines[0].strip() != "---":
                fail(errors, f"{skill_md.relative_to(REPO_ROOT)}: does not start with a '---' frontmatter block")
                continue
            try:
                closing_idx = lines[1:].index("---") + 1
            except ValueError:
                fail(errors, f"{skill_md.relative_to(REPO_ROOT)}: frontmatter block has no closing '---'")
                continue
            frontmatter_lines = lines[1:closing_idx]
            if not any(line.startswith("name:") for line in frontmatter_lines):
                fail(errors, f"{skill_md.relative_to(REPO_ROOT)}: frontmatter has no 'name:' key")


def main() -> int:
    errors: list[str] = []
    plugin_dirs = check_plugin_jsons(errors)
    check_marketplace(errors, plugin_dirs)
    check_skill_frontmatter(errors, plugin_dirs)

    if errors:
        print(f"validate-plugins: {len(errors)} problem(s) found:\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"validate-plugins: OK ({len(plugin_dirs)} plugin(s) checked: {', '.join(sorted(plugin_dirs))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
