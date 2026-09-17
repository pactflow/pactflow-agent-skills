#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
parse_pact_coverage.py — Pact v2/v3/v4 interaction coverage checker against an OpenAPI spec.

Reports which path/method operations, status codes, required request body fields, and
required response body fields are tested vs. missing across one or more pact.json files.

Pact spec version detection (from metadata.pactSpecification.version):
  v4   — interactions carry a "type" field; body is {"content": {...}, ...}
  v3/v2 — all interactions are HTTP; body is inline JSON {"field": value, ...}

Usage:
  uv run parse_pact_coverage.py --spec openapi.yaml --pacts pacts/consumer-provider.json
  uv run parse_pact_coverage.py --spec openapi.yaml --pacts "pacts/*.json"
  uv run parse_pact_coverage.py --spec openapi.yaml --pacts "pacts/*.json" --json
  uv run parse_pact_coverage.py --spec openapi.yaml --pacts "pacts/*.json" --exclude-codes 500 501

  # Consumer-filtered: only report on HTTP operations the consumer actually calls.
  # Pass --consumer-routes to supply a pre-built JSON routes list.
  uv run parse_pact_coverage.py --spec openapi.yaml --pacts "pacts/*.json" \\
      --consumer-routes '[{"method":"GET","path":"/orders/{id}"}]'

Exit codes:
  0 — full coverage across all four dimensions
  1 — gaps found (at least one dimension has missing coverage)
  2 — error (spec or pact file could not be parsed, or consumer-filtering failed)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
DEFAULT_EXCLUDE = {"500", "501", "502", "503"}


# ─── OAS helpers ───────────────────────────────────────────────────────────────

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


def _get_schema_properties(schema: dict, root: dict) -> set:
    """All property names defined in a schema (top-level, resolves $ref/allOf/anyOf/oneOf)."""
    if not isinstance(schema, dict):
        return set()
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
        if not schema:
            return set()
    props: set = set()
    for kw in ("allOf", "anyOf", "oneOf"):
        for branch in schema.get(kw, []):
            props |= _get_schema_properties(branch, root)
    props |= set(schema.get("properties", {}).keys())
    return props


def _consumer_status_branches(consumer_root: str) -> set[str]:
    """Grep consumer files for explicit `status == N` / `status(N)` branches."""
    root_path = Path(consumer_root)
    files = (
        [root_path] if root_path.is_file()
        else [
            f for f in root_path.rglob("*")
            if f.is_file() and f.suffix in (".rb", ".ts", ".js", ".py", ".go", ".java", ".kt")
        ]
    )
    # Matches: resp.status == 404 / response.status == 404 / status == 404 / status(404)
    pattern = re.compile(r'\bstatus\b[\s=!<>]*[\s(]*(\d{3})\b')
    codes: set[str] = set()
    for fpath in files:
        try:
            for m in pattern.finditer(fpath.read_text(errors="replace")):
                codes.add(m.group(1))
        except Exception:
            pass
    return codes


def _extract_required_fields(schema: dict, root: dict) -> set:
    """
    Collect required field names from an OAS schema node (top-level only).

    Handles $ref, allOf (union), anyOf/oneOf (union — conservative).
    """
    if not isinstance(schema, dict):
        return set()

    # Resolve $ref first
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], root)
        if not schema:
            return set()

    fields: set = set()

    # allOf — merge required from all branches
    for branch in schema.get("allOf", []):
        fields |= _extract_required_fields(branch, root)

    # anyOf / oneOf — union across all branches (conservative)
    for keyword in ("anyOf", "oneOf"):
        for branch in schema.get(keyword, []):
            fields |= _extract_required_fields(branch, root)

    # Direct required list at this node level
    for field in schema.get("required", []):
        fields.add(str(field))

    return fields


def _get_json_schema_for_media_type(content: dict, root: dict) -> dict:
    """
    Given an OAS content block, find the application/json schema.

    Returns the resolved schema dict, or {} if not found.
    """
    if not isinstance(content, dict):
        return {}

    # Prefer exact match, then first key containing 'json'
    entry = content.get("application/json")
    if entry is None:
        for key in content:
            if "json" in key:
                entry = content[key]
                break

    if not isinstance(entry, dict):
        return {}

    schema = entry.get("schema", {})
    if not isinstance(schema, dict):
        return {}

    if "$ref" in schema:
        return _resolve_ref(schema["$ref"], root)
    return schema


