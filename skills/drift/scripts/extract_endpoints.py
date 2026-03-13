#!/usr/bin/env python3
"""
extract_endpoints.py — Extract endpoints and response codes from an OpenAPI spec.

In summary mode (default), prints a table of every operation with its response codes
and flags parameters that have no spec example (these will cause Drift to fail with
"Value for query parameter X is missing" unless you supply explicit values).

In scaffold mode (--scaffold), emits a ready-to-fill drift.yaml `operations:` block
with one stub per (operation, response_code) — pre-wired with correct auth patterns,
nil UUIDs for 404s, ignore.schema for 4xx, and FILL_IN markers for params without
spec examples.

Requires: PyYAML  (pip install pyyaml)

Usage:
  python3 extract_endpoints.py --spec openapi.yaml
  python3 extract_endpoints.py --spec openapi.yaml --scaffold > operations.yaml
  python3 extract_endpoints.py --spec openapi.yaml --scaffold --source my-oas
  python3 extract_endpoints.py --spec openapi.yaml --scaffold --only-missing drift.yaml
  python3 extract_endpoints.py --spec openapi.yaml --filter /orgs
  python3 extract_endpoints.py --spec openapi.yaml --json

Exit codes:
  0 — success
  1 — one or more params have no spec example (summary mode only; warns you)
  2 — error (could not parse spec)
"""

import argparse
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

NIL_UUID = "00000000-0000-0000-0000-000000000000"
EXAMPLE_UUID = "59d6d97e-3106-4ebb-b608-352fad9c5b34"

# ─── $ref resolution ───────────────────────────────────────────────────────────

