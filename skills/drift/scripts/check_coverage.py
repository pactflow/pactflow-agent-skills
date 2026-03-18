#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
check_coverage.py — Drift test coverage checker.

Reads an OpenAPI spec and one or more Drift test YAML files, then reports which
operations and response codes are missing test coverage.

Usage:
  python3 check_coverage.py --spec openapi.yaml --test-files drift.yaml
  python3 check_coverage.py --spec openapi.yaml --test-files "tests/*.yaml"
  python3 check_coverage.py --spec openapi.yaml --test-files drift.yaml --json
  python3 check_coverage.py --spec openapi.yaml --test-files drift.yaml --exclude-codes 500 501

Exit codes:
  0 — full coverage (all operations + response codes have at least one test)
  1 — gaps found (missing operations or response codes)
  2 — error (could not parse spec or test files)
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
DEFAULT_EXCLUDE = {"500", "501", "502", "503"}


def _resolve_ref(ref: str, root: dict) -> dict:
    """Resolve a local JSON Pointer $ref (e.g. '#/components/schemas/Foo')."""
    if not ref.startswith("#/"):
        return {}  # external refs not supported — return empty
    parts = ref[2:].split("/")
    node = root
    for part in parts:
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _resolve_path_item(path_item: dict, root: dict) -> dict:
    """Resolve a top-level $ref in a path item object."""
    if "$ref" in path_item:
        return _resolve_ref(path_item["$ref"], root)
    return path_item


def get_spec_operations(spec_path: str, exclude_codes: set) -> dict:
    """
    Parse an OpenAPI spec and return a dict of operation descriptors.

    Returns:
        {
          "<operationId or method:path>": {
            "path": str,
            "method": str,
            "codes": set[str],        # 2xx + 4xx response codes, excluding exclude_codes
            "synthetic_key": str,     # "method:path" always
            "has_operation_id": bool,
          }
        }
    """
    with open(spec_path) as f:
        raw = yaml.safe_load(f)

    operations = {}

    for path, path_item in raw.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        path_item = _resolve_path_item(path_item, raw)

        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            # Collect 2xx and 4xx response codes only
            codes = set()
            for code in operation.get("responses", {}).keys():
                code_str = str(code)
                if code_str in exclude_codes:
                    continue
                if re.match(r"^[24]\d\d$", code_str):
                    codes.add(code_str)

            operation_id = operation.get("operationId")
            synthetic_key = f"{method}:{path}"
            primary_key = operation_id if operation_id else synthetic_key

            operations[primary_key] = {
                "path": path,
                "method": method,
                "codes": codes,
                "synthetic_key": synthetic_key,
                "has_operation_id": bool(operation_id),
            }

    return operations


# ─── Test file parsing ──────────────────────────────────────────────────────────

def _parse_target(target: str):
    """
    Parse a Drift target string into (source, operation_key).

    Formats:
      source:operationId
      source:get:/products/{id}
    """
    if not target or ":" not in target:
        return None, None

    source, rest = target.split(":", 1)

    # method:path format?
    m = re.match(r"^(get|post|put|patch|delete|head|options|trace):(.+)$", rest, re.IGNORECASE)
    if m:
        return source, f"{m.group(1).lower()}:{m.group(2)}"

    return source, rest  # operationId format


def get_test_coverage(test_files: list) -> dict:
    """
    Parse Drift test YAML files and return what's covered.

    Returns:
        { "<operationId or method:path>": set("<status_code>", ...) }
    """
    covered = defaultdict(set)

    for test_file in test_files:
        try:
            with open(test_file) as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"  Warning: could not parse {test_file}: {e}", file=sys.stderr)
            continue

        if not isinstance(data, dict):
            continue

        for _op_name, op in data.get("operations", {}).items():
            if not isinstance(op, dict):
                continue

            _source, op_key = _parse_target(op.get("target", ""))
            if not op_key:
                continue

            status = None
            try:
                status = op["expected"]["response"]["statusCode"]
            except (KeyError, TypeError):
                pass

            if status is not None:
                covered[op_key].add(str(status))

    return dict(covered)


# ─── Comparison ────────────────────────────────────────────────────────────────