# ─── Pact parsing ──────────────────────────────────────────────────────────────

def _body_fields(part: dict, *, v4: bool) -> set:
    """Extract top-level body field keys from a request or response part dict."""
    body = (part or {}).get("body") or {}
    if not isinstance(body, dict):
        return set()
    if v4:
        # v4: body = {"content": {field: value, ...}, "contentType": "..."}
        content = body.get("content")
        return set(content.keys()) if isinstance(content, dict) else set()
    # v3/v2: body IS the inline JSON object
    return set(body.keys())


def load_pact(path: str) -> dict:
    """Load and JSON-parse a pact file. Raises ValueError on bad JSON."""
    with open(path) as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in pact file '{path}': {e}") from e


def extract_pact_interactions(pact: dict) -> list:
    """
    Return a list of interaction dicts for HTTP interactions.

    Supports Pact spec v2, v3, and v4. Version is detected per-interaction:
    - Interactions with type="Synchronous/HTTP" are v4 (body wrapped in content).
    - Interactions with no type field are v3/v2 (body is inline JSON).
    - Interactions with any other type value are skipped (e.g. Asynchronous/Messages).
    """
    interactions = []
    for ix in pact.get("interactions", []):
        if not isinstance(ix, dict):
            continue
        ix_type = ix.get("type")
        if ix_type is not None and ix_type != "Synchronous/HTTP":
            continue  # skip non-HTTP typed interactions (v4 messages etc.)

        v4_body = ix_type == "Synchronous/HTTP"

        request = ix.get("request", {})
        response = ix.get("response", {})

        method = str(request.get("method", "")).upper()
        path = str(request.get("path", ""))
        status_raw = response.get("status", 0)
        try:
            status = int(status_raw)
        except (TypeError, ValueError):
            status = 0

        interactions.append({
            "description": ix.get("description", ""),
            "method": method,
            "path": path,
            "status": status,
            "req_body_fields": _body_fields(request, v4=v4_body),
            "resp_body_fields": _body_fields(response, v4=v4_body),
        })

    return interactions


# ─── OAS parsing ───────────────────────────────────────────────────────────────

def load_oas(path: str) -> dict:
    """Load an OAS spec (YAML or JSON). Raises ValueError on parse failure."""
    with open(path) as f:
        raw = f.read()
    try:
        result = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ValueError(f"Could not parse spec '{path}': {e}") from e
    if not isinstance(result, dict):
        raise ValueError("spec did not parse to a mapping")
    return result


def _filter_oas_to_routes(oas: dict, routes: list[dict]) -> dict:
    """Filter OAS to only the paths/methods listed in routes (no type enrichment)."""
    import copy
    filtered = copy.deepcopy(oas)
    oas_paths = oas.get("paths", {})
    filtered_paths: dict = {}
    for route in routes:
        method = route.get("method", "").lower()
        path = route.get("path", "")
        if path in oas_paths and method in oas_paths[path]:
            if path not in filtered_paths:
                filtered_paths[path] = {}
            filtered_paths[path][method] = oas_paths[path][method]
        else:
            print(
                f"WARNING: route {method.upper()} {path} did not match any OAS path/method — skipped",
                file=sys.stderr,
            )
    filtered["paths"] = filtered_paths
    return filtered