def _resolve_ref(ref, root):
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return {}
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def resolve(obj, root):
    """Recursively resolve $refs in obj (local refs only)."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            return resolve(_resolve_ref(obj["$ref"], root), root)
        return {k: resolve(v, root) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(i, root) for i in obj]
    return obj


# ─── Parameter value extraction ────────────────────────────────────────────────

def _schema_example(schema):
    """Pull an example value out of a JSON Schema dict."""
    if not isinstance(schema, dict):
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    fmt = schema.get("format", "")
    typ = schema.get("type", "")
    if fmt == "uuid":
        return EXAMPLE_UUID
    if fmt in ("date-time", "date"):
        return "2024-01-04" if fmt == "date" else "2024-01-04T00:00:00.000Z"
    if typ == "integer":
        return 1
    if typ == "number":
        return 1.0
    if typ == "boolean":
        return "false"
    if typ == "array":
        inner = _schema_example(schema.get("items", {}))
        return inner  # return scalar; Drift accepts single value for array params
    return None


def get_param_example(param, root):
    """
    Return (value, has_example) for a parameter.
    has_example=True means the spec supplied an example we can use directly.
    has_example=False means we synthesised a value or have nothing.
    """
    param = resolve(param, root)
    if not isinstance(param, dict):
        return None, False

    # Explicit example at param level (highest priority)
    if "example" in param:
        return param["example"], True
    if "examples" in param and isinstance(param["examples"], dict):
        first = next(iter(param["examples"].values()), {})
        first = resolve(first, root)
        if "value" in first:
            return first["value"], True

    schema = resolve(param.get("schema", {}), root)
    val = _schema_example(schema)
    if val is not None:
        # Synthesised from schema — still usable but mark as inferred
        fmt = schema.get("format", "")
        return val, fmt == "uuid"  # UUIDs we're confident about; others are inferred

    return None, False


def get_404_path_value(param, root):
    """Return a value that should produce a 404 (non-existent but format-valid ID)."""
    param = resolve(param, root)
    schema = resolve(param.get("schema", {}), root)
    fmt = schema.get("format", "")
    typ = schema.get("type", "string")
    pattern = schema.get("pattern", "")

    if fmt == "uuid":
        return NIL_UUID
    if pattern:
        # Can't auto-generate — caller must fill in
        return f"FILL_IN  # must match pattern: {pattern}"
    if typ == "integer":
        return 999999
    return "nonexistent"


# ─── Spec loading ──────────────────────────────────────────────────────────────

def load_operations(spec_path, exclude_codes, path_filter=None):
    """
    Parse spec and return list of operation dicts.

    Each dict:
      operationId, path, method, response_codes (list), params (list of param dicts),
      has_request_body, request_body_required_fields
    """
    with open(spec_path) as f:
        raw = yaml.safe_load(f)

    ops = []
    for path, path_item in raw.get("paths", {}).items():
        if path_filter and not path.startswith(path_filter):
            continue
        if not isinstance(path_item, dict):
            continue
        if "$ref" in path_item:
            path_item = _resolve_ref(path_item["$ref"], raw)

        # Collect path-level parameters (shared across methods)
        path_level_params = [resolve(p, raw) for p in path_item.get("parameters", [])]

        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            # Response codes
            codes = []
            for code in operation.get("responses", {}).keys():
                code_str = str(code)
                if code_str in exclude_codes:
                    continue
                if re.match(r"^[24]\d\d$", code_str):
                    codes.append(code_str)
            codes.sort()

            # Parameters (path-level + operation-level, deduplicated by name)
            op_params = [resolve(p, raw) for p in operation.get("parameters", [])]
            all_params = {p.get("name"): p for p in path_level_params}
            all_params.update({p.get("name"): p for p in op_params})

            # Request body
            request_body = resolve(operation.get("requestBody", {}), raw)
            has_body = bool(request_body)
            required_fields = []
            if has_body:
                for ct, ct_obj in request_body.get("content", {}).items():
                    schema = resolve(ct_obj.get("schema", {}), raw)
                    required_fields = schema.get("required", [])
                    break

            ops.append({
                "operationId": operation.get("operationId") or f"{method}:{path}",
                "path": path,
                "method": method,
                "codes": codes,
                "params": list(all_params.values()),
                "has_body": has_body,
                "required_body_fields": required_fields,
                "tags": operation.get("tags", []),
            })

    return ops, raw


# ─── Summary output ────────────────────────────────────────────────────────────

def print_summary(ops, raw):
    needs_fill = False
    for op in ops:
        codes_str = ", ".join(op["codes"]) or "(none documented)"
        print(f"  {op['method'].upper():<7}  {op['path']}")
        if op["operationId"] != f"{op['method']}:{op['path']}":
            print(f"           id:     {op['operationId']}")
        print(f"           codes: {codes_str}")

        # Flag params without examples
        missing = []
        for p in op["params"]:
            val, has_ex = get_param_example(p, raw)
            if val is None:
                missing.append(f"{p.get('in','?')}.{p.get('name','?')}")
        if missing:
            print(f"           ⚠ no example: {', '.join(missing)}")
            needs_fill = True
        print()

    return needs_fill


# ─── Scaffold output ───────────────────────────────────────────────────────────

_STATUS_SUFFIX = {
    "200": "Success",
    "201": "Created",
    "204": "NoContent",
    "400": "BadRequest",
    "401": "Unauthorized",
    "403": "Forbidden",
    "404": "NotFound",
    "409": "Conflict",
    "422": "UnprocessableEntity",
}

def _op_name(op_id, code):
    suffix = _STATUS_SUFFIX.get(code, f"Status{code}")
    # Sanitise operationId (replace non-word chars)
    safe_id = re.sub(r"[^\w]", "_", op_id)
    return f"{safe_id}_{suffix}"


def _yaml_value(v):
    """Render a Python value as a compact YAML-safe scalar string."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    # Quote if needed
    if any(c in s for c in (": ", "{", "}", "[", "]", "#", "\\", "\n")):
        return f'"{s}"'
    if s in ("true", "false", "null", "~") or re.match(r"^\d", s):
        return f'"{s}"'
    return f'"{s}"'


