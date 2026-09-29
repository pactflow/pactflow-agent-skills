from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def load_validator() -> ModuleType:
    path = Path(__file__).resolve().parent.parent / "scripts" / "validate-plugins.py"
    spec = importlib.util.spec_from_file_location("validate_plugins", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate_plugins = load_validator()


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


def test_repository_assets_are_valid() -> None:
    assert validate_plugins.main() == 0