def compare(spec_ops: dict, test_coverage: dict) -> dict:
    """Diff spec operations against test coverage and return a structured report."""
    missing_ops = []
    partial_ops = []
    full_ops = []
    total_codes = 0
    covered_codes = 0

    for op_key, info in spec_ops.items():
        spec_codes = info["codes"]
        total_codes += len(spec_codes)

        # Match by operationId first, fall back to method:path
        test_codes = set()
        if op_key in test_coverage:
            test_codes = test_coverage[op_key]
        elif info["synthetic_key"] in test_coverage:
            test_codes = test_coverage[info["synthetic_key"]]

        missing = sorted(spec_codes - test_codes)
        tested = sorted(spec_codes & test_codes)
        covered_codes += len(tested)

        entry = {
            "operation": op_key,
            "path": info["path"],
            "method": info["method"].upper(),
            "spec_codes": sorted(spec_codes),
            "tested_codes": tested,
            "missing_codes": missing,
        }

        if not test_codes and spec_codes:
            missing_ops.append(entry)
        elif missing:
            partial_ops.append(entry)
        else:
            full_ops.append(entry)

    return {
        "total_operations": len(spec_ops),
        "covered_operations": len(partial_ops) + len(full_ops),
        "total_codes": total_codes,
        "covered_codes": covered_codes,
        "missing_operations": sorted(missing_ops, key=lambda x: (x["path"], x["method"])),
        "partial_operations": sorted(partial_ops, key=lambda x: (x["path"], x["method"])),
        "fully_covered": sorted(full_ops, key=lambda x: (x["path"], x["method"])),
    }


# ─── Output ────────────────────────────────────────────────────────────────────

def print_report(report: dict, spec_path: str, test_files: list, exclude_codes: set):
    total_ops = report["total_operations"]
    covered_ops = report["covered_operations"]
    total_codes = report["total_codes"]
    covered_codes = report["covered_codes"]
    op_pct = (covered_ops / total_ops * 100) if total_ops else 0
    code_pct = (covered_codes / total_codes * 100) if total_codes else 0

    print(f"Spec:        {spec_path}")
    print(f"Test files:  {', '.join(test_files)}")
    print(f"Excluding:   {', '.join(sorted(exclude_codes))}")
    print()
    print("=" * 62)
    print("COVERAGE SUMMARY")
    print("=" * 62)
    print(f"Operations:     {covered_ops}/{total_ops}  ({op_pct:.0f}%)")
    print(f"Response codes: {covered_codes}/{total_codes}  ({code_pct:.0f}%)")
    print()

    if report["missing_operations"]:
        print("─" * 62)
        print(f"UNTESTED OPERATIONS  ({len(report['missing_operations'])})")
        print("─" * 62)
        for op in report["missing_operations"]:
            codes = ", ".join(op["spec_codes"]) or "(none documented)"
            print(f"  {op['method']:<7}  {op['path']}")
            if op["operation"] != f"{op['method'].lower()}:{op['path']}":
                print(f"           id:     {op['operation']}")
            print(f"           needs:  {codes}")
            print()

    if report["partial_operations"]:
        print("─" * 62)
        print(f"PARTIAL COVERAGE  ({len(report['partial_operations'])})")
        print("─" * 62)
        for op in report["partial_operations"]:
            print(f"  {op['method']:<7}  {op['path']}")
            if op["operation"] != f"{op['method'].lower()}:{op['path']}":
                print(f"           id:      {op['operation']}")
            print(f"           tested:  {', '.join(op['tested_codes'])}")
            print(f"           missing: {', '.join(op['missing_codes'])}")
            print()

    if not report["missing_operations"] and not report["partial_operations"]:
        print("✓  All operations and response codes are covered.")
        print("=" * 62)


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Check Drift test coverage against an OpenAPI spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--spec", required=True, help="Path to OpenAPI spec (YAML or JSON)")
    parser.add_argument(
        "--test-files", nargs="+", required=True,
        help="Drift test YAML files or glob patterns"
    )
    parser.add_argument(
        "--exclude-codes", nargs="*", default=sorted(DEFAULT_EXCLUDE),
        help=f"Response codes to skip (default: {' '.join(sorted(DEFAULT_EXCLUDE))})"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of text")
    args = parser.parse_args()

    # Expand globs
    test_files = []
    for pattern in args.test_files:
        matches = glob.glob(pattern)
        test_files.extend(matches if matches else ([pattern] if os.path.exists(pattern) else []))

    if not test_files:
        print("ERROR: No test files found.", file=sys.stderr)
        sys.exit(2)

    exclude_codes = set(str(c) for c in args.exclude_codes)

    try:
        spec_ops = get_spec_operations(args.spec, exclude_codes)
    except Exception as e:
        print(f"ERROR: Could not parse spec '{args.spec}': {e}", file=sys.stderr)
        sys.exit(2)

    if not spec_ops:
        print("ERROR: No operations found in spec. Check the spec path.", file=sys.stderr)
        sys.exit(2)

    test_coverage = get_test_coverage(test_files)
    report = compare(spec_ops, test_coverage)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args.spec, test_files, exclude_codes)

    has_gaps = report["missing_operations"] or report["partial_operations"]
    sys.exit(1 if has_gaps else 0)


if __name__ == "__main__":
    main()