def extract_oas_operations(oas: dict, exclude_codes: set | None = None) -> dict:
    """
    Walk oas['paths'] and produce an operations dict keyed by 'method:path'.

    Only includes 2xx and 4xx status codes, excluding exclude_codes.
    """
    if exclude_codes is None:
        exclude_codes = DEFAULT_EXCLUDE

    operations = {}

    for path, path_item in oas.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        # Resolve path item $ref
        if "$ref" in path_item:
            path_item = _resolve_ref(path_item["$ref"], oas)
            if not path_item:
                continue

        for method, operation in path_item.items():
            if method not in HTTP_METHODS:
                continue
            if not isinstance(operation, dict):
                continue

            # Collect 2xx and 4xx response codes only
            status_codes: set = set()
            for code in operation.get("responses", {}).keys():
                code_str = str(code)
                if code_str in exclude_codes:
                    continue
                if re.match(r"^[24]\d\d$", code_str):
                    status_codes.add(code_str)

            # Request body required fields + all schema properties
            req_required_fields: set = set()
            req_schema_properties: set = set()
            request_body = operation.get("requestBody", {})
            if isinstance(request_body, dict):
                if "$ref" in request_body:
                    request_body = _resolve_ref(request_body["$ref"], oas)
                req_content = request_body.get("content", {})
                req_schema = _get_json_schema_for_media_type(req_content, oas)
                req_required_fields = _extract_required_fields(req_schema, oas)
                req_schema_properties = _get_schema_properties(req_schema, oas)

            # Response body required fields + all schema properties per status code
            resp_required_fields: dict = {}
            resp_schema_properties: dict = {}
            for code in status_codes:
                response_obj = operation.get("responses", {}).get(code, {})
                if not isinstance(response_obj, dict):
                    resp_required_fields[code] = set()
                    resp_schema_properties[code] = set()
                    continue
                if "$ref" in response_obj:
                    response_obj = _resolve_ref(response_obj["$ref"], oas)
                resp_content = response_obj.get("content", {})
                resp_schema = _get_json_schema_for_media_type(resp_content, oas)
                resp_required_fields[code] = _extract_required_fields(resp_schema, oas)
                resp_schema_properties[code] = _get_schema_properties(resp_schema, oas)

            op_key = f"{method}:{path}"
            operations[op_key] = {
                "path": path,
                "method": method,
                "status_codes": status_codes,
                "req_required_fields": req_required_fields,
                "req_schema_properties": req_schema_properties,
                "resp_required_fields": resp_required_fields,
                "resp_schema_properties": resp_schema_properties,
            }

    return operations


# ─── Path matching ─────────────────────────────────────────────────────────────

def oas_path_to_pattern(oas_path: str) -> re.Pattern:
    """Convert an OAS path template to a compiled regex anchored at both ends."""
    parts = re.split(r'(\{[^}]+\})', oas_path)
    regex = ""
    for part in parts:
        if part.startswith('{') and part.endswith('}'):
            regex += '[^/]+'
        else:
            regex += re.escape(part)
    return re.compile(f'^{regex}$')


def find_matching_operation(method: str, concrete_path: str, oas_operations: dict) -> str | None:
    """
    Find the OAS operation key matching this method + concrete path.

    1. Normalize method to lowercase.
    2. Try exact match first.
    3. Try regex match; prefer operation with fewer {param} segments.
    """
    method = method.lower()
    exact_key = f"{method}:{concrete_path}"
    if exact_key in oas_operations:
        return exact_key

    # Regex matching — find all candidates for this method
    candidates = []
    prefix = f"{method}:"
    for key in oas_operations:
        if not key.startswith(prefix):
            continue
        oas_path = key[len(prefix):]
        pattern = oas_path_to_pattern(oas_path)
        if pattern.match(concrete_path):
            param_count = oas_path.count("{")
            candidates.append((param_count, key))

    if not candidates:
        return None

    # Prefer the most specific match (fewest params)
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ─── Coverage computation ──────────────────────────────────────────────────────

