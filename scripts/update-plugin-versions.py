#!/usr/bin/env python3
"""Synchronize a version across manifests for marketplace-registered plugins."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from plugin_manifest import load_json

REPO_ROOT = Path(__file__).resolve().parent.parent
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
MANIFEST_PATHS = (
    Path("plugin.json"),
    Path(".claude-plugin/plugin.json"),
    Path(".codex-plugin/plugin.json"),
)


def marketplace_plugins() -> dict[str, Path]:
    marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    marketplace = load_json(marketplace_path, REPO_ROOT)
    entries = marketplace.get("plugins")
    if not isinstance(entries, list):
        raise ValueError(f"{marketplace_path.relative_to(REPO_ROOT)}: 'plugins' must be a list")

    plugins: dict[str, Path] = {}
    for entry in entries:
        valid_entry = (
            isinstance(entry, dict) and isinstance(entry.get("name"), str) and isinstance(entry.get("source"), str)
        )
        if not valid_entry:
            raise ValueError(f"{marketplace_path.relative_to(REPO_ROOT)}: each plugin needs string 'name' and 'source'")
        plugins[entry["name"]] = REPO_ROOT / entry["source"].lstrip("./")
    return plugins


def update_plugin(plugin_name: str, plugin_dir: Path, version: str) -> list[Path]:
    manifests = [plugin_dir / relative_path for relative_path in MANIFEST_PATHS]
    missing = [path.relative_to(REPO_ROOT) for path in manifests if not path.is_file()]
    if missing:
        missing_paths = ", ".join(str(path) for path in missing)
        raise ValueError(f"{plugin_name}: missing manifest(s): {missing_paths}")

    for manifest_path in manifests:
        manifest = load_json(manifest_path, REPO_ROOT)
        if manifest.get("name") != plugin_name:
            raise ValueError(
                f"{manifest_path.relative_to(REPO_ROOT)}: name {manifest.get('name')!r} does not match {plugin_name!r}"
            )

    for manifest_path in manifests:
        manifest = load_json(manifest_path, REPO_ROOT)
        manifest["version"] = version
        manifest_path.write_text(f"{json.dumps(manifest, indent=2, ensure_ascii=False)}\n")
    return manifests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Semantic version to apply, for example 1.3.0")
    parser.add_argument(
        "plugins", nargs="*", metavar="PLUGIN", help="Marketplace plugin names to update (default: all)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not SEMVER_PATTERN.fullmatch(args.version):
        print(f"error: version must be semantic versioning, got {args.version!r}", file=sys.stderr)
        return 2

    try:
        registered_plugins = marketplace_plugins()
        selected_plugins = args.plugins or list(registered_plugins)
        unknown_plugins = sorted(set(selected_plugins) - registered_plugins.keys())
        if unknown_plugins:
            raise ValueError(f"not registered in the marketplace: {', '.join(unknown_plugins)}")

        for plugin_name in selected_plugins:
            update_plugin(plugin_name, registered_plugins[plugin_name], args.version)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Updated {len(selected_plugins)} plugin(s) to {args.version}: {', '.join(selected_plugins)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
