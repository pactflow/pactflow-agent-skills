#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml~=6.0",
# ]
# ///
"""
build_filtered_oas.py — CI tool: discover consumer routes via a code-intelligence tool.

Supported --tool values: ripwire (default), graphify, aider, repowise, codebase-memory,
grep (built-in text scan, no external tool), auto (first available of the above).
repowise uses `repowise ask` (an LLM call; needs a configured provider). codebase-memory
indexes the repo with `codebase-memory-mcp cli` and runs a regex `search_code`.
Any other tool can be used with --tool-cmd.
All non-ripwire tools return free text, so routes are extracted heuristically
(HTTP verb + path literals) and should be reviewed.

Outputs a --consumer-routes JSON list for use with parse_pact_coverage.py.
For adaptive multi-strategy discovery, use the pact-coverage agent instead.

Usage:
  uv run scripts/build_filtered_oas.py --consumer-root ./consumer-src --output routes.json
  uv run scripts/build_filtered_oas.py --consumer-root ./consumer-src --tool graphify
  uv run scripts/build_filtered_oas.py --consumer-root ./consumer-src --tool repowise \
    --tool-cmd 'repowise search "HTTP API route calls"'
  uv run scripts/parse_pact_coverage.py --spec provider-oas.yaml --pacts "pacts/*.json" \
    --consumer-routes "$(cat routes.json)"

Exit codes:
  0 — routes JSON written
  1 — no routes found
  2 — error
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ─── ripwire integration ───────────────────────────────────────────────────────


def run_ripwire(bin_path: str, root: str, args: list[str], *, timeout: int = 30) -> str:
    """Run ripwire as subprocess. Returns stdout string. Raises RuntimeError on non-zero exit."""
    cmd = [bin_path, root] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"ripwire binary not found at '{bin_path}': {e}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ripwire timed out after {timeout}s") from e
    if result.returncode != 0:
        raise RuntimeError(f"ripwire exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def parse_routes_xml(xml_str: str) -> tuple[list[dict[str, str]], str, bool]:
    """Parse ripwire XML output. Returns (routes, confidence, over_ceiling)."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return ([], "low", False)

    confidence = root.get("confidence", "low")
    over_ceiling = root.get("over_ceiling", "0") == "1"

    routes = []
    for elem in root.iter("route"):
        method = elem.get("method", "")
        path = elem.get("path", "")
        from_sym = elem.get("from", "")
        to_sym = elem.get("to", "")
        routes.append(
            {
                "method": method.upper(),
                "path": path,
                "from": from_sym,
                "to": to_sym,
            }
        )

    return (routes, confidence, over_ceiling)


# ─── Generic (non-ripwire) tools ───────────────────────────────────────────────

ROUTE_QUERY = "HTTP API route calls and response types"
TOOL_BINARIES = {
    "ripwire": "ripwire",
    "codebase-memory": "codebase-memory-mcp",
    "graphify": "graphify",
    "repowise": "repowise",
    "aider": "aider",
}
HTTP_CALL_REGEX = r"""\.(get|post|put|patch|delete)\w*\(\s*f?["'`]/"""
SOURCE_SUFFIXES = {".rb", ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".kt", ".cs", ".php"}
SKIP_DIRS = {"node_modules", ".git", "vendor", "dist", "build", "target", "__pycache__", ".venv"}

_VERB_THEN_PATH = re.compile(r"""\b(GET|POST|PUT|PATCH|DELETE)\b[^\n/]{0,40}?["'`](/[^\s"'`?]*)""", re.IGNORECASE)
_CALL_STYLE = re.compile(r"""\.(get|post|put|patch|delete)\w*\(\s*f?["'`](/[^\s"'`?]*)""", re.IGNORECASE)
_TEMPLATE_VAR = re.compile(r"\$\{[^}]*\}|\{[^}]*\}")


def extract_routes_from_text(text: str) -> list[dict[str, str]]:
    """Heuristically extract (method, path) pairs from free text or source code."""
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for pattern in (_VERB_THEN_PATH, _CALL_STYLE):
        for method, path in pattern.findall(text):
            norm = _TEMPLATE_VAR.sub("{id}", path).rstrip("/") or "/"
            key = (method.upper(), norm)
            seen.setdefault(key, {"method": key[0], "path": norm, "from": "", "to": ""})
    return list(seen.values())