def compute_coverage(
    oas_ops: dict,
    pact_interactions: list,
    exclude_codes: set,
    consumer_root: str | None = None,
) -> dict:
    """Compute coverage across all 4 dimensions."""
    # Group pact interactions by their matching OAS operation key
    matched: dict = defaultdict(list)  # op_key -> [interaction, ...]
    for ix in pact_interactions:
        key = find_matching_operation(ix["method"], ix["path"], oas_ops)
        if key:
            matched[key].append(ix)

    # Dimension 1: path/method coverage
    path_method_covered = sorted(k for k in oas_ops if k in matched)
    path_method_missing = sorted(k for k in oas_ops if k not in matched)

    # Dimension 2: status code coverage (per operation)
    status_codes: dict = {}
    for op_key, info in oas_ops.items():
        spec_codes = info["status_codes"]
        tested_codes = {str(ix["status"]) for ix in matched.get(op_key, [])}
        missing_codes = sorted(spec_codes - tested_codes)
        covered_codes = sorted(spec_codes & tested_codes)
        if missing_codes or covered_codes:
            status_codes[op_key] = {
                "path": info["path"], "method": info["method"],
                "covered": covered_codes, "missing": missing_codes,
            }

    # Dimension 3: request body required fields (per operation, only when spec has required fields)
    req_body_fields: dict = {}
    for op_key, info in oas_ops.items():
        req_required = info["req_required_fields"]
        if not req_required:
            continue
        tested_fields: set = set()
        for ix in matched.get(op_key, []):
            tested_fields |= ix["req_body_fields"]
        missing = sorted(req_required - tested_fields)
        covered = sorted(req_required & tested_fields)
        req_body_fields[op_key] = {
            "path": info["path"], "method": info["method"],
            "covered": covered, "missing": missing,
        }

    # Dimension 4: response body required fields (per op+status_code, only when spec has required fields)
    resp_body_fields: dict = {}
    for op_key, info in oas_ops.items():
        for status_code, resp_required in info["resp_required_fields"].items():
            if not resp_required:
                continue
            key = f"{op_key}:{status_code}"
            tested_fields = set()
            for ix in matched.get(op_key, []):
                if str(ix["status"]) == status_code:
                    tested_fields |= ix["resp_body_fields"]
            missing = sorted(resp_required - tested_fields)
            covered = sorted(resp_required & tested_fields)
            resp_body_fields[key] = {
                "path": info["path"], "method": info["method"], "status": status_code,
                "covered": covered, "missing": missing,
            }

    # Schema quality warnings — OAS schema has properties but no required[],
    # yet pact body contains fields. Surfaces silent N/A sections.
    schema_quality_warnings: list[dict] = []
    for op_key, info in oas_ops.items():
        req_props = info.get("req_schema_properties", set())
        req_required = info["req_required_fields"]
        if req_props and not req_required:
            pact_req = set()
            for ix in matched.get(op_key, []):
                pact_req |= ix["req_body_fields"]
            if pact_req:
                uncovered = sorted(req_props - pact_req)
                schema_quality_warnings.append({
                    "op_key": op_key, "dimension": "request",
                    "path": info["path"], "method": info["method"],
                    "schema_prop_count": len(req_props),
                    "pact_fields": sorted(pact_req),
                    "uncovered_props": uncovered,
                })

        for status_code, resp_required in info["resp_required_fields"].items():
            resp_props = info.get("resp_schema_properties", {}).get(status_code, set())
            if resp_props and not resp_required:
                pact_resp = set()
                for ix in matched.get(op_key, []):
                    if str(ix["status"]) == status_code:
                        pact_resp |= ix["resp_body_fields"]
                if pact_resp:
                    uncovered = sorted(resp_props - pact_resp)
                    schema_quality_warnings.append({
                        "op_key": op_key, "dimension": "response", "status": status_code,
                        "path": info["path"], "method": info["method"],
                        "schema_prop_count": len(resp_props),
                        "pact_fields": sorted(pact_resp),
                        "uncovered_props": uncovered,
                    })

    # Consumer code status branch analysis — grep consumer source for explicit
    # `status == N` checks and flag status codes handled in code but untested by pact.
    consumer_status_branches: dict = {}
    if consumer_root:
        explicit_codes = _consumer_status_branches(consumer_root)
        explicit_codes -= exclude_codes
        if explicit_codes:
            for op_key, ixs in matched.items():
                tested_codes = {str(ix["status"]) for ix in ixs}
                untested = sorted(explicit_codes - tested_codes)
                if untested:
                    info = oas_ops[op_key]
                    consumer_status_branches[op_key] = {
                        "path": info["path"], "method": info["method"],
                        "explicit_codes": sorted(explicit_codes),
                        "untested": untested,
                    }

    # has_gaps: true if any dimension has missing items
    has_gaps = bool(
        path_method_missing
        or any(v["missing"] for v in status_codes.values())
        or any(v["missing"] for v in req_body_fields.values())
        or any(v["missing"] for v in resp_body_fields.values())
    )

    return {
        "path_method": {"covered": path_method_covered, "missing": path_method_missing},
        "status_codes": status_codes,
        "req_body_fields": req_body_fields,
        "resp_body_fields": resp_body_fields,
        "schema_quality_warnings": schema_quality_warnings,
        "consumer_status_branches": consumer_status_branches,
        "has_gaps": has_gaps,
        "total_interactions": len(pact_interactions),
    }


