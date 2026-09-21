#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml~=6.0",
# ]
# ///
"""
build_filtered_oas.py — CI tool: discover consumer routes via ripwire (Strategy 1).

Outputs a --consumer-routes JSON list for use with parse_pact_coverage.py.
For adaptive multi-strategy discovery, use the pact-coverage agent instead.

Usage:
  uv run scripts/build_filtered_oas.py --consumer-root ./consumer-src --output routes.json
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


def parse_routes_xml(xml_str: str) -> tuple[list[dict], str, bool]:
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
        routes.append({
            "method": method.upper(),
            "path": path,
            "from": from_sym,
            "to": to_sym,
        })

    return (routes, confidence, over_ceiling)


# ─── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover consumer routes via ripwire and output them as JSON.",
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
        "--output",
        default="-",
        help="Output path for JSON routes (- for stdout, default: -)",
    )
    args = parser.parse_args()

    # Strategy 1: run ripwire for HTTP API route calls and response types
    try:
        xml_str = run_ripwire(
            args.ripwire,
            args.consumer_root,
            ["--for=HTTP API route calls and response types"],
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    routes, _confidence, _over_ceiling = parse_routes_xml(xml_str)

    if not routes:
        print(
            "WARNING: ripwire found no HTTP route calls in consumer codebase",
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