def scan_sources(root: str) -> str:
    """Concatenate consumer source files for the built-in text scan."""
    chunks: list[str] = []
    for path in Path(root).rglob("*"):
        if path.suffix in SOURCE_SUFFIXES and not SKIP_DIRS.intersection(path.parts):
            try:
                chunks.append(path.read_text(errors="ignore"))
            except OSError:
                continue
    return "\n".join(chunks)


def run_command(cmd: list[str], cwd: str, *, timeout: int = 120) -> str:
    """Run a tool command in cwd and return stdout; raise RuntimeError on failure."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    except FileNotFoundError as e:
        raise RuntimeError(f"'{cmd[0]}' not found: {e}") from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"'{cmd[0]}' timed out after {timeout}s") from e
    if result.returncode != 0:
        raise RuntimeError(f"'{cmd[0]}' exited {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def resolve_tool(tool: str, tool_cmd: str | None) -> str:
    """Resolve 'auto' to the first available tool; fall back to the built-in scan."""
    if tool != "auto":
        return tool
    if tool_cmd:
        return "custom"
    for name, binary in TOOL_BINARIES.items():
        if shutil.which(binary):
            return name
    return "grep"


def discover_routes(args: argparse.Namespace) -> list[dict[str, str]]:
    """Discover consumer routes using the selected tool."""
    tool = resolve_tool(args.tool, args.tool_cmd)
    root = args.consumer_root
    if args.tool_cmd:
        cmd = shlex.split(args.tool_cmd.replace("{root}", root).replace("{query}", ROUTE_QUERY))
        return extract_routes_from_text(run_command(cmd, root))
    if tool == "ripwire":
        xml_str = run_ripwire(args.ripwire, root, [f"--for={ROUTE_QUERY}"])
        return parse_routes_xml(xml_str)[0]
    if tool == "graphify":
        return extract_routes_from_text(run_command(["graphify", "query", ROUTE_QUERY], root))
    if tool == "aider":
        out = run_command(["aider", "--show-repo-map", "--map-tokens", "8192"], root)
        return extract_routes_from_text(out)
    if tool == "grep":
        return extract_routes_from_text(scan_sources(root))
    if tool == "repowise":
        out = run_command(["repowise", "ask", ROUTE_QUERY, "--path", root], root, timeout=300)
        return extract_routes_from_text(out)
    if tool == "codebase-memory":
        return extract_routes_from_text(_codebase_memory_search(root))
    raise RuntimeError(f"--tool {tool} has no built-in command; pass --tool-cmd")


def _codebase_memory_search(root: str) -> str:
    """Index root with codebase-memory-mcp (fast mode) and regex-search HTTP call sites."""
    binary = "codebase-memory-mcp"
    project = "pact-coverage-" + re.sub(r"\W+", "-", Path(root).resolve().name)
    run_command(
        [binary, "cli", "--quiet", "index_repository", "--repo-path", str(Path(root).resolve())]
        + ["--mode", "fast", "--name", project],
        root,
    )
    return run_command(
        [binary, "cli", "--quiet", "search_code", "--project", project]
        + ["--pattern", HTTP_CALL_REGEX, "--regex", "true", "--mode", "full"]
        + ["--limit", "500", "--result-limit", "500"],
        root,
    )


# ─── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover consumer routes via a code-intelligence tool and output them as JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--consumer-root",
        required=True,
        help="Consumer codebase root to scan",
    )
    parser.add_argument(
        "--ripwire",
        default="ripwire",
        help="Path to ripwire binary (default: ripwire)",
    )
    parser.add_argument(
        "--tool",
        choices=["auto", "ripwire", "graphify", "aider", "repowise", "codebase-memory", "grep"],
        default="ripwire",
        help="Code-intelligence tool used for discovery (default: ripwire)",
    )
    parser.add_argument(
        "--tool-cmd",
        help="Custom command (run in consumer root; {root} and {query} are substituted)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output path for JSON routes (- for stdout, default: -)",
    )
    args = parser.parse_args()

    try:
        routes = discover_routes(args)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    if not routes:
        print(
            f"WARNING: {args.tool} found no HTTP route calls in consumer codebase",
            file=sys.stderr,
        )
        sys.exit(1)

    output = json.dumps([{"method": r["method"], "path": r["path"]} for r in routes])

    if args.output == "-":
        print(output)
    else:
        Path(args.output).write_text(output)

    sys.exit(0)


if __name__ == "__main__":
    main()