# ─── Output ────────────────────────────────────────────────────────────────────

def _pct(covered: int, total: int) -> str:
    """Return a 'covered/total — X%' label."""
    if total == 0:
        return "0/0 — N/A"
    return f"{covered}/{total} — {covered * 100 // total}%"


def print_report(
    report: dict,
    spec_path: str,
    pact_files: list,
    exclude_codes: set,
    consumer_root: str | None = None,
) -> None:
    """Print a 4-section coverage report to stdout."""
    divider = "═" * 62

    total_interactions = report["total_interactions"]

    print(f"Spec:        {spec_path}")
    print(f"Pact files:  {', '.join(pact_files)} ({total_interactions} interactions)")
    print(f"Excluding:   {', '.join(sorted(exclude_codes))}")
    print()

    # Section 1 — path/method
    pm = report["path_method"]
    s1_covered = len(pm["covered"])
    s1_total = s1_covered + len(pm["missing"])
    print(divider)
    print(f"SECTION 1 — PATH / METHOD COVERAGE  [{_pct(s1_covered, s1_total)}]")
    print(divider)

    covered_items = [f"{k.split(':', 1)[0].upper()} {k.split(':', 1)[1]}" for k in pm["covered"]]
    missing_items = [f"{k.split(':', 1)[0].upper()} {k.split(':', 1)[1]}" for k in pm["missing"]]
    print(f"  COVERED     ({s1_covered}): {', '.join(covered_items) or '(none)'}")
    print(f"  NOT COVERED ({len(pm['missing'])}): {', '.join(missing_items) or '(none)'}")
    print()

    # Section 2 — status codes
    s2_covered = sum(len(v["covered"]) for v in report["status_codes"].values())
    s2_total = sum(len(v["covered"]) + len(v["missing"]) for v in report["status_codes"].values())
    print(divider)
    print(f"SECTION 2 — STATUS CODE COVERAGE  [{_pct(s2_covered, s2_total)}]")
    print(divider)
    for op_key, info in report["status_codes"].items():
        method = info["method"].upper()
        path = info["path"]
        if op_key in pm["missing"]:
            print(f"  {method} {path} — no interactions (see Section 1)")
        else:
            op_c = len(info["covered"])
            op_t = op_c + len(info["missing"])
            print(f"  {method} {path}  [{_pct(op_c, op_t)}]")
            print(f"    Covered:  {', '.join(info['covered']) or '(none)'}")
            print(f"    Missing:  {', '.join(info['missing']) or '(none)'}")
    print()

    # Build schema-quality warning index for quick lookup in Sections 3 & 4
    sqw_req: dict = {}   # op_key -> warning
    sqw_resp: dict = {}  # "op_key:status" -> warning
    for w in report.get("schema_quality_warnings", []):
        if w["dimension"] == "request":
            sqw_req[w["op_key"]] = w
        else:
            sqw_resp[f"{w['op_key']}:{w['status']}"] = w

    # Section 3 — request body required fields
    s3_covered = sum(len(v["covered"]) for v in report["req_body_fields"].values())
    s3_total = sum(len(v["covered"]) + len(v["missing"]) for v in report["req_body_fields"].values())
    print(divider)
    print(f"SECTION 3 — REQUEST BODY REQUIRED FIELDS  [{_pct(s3_covered, s3_total)}]")
    print(divider)
    for op_key, info in report["req_body_fields"].items():
        method = info["method"].upper()
        path = info["path"]
        if op_key in pm["missing"]:
            print(f"  {method} {path} — no interactions (see Section 1)")
        else:
            op_c = len(info["covered"])
            op_t = op_c + len(info["missing"])
            print(f"  {method} {path}  [{_pct(op_c, op_t)}]")
            print(f"    Covered:  {', '.join(info['covered']) or '(none)'}")
            print(f"    Missing:  {', '.join(info['missing']) or '(none)'}")
    if s3_total == 0:
        # N/A — explain if schema has properties but no required[]
        for w in sqw_req.values():
            if w["op_key"] not in pm["missing"]:
                method = w["method"].upper()
                path = w["path"]
                pact_fields_str = ", ".join(w["pact_fields"][:5])
                if len(w["pact_fields"]) > 5:
                    pact_fields_str += f", +{len(w['pact_fields']) - 5} more"
                uncov = w["uncovered_props"]
                uncov_str = (", ".join(uncov[:5]) + (f", +{len(uncov)-5} more" if len(uncov) > 5 else "")) if uncov else "(none)"
                print(f"  ⚠ {method} {path}: OAS requestBody has {w['schema_prop_count']} properties but no required[]")
                print(f"    Pact sends:  {pact_fields_str or '(none)'}")
                print(f"    Not in pact: {uncov_str}")
                print(f"    → Add required: to the OAS requestBody schema to enable field coverage analysis")
    print()

    # Section 4 — response body required fields
    s4_covered = sum(len(v["covered"]) for v in report["resp_body_fields"].values())
    s4_total = sum(len(v["covered"]) + len(v["missing"]) for v in report["resp_body_fields"].values())
    print(divider)
    print(f"SECTION 4 — RESPONSE BODY REQUIRED FIELDS  [{_pct(s4_covered, s4_total)}]")
    print(divider)
    for key, info in report["resp_body_fields"].items():
        method = info["method"].upper()
        path = info["path"]
        status = info["status"]
        op_c = len(info["covered"])
        op_t = op_c + len(info["missing"])
        print(f"  {method} {path} → {status}  [{_pct(op_c, op_t)}]")
        print(f"    Covered:  {', '.join(info['covered']) or '(none)'}")
        print(f"    Missing:  {', '.join(info['missing']) or '(none)'}")
    if s4_total == 0:
        for w in sqw_resp.values():
            op_key = w["op_key"]
            status = w["status"]
            if op_key not in pm["missing"]:
                method = w["method"].upper()
                path = w["path"]
                pact_fields_str = ", ".join(w["pact_fields"][:5])
                if len(w["pact_fields"]) > 5:
                    pact_fields_str += f", +{len(w['pact_fields']) - 5} more"
                uncov = w["uncovered_props"]
                uncov_str = (", ".join(uncov[:5]) + (f", +{len(uncov)-5} more" if len(uncov) > 5 else "")) if uncov else "(none)"
                print(f"  ⚠ {method} {path} → {status}: OAS response has {w['schema_prop_count']} properties but no required[]")
                print(f"    Pact returns: {pact_fields_str or '(none)'}")
                print(f"    Not in pact:  {uncov_str}")
                print(f"    → Add required: to the OAS response schema to enable field coverage analysis")
    print()

    # Section 5 — consumer code status branch analysis (only when consumer_root used)
    consumer_branches = report.get("consumer_status_branches", {})
    if consumer_root and consumer_branches:
        print(divider)
        print("SECTION 5 — CONSUMER CODE STATUS BRANCHES")
        print(divider)
        for op_key, info in consumer_branches.items():
            method = info["method"].upper()
            path = info["path"]
            untested = ", ".join(info["untested"])
            explicit = ", ".join(info["explicit_codes"])
            print(f"  {method} {path}")
            print(f"    Consumer branches on: {explicit}")
            print(f"    Not tested by pact:   {untested}")
            print(f"    → Add pact interactions for status {untested} or verify via provider state")
        print()

    # Summary
    overall_covered = s1_covered + s2_covered + s3_covered + s4_covered
    overall_total = s1_total + s2_total + s3_total + s4_total

    print(divider)
    if report["has_gaps"]:
        gap_count = (
            len(pm["missing"])
            + sum(1 for v in report["status_codes"].values() if v["missing"])
            + sum(1 for v in report["req_body_fields"].values() if v["missing"])
            + sum(1 for v in report["resp_body_fields"].values() if v["missing"])
        )
        print(f"SUMMARY: {gap_count} gap(s) found. Exit code 1.")
    else:
        print("✓  All 4 dimensions fully covered. Exit code 0.")
    print()
    print(f"  Overall coverage:      {_pct(overall_covered, overall_total)}")
    print(f"  Paths/methods:         {_pct(s1_covered, s1_total)}")
    print(f"  Status codes:          {_pct(s2_covered, s2_total)}")
    print(f"  Req body fields:       {_pct(s3_covered, s3_total)}")
    print(f"  Resp body fields:      {_pct(s4_covered, s4_total)}")
    print(divider)