def scaffold_op(op, code, raw, source):
    """Return a YAML string for one drift test case stub."""
    lines = []
    op_id = op["operationId"]
    name = _op_name(op_id, code)
    is_error = code.startswith("4")
    is_401 = code == "401"
    is_404 = code == "404"
    is_400 = code == "400"
    is_write = op["method"] in ("post", "put", "patch")
    is_delete = op["method"] == "delete"

    lines.append(f"  {name}:")
    lines.append(f"    target: {source}:{op_id}")

    # Infer tags
    tags = []
    if code.startswith("2"):
        tags += ["smoke", "read-only"] if op["method"] == "get" else ["write"]
        if is_delete:
            tags = ["destructive"]
    elif code == "401":
        tags = ["security"]
    elif code == "403":
        tags = ["security"]
    else:
        tags = ["regression"]
    if op.get("tags"):
        tags.append(op["tags"][0].lower().replace(" ", "-"))
    lines.append(f"    tags: [{', '.join(tags)}]")

    # Auth exclusion for 401
    if is_401:
        lines.append("    exclude:")
        lines.append("      - auth")

    # ignore.schema for 4xx
    if is_error:
        lines.append("    ignore:")
        lines.append("      schema: true")

    # Parameters
    path_params = [p for p in op["params"] if p.get("in") == "path"]
    query_params = [p for p in op["params"] if p.get("in") == "query"]
    header_params = [p for p in op["params"] if p.get("in") == "header"]

    has_params = path_params or query_params or header_params or is_401 or (is_error and True) or (is_write and op["has_body"])

    if has_params:
        lines.append("    parameters:")

        # Path params
        if path_params:
            lines.append("      path:")
            for p in path_params:
                pname = p.get("name", "id")
                if is_404:
                    val = get_404_path_value(p, raw)
                    comment = "  # non-existent ID"
                else:
                    val, has_ex = get_param_example(p, raw)
                    comment = "" if has_ex else "  # ⚠ no spec example — fill in"
                    if val is None:
                        val = "FILL_IN"
                lines.append(f"        {pname}: {_yaml_value(val)}{comment}")

        # Query params
        if query_params:
            lines.append("      query:")
            for p in query_params:
                pname = p.get("name", "param")
                val, has_ex = get_param_example(p, raw)
                comment = "" if has_ex else "  # ⚠ no spec example — fill in"
                if val is None:
                    val = "FILL_IN"
                lines.append(f"        {pname}: {_yaml_value(val)}{comment}")

        # Headers
        need_headers = header_params or is_401 or is_error
        if need_headers:
            lines.append("      headers:")
            for p in header_params:
                pname = p.get("name")
                val, _ = get_param_example(p, raw)
                if val is None:
                    val = "FILL_IN"
                lines.append(f"        {pname}: {_yaml_value(val)}")
            if is_401:
                lines.append('        authorization: "Bearer invalid-token"')
                lines.append('        Prefer: "code=401"')
            elif is_error:
                lines.append(f'        Prefer: "code={code}"')

        # Request body
        if is_write and op["has_body"]:
            if is_400:
                lines.append("      request:")
                lines.append("        body:  # intentionally missing required fields")
                # Include only one optional field to trigger validation error
                lines.append("          _placeholder: FILL_IN")
            elif not is_error:
                lines.append("      request:")
                lines.append("        body:")
                if op["required_body_fields"]:
                    for field in op["required_body_fields"][:5]:
                        lines.append(f"          {field}: FILL_IN  # required")
                else:
                    lines.append("          # FILL_IN — see spec for request body schema")

    # Expected
    lines.append("    expected:")
    lines.append("      response:")
    lines.append(f"        statusCode: {code}")

    return "\n".join(lines)


def scaffold_all(ops, raw, source, only_missing_coverage=None):
    """Emit full operations: block as YAML string."""
    out = ["operations:"]

    # Group by path for readable section headers
    current_path = None
    for op in ops:
        for code in op["codes"]:
            # Skip if already covered
            if only_missing_coverage:
                op_key = op["operationId"]
                covered = only_missing_coverage.get(op_key, set()) | \
                          only_missing_coverage.get(f"{op['method']}:{op['path']}", set())
                if code in covered:
                    continue

            if op["path"] != current_path:
                current_path = op["path"]
                dashes = "─" * max(0, 60 - len(current_path) - 5)
                out.append(f"\n  # ── {op['method'].upper()} {current_path} {dashes}")

            out.append("")
            out.append(scaffold_op(op, code, raw, source))

    return "\n".join(out)


