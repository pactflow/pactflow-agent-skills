from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def load_script(module_name: str, script_name: str) -> ModuleType:
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    path = scripts_dir / script_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts_dir))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


validate_plugins = load_script("validate_plugins", "validate-plugins.py")
update_plugin_versions = load_script("update_plugin_versions", "update-plugin-versions.py")


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def create_plugin(root: Path, *, portable_version: str = "1.0.0") -> Path:
    plugin_dir = root / "plugins" / "example"
    claude_manifest = {"name": "example", "description": "Example plugin", "version": "1.0.0"}
    write_json(plugin_dir / ".claude-plugin" / "plugin.json", claude_manifest)
    write_json(plugin_dir / ".codex-plugin" / "plugin.json", claude_manifest)
    write_json(
        plugin_dir / "plugin.json",
        {
            "$schema": validate_plugins.AGENT_PLUGINS_SCHEMA_URL,
            "name": "example",
            "description": "Example plugin",
            "version": portable_version,
        },
    )
    return plugin_dir


def test_portable_manifest_version_must_match_claude_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validate_plugins, "REPO_ROOT", tmp_path)
    create_plugin(tmp_path, portable_version="2.0.0")
    errors: list[str] = []

    plugin_dirs = validate_plugins.check_plugin_jsons(errors)
    validate_plugins.check_agent_plugins_manifest(errors, plugin_dirs)

    assert any("'version' must match" in error for error in errors)


def test_mcp_configs_must_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validate_plugins, "REPO_ROOT", tmp_path)
    plugin_dir = create_plugin(tmp_path)
    claude_manifest = json.loads((plugin_dir / ".claude-plugin" / "plugin.json").read_text())
    claude_manifest["mcpServers"] = "./.mcp.json"
    write_json(plugin_dir / ".claude-plugin" / "plugin.json", claude_manifest)
    write_json(plugin_dir / ".codex-plugin" / "plugin.json", claude_manifest)
    write_json(plugin_dir / ".mcp.json", {"mcpServers": {"example": {"command": "one"}}})
    write_json(
        plugin_dir / "mcp.json",
        {
            "$schema": validate_plugins.AGENT_PLUGINS_MCP_SCHEMA_URL,
            "mcpServers": {"example": {"type": "stdio", "command": "two"}},
        },
    )
    errors: list[str] = []

    plugin_dirs = validate_plugins.check_plugin_jsons(errors)
    validate_plugins.check_agent_plugins_manifest(errors, plugin_dirs)

    assert any("does not match portable mcp.json" in error for error in errors)


def test_invalid_eval_shape_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(validate_plugins, "REPO_ROOT", tmp_path)
    plugin_dir = create_plugin(tmp_path)
    write_json(plugin_dir / "skills" / "example" / "evals" / "evals.json", {"skill_name": "example", "evals": []})
    errors: list[str] = []

    validate_plugins.check_evals(errors, {"example": plugin_dir})

    assert any("aggregate eval requires" in error for error in errors)


def test_updates_all_manifests_for_a_marketplace_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_plugin_versions, "REPO_ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins" / "example"
    manifest = {"name": "example", "description": "Example", "version": "1.0.0"}
    for relative_path in update_plugin_versions.MANIFEST_PATHS:
        write_json(plugin_dir / relative_path, manifest)
    write_json(
        tmp_path / ".claude-plugin" / "marketplace.json",
        {"plugins": [{"name": "example", "source": "./plugins/example"}]},
    )

    marketplace_plugins = update_plugin_versions.marketplace_plugins()
    updated_paths = update_plugin_versions.update_plugin("example", marketplace_plugins["example"], "1.2.3")

    assert updated_paths == [plugin_dir / relative_path for relative_path in update_plugin_versions.MANIFEST_PATHS]
    assert all(json.loads(path.read_text())["version"] == "1.2.3" for path in updated_paths)


def test_repository_assets_are_valid() -> None:
    assert validate_plugins.main() == 0
