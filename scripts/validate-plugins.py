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
  6. Every plugins/*/plugin.json (the portable agent-plugins.org manifest,
     at the plugin root rather than under .claude-plugin/) is valid JSON,
     has the exact `$schema` the standard requires, a `name` matching the
     standard's naming pattern, and matches the .claude-plugin name. If a
     sibling root mcp.json exists, same treatment for its `$schema` and
     required `mcpServers`.

Exits 1 with a list of every failure found (not just the first), 0 if clean.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from plugin_manifest import load_json as read_json

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_PLUGIN_KEYS = ("name", "description", "version")
AGENT_PLUGINS_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_PLUGINS_MCP_SCHEMA_URL = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
AGENT_PLUGINS_NAME_PATTERN = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(errors: list[str], path: Path) -> dict[str, Any] | None:
    try:
        return read_json(path, REPO_ROOT)
    except ValueError as error:
        fail(errors, str(error))
        return None


def check_frontmatter(errors: list[str], path: Path, required_keys: tuple[str, ...]) -> None:
    lines = path.read_text().splitlines()
    if not lines or lines[0].strip() != "---":
        fail(errors, f"{path.relative_to(REPO_ROOT)}: does not start with a '---' frontmatter block")
        return
    try:
        closing_idx = lines[1:].index("---") + 1
    except ValueError:
        fail(errors, f"{path.relative_to(REPO_ROOT)}: frontmatter block has no closing '---'")
        return
    frontmatter_lines = lines[1:closing_idx]
    for key in required_keys:
        if not any(line.startswith(f"{key}:") for line in frontmatter_lines):
            fail(errors, f"{path.relative_to(REPO_ROOT)}: frontmatter has no '{key}:' key")


def validate_claude_manifest(errors: list[str], path: Path, data: dict[str, Any]) -> str | None:
    for key in REQUIRED_PLUGIN_KEYS:
        if key not in data:
            fail(errors, f"{path.relative_to(REPO_ROOT)}: missing required key '{key}'")

    version = data.get("version")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        fail(errors, f"{path.relative_to(REPO_ROOT)}: 'version' must be semantic versioning")

    name = data.get("name")
    return name if isinstance(name, str) else None


def check_codex_manifest(errors: list[str], plugin_dir: Path, claude_path: Path, claude_data: dict[str, Any]) -> None:
    codex_path = plugin_dir / ".codex-plugin" / "plugin.json"
    if not codex_path.is_file():
        return
    codex_data = load_json(errors, codex_path)
    if codex_data is not None and codex_data != claude_data:
        fail(
            errors,
            f"{codex_path.relative_to(REPO_ROOT)} does not match "
            f"{claude_path.relative_to(REPO_ROOT)} (should be identical)",
        )


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

        data = load_json(errors, claude_json)
        if data is None:
            continue

        name = validate_claude_manifest(errors, claude_json, data)
        if name is not None:
            plugin_dirs[name] = plugin_dir
        check_codex_manifest(errors, plugin_dir, claude_json, data)

    return plugin_dirs


def check_marketplace(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        fail(errors, f"missing {marketplace_path.relative_to(REPO_ROOT)}")
        return

    marketplace = load_json(errors, marketplace_path)
    if marketplace is None:
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

        plugin_data = load_json(errors, entry_plugin_json)
        if plugin_data is None:
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


def validate_portable_identity(
    errors: list[str],
    name: str,
    manifest_path: Path,
    data: dict[str, Any],
    claude_data: dict[str, Any],
) -> None:
    claude_path = manifest_path.parent / ".claude-plugin" / "plugin.json"
    if data.get("$schema") != AGENT_PLUGINS_SCHEMA_URL:
        fail(
            errors,
            f"{manifest_path.relative_to(REPO_ROOT)}: '$schema' must be '{AGENT_PLUGINS_SCHEMA_URL}', "
            f"got {data.get('$schema')!r}",
        )

    manifest_name = data.get("name")
    if not manifest_name or not AGENT_PLUGINS_NAME_PATTERN.match(manifest_name):
        fail(
            errors,
            f"{manifest_path.relative_to(REPO_ROOT)}: 'name' {manifest_name!r} does not match the "
            f"agent-plugins.org naming pattern",
        )
    elif manifest_name != name:
        fail(
            errors,
            f"{manifest_path.relative_to(REPO_ROOT)}: 'name' {manifest_name!r} does not match "
            f".claude-plugin/plugin.json 'name' {name!r}",
        )

    if data.get("version") != claude_data.get("version"):
        fail(
            errors, f"{manifest_path.relative_to(REPO_ROOT)}: 'version' must match {claude_path.relative_to(REPO_ROOT)}"
        )


def check_mcp_config(errors: list[str], plugin_dir: Path, claude_path: Path, claude_data: dict[str, Any]) -> None:
    mcp_path = plugin_dir / "mcp.json"
    if not mcp_path.is_file():
        return
    mcp_data = load_json(errors, mcp_path)
    if mcp_data is None:
        return

    if mcp_data.get("$schema") != AGENT_PLUGINS_MCP_SCHEMA_URL:
        fail(
            errors,
            f"{mcp_path.relative_to(REPO_ROOT)}: '$schema' must be '{AGENT_PLUGINS_MCP_SCHEMA_URL}', "
            f"got {mcp_data.get('$schema')!r}",
        )
    portable_servers = mcp_data.get("mcpServers")
    if not isinstance(portable_servers, dict):
        fail(errors, f"{mcp_path.relative_to(REPO_ROOT)}: missing or invalid 'mcpServers' object")
        return

    claude_mcp_ref = claude_data.get("mcpServers")
    if not isinstance(claude_mcp_ref, str):
        return
    claude_mcp_path = plugin_dir / claude_mcp_ref
    if not claude_mcp_path.is_file():
        fail(errors, f"{claude_path.relative_to(REPO_ROOT)}: MCP config does not exist: {claude_mcp_ref}")
        return
    claude_mcp_data = load_json(errors, claude_mcp_path)
    if claude_mcp_data is None:
        return

    normalized = {
        server_name: {key: value for key, value in server.items() if key != "type"}
        for server_name, server in portable_servers.items()
        if isinstance(server, dict)
    }
    if normalized != claude_mcp_data.get("mcpServers"):
        fail(errors, f"{claude_mcp_path.relative_to(REPO_ROOT)} does not match portable mcp.json")


def check_agent_plugins_manifest(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    """Validate the portable plugins/*/plugin.json (agent-plugins.org standard)."""
    for name, plugin_dir in plugin_dirs.items():
        manifest_path = plugin_dir / "plugin.json"
        if not manifest_path.is_file():
            fail(errors, f"{plugin_dir.relative_to(REPO_ROOT)}: missing root plugin.json (agent-plugins.org manifest)")
            continue

        data = load_json(errors, manifest_path)
        claude_path = plugin_dir / ".claude-plugin" / "plugin.json"
        claude_data = load_json(errors, claude_path)
        if data is None or claude_data is None:
            continue

        validate_portable_identity(errors, name, manifest_path, data, claude_data)
        check_mcp_config(errors, plugin_dir, claude_path, claude_data)


def check_skill_frontmatter(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    for _name, plugin_dir in plugin_dirs.items():
        for skill_md in sorted(plugin_dir.rglob("SKILL.md")):
            check_frontmatter(errors, skill_md, ("name", "description"))


def check_hook_command(errors: list[str], hooks_path: Path, plugin_dir: Path, hook: Any) -> None:
    if not isinstance(hook, dict):
        fail(errors, f"{hooks_path.relative_to(REPO_ROOT)}: command hook must be an object")
        return
    command = hook.get("command")
    if isinstance(command, str) and command.startswith("${CLAUDE_PLUGIN_ROOT}/"):
        command_path = plugin_dir / command.removeprefix("${CLAUDE_PLUGIN_ROOT}/")
        if not command_path.is_file():
            fail(errors, f"{hooks_path.relative_to(REPO_ROOT)}: command does not exist: {command}")


def check_hook_event(errors: list[str], hooks_path: Path, plugin_dir: Path, event_hooks: Any) -> None:
    if not isinstance(event_hooks, list):
        fail(errors, f"{hooks_path.relative_to(REPO_ROOT)}: hook event value must be a list")
        return
    for event_hook in event_hooks:
        if not isinstance(event_hook, dict) or not isinstance(event_hook.get("hooks"), list):
            fail(errors, f"{hooks_path.relative_to(REPO_ROOT)}: hook entry must contain a 'hooks' list")
            continue
        for hook in event_hook["hooks"]:
            check_hook_command(errors, hooks_path, plugin_dir, hook)


def check_agents_and_hooks(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    for _name, plugin_dir in plugin_dirs.items():
        for agent_md in sorted((plugin_dir / "agents").glob("*.md")):
            check_frontmatter(errors, agent_md, ("name", "description"))

        hooks_path = plugin_dir / "hooks" / "hooks.json"
        if not hooks_path.is_file():
            continue
        hooks_data = load_json(errors, hooks_path)
        if hooks_data is None or not isinstance(hooks_data.get("hooks"), dict):
            fail(errors, f"{hooks_path.relative_to(REPO_ROOT)}: missing or invalid 'hooks' object")
            continue
        for event_hooks in hooks_data["hooks"].values():
            check_hook_event(errors, hooks_path, plugin_dir, event_hooks)


def eval_entries(errors: list[str], eval_path: Path, data: dict[str, Any]) -> list[Any]:
    if "evals" not in data:
        return [data]
    entries = data.get("evals")
    if not isinstance(data.get("skill_name"), str) or not isinstance(entries, list) or not entries:
        fail(errors, f"{eval_path.relative_to(REPO_ROOT)}: aggregate eval requires skill_name and evals")
        return []
    return entries


def check_eval_entry(errors: list[str], eval_path: Path, entry: Any) -> None:
    if not isinstance(entry, dict):
        fail(errors, f"{eval_path.relative_to(REPO_ROOT)}: each eval must be an object")
        return
    prompt = entry.get("prompt", entry.get("query"))
    expected = entry.get("expected_output", entry.get("expected_behavior"))
    if not isinstance(prompt, str) or not prompt.strip():
        fail(errors, f"{eval_path.relative_to(REPO_ROOT)}: each eval requires a prompt or query")
    if not isinstance(expected, (str, list)):
        fail(errors, f"{eval_path.relative_to(REPO_ROOT)}: each eval requires expected output or behavior")
    files = entry.get("files", [])
    if not isinstance(files, list) or not all(isinstance(path, str) for path in files):
        fail(errors, f"{eval_path.relative_to(REPO_ROOT)}: eval 'files' must be a list of paths")
        return
    skill_dir = eval_path.parent.parent
    for file_ref in files:
        if Path(file_ref).is_absolute() or not (skill_dir / file_ref).is_file():
            fail(errors, f"{eval_path.relative_to(REPO_ROOT)}: eval file does not exist: {file_ref}")


def check_evals(errors: list[str], plugin_dirs: dict[str, Path]) -> None:
    for _name, plugin_dir in plugin_dirs.items():
        for eval_path in sorted(plugin_dir.rglob("evals/*.json")):
            data = load_json(errors, eval_path)
            if data is None:
                continue
            for entry in eval_entries(errors, eval_path, data):
                check_eval_entry(errors, eval_path, entry)


def check_powers(errors: list[str]) -> None:
    powers_root = REPO_ROOT / "powers"
    if not powers_root.is_dir():
        return
    for power_dir in sorted(path for path in powers_root.iterdir() if path.is_dir()):
        power_md = power_dir / "POWER.md"
        if not power_md.is_file():
            fail(errors, f"{power_dir.relative_to(REPO_ROOT)}: missing POWER.md")
        else:
            check_frontmatter(errors, power_md, ("name", "displayName", "description"))
        mcp_path = power_dir / "mcp.json"
        if mcp_path.is_file():
            data = load_json(errors, mcp_path)
            if data is not None and not isinstance(data.get("mcpServers"), dict):
                fail(errors, f"{mcp_path.relative_to(REPO_ROOT)}: missing or invalid 'mcpServers' object")


def main() -> int:
    errors: list[str] = []
    plugin_dirs = check_plugin_jsons(errors)
    check_marketplace(errors, plugin_dirs)
    check_agent_plugins_manifest(errors, plugin_dirs)
    check_skill_frontmatter(errors, plugin_dirs)
    check_agents_and_hooks(errors, plugin_dirs)
    check_evals(errors, plugin_dirs)
    check_powers(errors)

    if errors:
        print(f"validate-plugins: {len(errors)} problem(s) found:\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"validate-plugins: OK ({len(plugin_dirs)} plugin(s) checked: {', '.join(sorted(plugin_dirs))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