# ─── Load existing test coverage (for --only-missing) ──────────────────────────

def load_existing_coverage(test_file):
    """Return dict: operationId -> set of covered status codes."""
    try:
        with open(test_file) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"WARNING: Could not read {test_file}: {e}", file=sys.stderr)
        return {}

    covered = defaultdict(set)
    for _name, op in (data or {}).get("operations", {}).items():
        if not isinstance(op, dict):
            continue
        target = op.get("target", "")
        if ":" not in target:
            continue
        _, op_key = target.split(":", 1)
        # Normalise method:path targets
        m = re.match(r"^(get|post|put|patch|delete|head|options|trace):(.+)$", op_key, re.I)
        if m:
            op_key = f"{m.group(1).lower()}:{m.group(2)}"
        try:
            code = str(op["expected"]["response"]["statusCode"])
            covered[op_key].add(code)
        except (KeyError, TypeError):
            pass
    return dict(covered)


# ─── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extract endpoints and response codes from an OpenAPI spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--spec", required=True, help="Path to OpenAPI spec")
    parser.add_argument("--scaffold", action="store_true",
                        help="Emit drift test case stubs instead of summary")
    parser.add_argument("--source", default="source-oas",
                        help="Drift source name to use in targets (default: source-oas)")
    parser.add_argument("--only-missing", metavar="DRIFT_YAML",
                        help="Only scaffold operations/codes not already in this test file")
    parser.add_argument("--filter", metavar="PATH_PREFIX",
                        help="Only include paths starting with this prefix")
    parser.add_argument("--exclude-codes", nargs="*", default=sorted(DEFAULT_EXCLUDE),
                        help="Response codes to skip")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    exclude_codes = set(str(c) for c in args.exclude_codes)

    try:
        ops, raw = load_operations(args.spec, exclude_codes, args.filter)
    except Exception as e:
        print(f"ERROR: Could not parse spec: {e}", file=sys.stderr)
        sys.exit(2)

    if not ops:
        print("No operations found. Check --spec path and --filter.", file=sys.stderr)
        sys.exit(2)

    # JSON mode
    if args.json:
        out = []
        for op in ops:
            param_info = []
            for p in op["params"]:
                val, has_ex = get_param_example(p, raw)
                param_info.append({
                    "name": p.get("name"),
                    "in": p.get("in"),
                    "required": p.get("required", False),
                    "example": val,
                    "has_spec_example": has_ex,
                })
            out.append({
                "operationId": op["operationId"],
                "method": op["method"].upper(),
                "path": op["path"],
                "response_codes": op["codes"],
                "parameters": param_info,
                "has_request_body": op["has_body"],
            })
        print(json.dumps(out, indent=2))
        return

    # Scaffold mode
    if args.scaffold:
        existing = {}
        if args.only_missing:
            existing = load_existing_coverage(args.only_missing)
        print(scaffold_all(ops, raw, args.source, existing or None))
        return

    # Summary mode
    print(f"Spec: {args.spec}")
    print(f"Operations: {len(ops)}  |  Excluding: {', '.join(sorted(exclude_codes))}")
    if args.filter:
        print(f"Filter: {args.filter}")
    print()

    needs_fill = print_summary(ops, raw)

    total_codes = sum(len(op["codes"]) for op in ops)
    print(f"Total: {len(ops)} operations, {total_codes} response codes to cover")

    if needs_fill:
        print()
        print("⚠  Some parameters have no spec example — you must supply explicit values")
        print("   in parameters.query/path or Drift will fail before sending the request.")
        sys.exit(1)


if __name__ == "__main__":
    main()