# ─── Consumer filtering ────────────────────────────────────────────────────────

def _build_consumer_filtered_oas(
    oas: dict,
    *,
    consumer_root: str | None = None,
    kg: str | None = None,
    consumer_routes: str | None = None,
    ripwire: str = "ripwire",
    http_client: str | None = None,
) -> dict | None:
    """Filter OAS to consumer-routes only. Returns None when no valid routes given."""
    if not consumer_routes:
        return None
    try:
        routes = json.loads(consumer_routes)
    except json.JSONDecodeError:
        return None
    if not routes:
        return None
    return _filter_oas_to_routes(oas, routes)


# ─── Entry point ───────────────────────────────────────────────────────────────

def fetch_pacts_from_broker(
    consumer: str,
    broker_url: str,
    broker_token: str | None,
    pact_out_dir: str,
) -> list[str]:
    """Download the latest published pacts for a consumer from a pact broker.

    Tries pact-broker CLI first, then falls back to direct HTTP HAL navigation.
    Returns paths of written pact files; prints WARNING and returns [] on failure.
    """
    broker_url = broker_url.rstrip("/")
    os.makedirs(pact_out_dir, exist_ok=True)

    # Strategy 1: pact-broker CLI
    if shutil.which("pact-broker"):
        cmd = [
            "pact-broker", "download-pacts",
            "--consumer", consumer,
            "--output-dir", pact_out_dir,
            "--broker-base-url", broker_url,
        ]
        if broker_token:
            cmd += ["--broker-token", broker_token]
        try:
            subprocess.run(cmd, check=True, timeout=60)
            files = glob.glob(os.path.join(pact_out_dir, "*.json"))
            if files:
                return files
        except Exception as e:
            print(f"WARNING: pact-broker CLI failed: {e}", file=sys.stderr)

    # Strategy 2: direct HTTP via urllib (HAL navigation)
    headers: dict[str, str] = {"Accept": "application/hal+json"}
    if broker_token:
        headers["Authorization"] = f"Bearer {broker_token}"

    def _get_json(url: str) -> dict:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    try:
        pacticipant = _get_json(f"{broker_url}/pacticipants/{consumer}")
        links = pacticipant.get("_links", {})
        pact_version_links = (
            links.get("pb:pact-versions")
            or links.get("pb:latest-pact-versions")
            or []
        )
        if isinstance(pact_version_links, dict):
            pact_version_links = [pact_version_links]

        written: list[str] = []
        for link in pact_version_links:
            href = link.get("href", "")
            if not href:
                continue
            try:
                pact_data = _get_json(href)
                provider = (pact_data.get("provider") or {}).get("name", "unknown-provider")
                out_path = os.path.join(pact_out_dir, f"{consumer}-{provider}-latest.json")
                Path(out_path).write_text(json.dumps(pact_data, indent=2))
                written.append(out_path)
            except Exception as e:
                print(f"WARNING: could not fetch pact from {href}: {e}", file=sys.stderr)
        return written

    except urllib.error.HTTPError as e:
        print(f"WARNING: broker HTTP error {e.code} for consumer '{consumer}': {e}", file=sys.stderr)
    except Exception as e:
        print(f"WARNING: broker fetch failed: {e}", file=sys.stderr)

    return []


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check Pact interaction coverage against an OpenAPI spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--spec", required=True, help="Path to OpenAPI spec (YAML or JSON)")
    parser.add_argument(
        "--pacts", nargs="*", default=["pacts/*.json"],
        help="Pact JSON files or glob patterns (default: pacts/*.json).",
    )
    parser.add_argument(
        "--exclude-codes", nargs="*", default=sorted(DEFAULT_EXCLUDE),
        help="Status codes to exclude from coverage",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Consumer-filtering flags (optional)
    parser.add_argument(
        "--consumer-routes", metavar="JSON",
        help='Pre-built JSON route list, e.g. \'[{"method":"GET","path":"/orders/{id}"}]\'. '
             "Filters the OAS to only the listed routes before computing coverage.",
    )

    # Broker fetch flags (optional; env vars PACT_BROKER_BASE_URL / PACT_BROKER_TOKEN / PACT_CONSUMER)
    parser.add_argument("--consumer", metavar="NAME",
        help="Consumer name for pact broker fetch (env: PACT_CONSUMER)")
    parser.add_argument("--broker-url", metavar="URL",
        help="Pact broker base URL (env: PACT_BROKER_BASE_URL)")
    parser.add_argument("--broker-token", metavar="TOKEN",
        help="Pact broker bearer token (env: PACT_BROKER_TOKEN)")
    parser.add_argument("--pact-out-dir", metavar="DIR", default="pacts",
        help="Directory to write fetched pact files (default: pacts/)")

    args = parser.parse_args()

    # Resolve broker config from flags or env vars
    broker_url   = args.broker_url   or os.environ.get("PACT_BROKER_BASE_URL")
    broker_token = args.broker_token or os.environ.get("PACT_BROKER_TOKEN")
    consumer     = args.consumer     or os.environ.get("PACT_CONSUMER")

    # Expand globs
    pact_files: list[str] = []
    for pattern in args.pacts:
        matches = glob.glob(pattern)
        pact_files.extend(matches if matches else ([pattern] if os.path.exists(pattern) else []))

    # If no local pact files found, try fetching from broker
    if not pact_files and consumer and broker_url:
        print(
            f"INFO: No pact files found at given patterns — fetching from broker for consumer '{consumer}'...",
            file=sys.stderr,
        )
        pact_files = fetch_pacts_from_broker(consumer, broker_url, broker_token, args.pact_out_dir)
        if pact_files:
            print(f"INFO: Fetched {len(pact_files)} pact file(s) from broker.", file=sys.stderr)

    if not pact_files:
        print(
            "ERROR: No pact files found.\n"
            "  • Run consumer tests first, then re-run this script with --pacts <output>/*.json\n"
            "  • Fetch from broker: set PACT_BROKER_BASE_URL + PACT_BROKER_TOKEN + PACT_CONSUMER\n"
            "  • Or specify files directly: --pacts path/to/consumer-provider.json",
            file=sys.stderr,
        )
        sys.exit(2)

    exclude_codes = set(str(c) for c in args.exclude_codes)

    try:
        oas = load_oas(args.spec)
    except Exception as e:
        print(f"ERROR: Could not parse spec '{args.spec}': {e}", file=sys.stderr)
        sys.exit(2)

    if args.consumer_routes:
        try:
            routes = json.loads(args.consumer_routes)
        except json.JSONDecodeError as e:
            print(f"ERROR: --consumer-routes is not valid JSON: {e}", file=sys.stderr)
            sys.exit(2)
        oas = _filter_oas_to_routes(oas, routes)

    try:
        oas_ops = extract_oas_operations(oas, exclude_codes)
    except Exception as e:
        print(f"ERROR: Could not parse spec '{args.spec}': {e}", file=sys.stderr)
        sys.exit(2)
    if not oas_ops:
        print("ERROR: No operations found in spec.", file=sys.stderr)
        sys.exit(2)

    all_interactions = []
    for pact_path in pact_files:
        try:
            pact = load_pact(pact_path)
            all_interactions.extend(extract_pact_interactions(pact))
        except Exception as e:
            print(f"ERROR: Could not parse pact '{pact_path}': {e}", file=sys.stderr)
            sys.exit(2)

    report = compute_coverage(oas_ops, all_interactions, exclude_codes)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args.spec, pact_files, exclude_codes)

    sys.exit(1 if report["has_gaps"] else 0)


if __name__ == "__main__":
    main()
