#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
build_filtered_oas.py — Filter an OpenAPI spec to only what a consumer codebase uses.

Uses ripwire knowledge graph output to identify which endpoints a consumer calls
and which response fields its types declare, then narrows the OAS accordingly.
The filtered spec is the correct input for parse_pact_coverage.py.

Usage:
  # Generate KG first (iterative until confidence=high):
  ripwire ./consumer-src --for="HTTP API route calls" > kg.xml

  # Build filtered OAS:
  uv run build_filtered_oas.py --spec openapi.yaml --kg kg.xml --output filtered.yaml

  # Let the script drive ripwire itself (iterative loop built-in):
  uv run build_filtered_oas.py --spec openapi.yaml --consumer-root ./consumer-src --output filtered.yaml

  # Fallback: supply routes manually as JSON (for unsupported HTTP clients):
  #   Read the consumer source, identify which endpoints it calls, then supply them:
  uv run build_filtered_oas.py --spec openapi.yaml --routes '[{"method":"GET","path":"/orders/{id}"}]' --output filtered.yaml

Exit codes:
  0 — filtered OAS written, all routes resolved with high confidence
  1 — filtered OAS written, some routes fell back to Tier 4 (OAS required[] used as-is)
  2 — error (spec unreadable, no routes found via any source)
"""

from __future__ import annotations

import argparse
import copy
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

RIPWIRE_TASK = "HTTP API route calls and response types"
RESPONSE_TYPE_TASK = "HTTP response body deserialization and typed object construction"
MAX_ITER = 3
STRUCTURAL_THRESHOLD = 0.8
STRIP_SUFFIXES = ["Response", "Dto", "Model", "View", "Entity", "Resource", "Payload", "Data", "Result"]
STRIP_PREFIXES = ["I", "T"]
SKIP_TYPE_NAMES = {
    "Response", "Promise", "Error", "Exception", "String", "Int", "Bool",
    "Object", "Any", "Void", "None", "Null", "Optional", "Array", "List",
    "Map", "Dict", "Set", "Type", "Function", "Http", "Axios", "Fetch",
    "Request", "Result", "Future",
}

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


# ─── OAS loading ──────────────────────────────────────────────────────────────

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


def parse_body_xml(xml_str: str) -> str:
    """Extract function body text from --expand XML output."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return ""

    parts = []
    for elem in root.iter("body"):
        if elem.text:
            parts.append(elem.text)
    return "\n".join(parts)


def parse_type_fields_xml(xml_str: str, type_name: str) -> tuple[set[str], set[str]]:
    """Extract field names from ripwire output for a given type name.

    Returns (required_fields, optional_fields).
    Optional means: TypeScript `field?: T` or Python `field: T = default`.
    Only required_fields should drive the coverage denominator.
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return (set(), set())

    valid_types = {"cls", "iface", "struct", "type"}
    required: set[str] = set()
    optional: set[str] = set()

    for elem in root.iter("s"):
        if elem.get("n") != type_name:
            continue
        if elem.get("t") not in valid_types:
            continue

        # <prop n=...> children — may carry optional="1"
        for prop in elem:
            if prop.tag == "prop" and prop.get("n"):
                name = prop.get("n")
                if prop.get("optional") in ("1", "true", "yes"):
                    optional.add(name)
                else:
                    required.add(name)

        # <props> text (space-separated names, no optionality info → treat as required)
        for props_elem in elem:
            if props_elem.tag == "props" and props_elem.text:
                for name in props_elem.text.split():
                    if name:
                        required.add(name)

        # <body> text: parse field declarations
        for body_elem in elem:
            if body_elem.tag != "body" or not body_elem.text:
                continue
            body = body_elem.text
            # TypeScript: `  fieldName?: Type` → optional, `  fieldName: Type` → required
            for m in re.finditer(r'^\s*(\w+)(\??)\s*:', body, re.MULTILINE):
                name, q = m.group(1), m.group(2)
                if q:
                    optional.add(name)
                else:
                    # Python default values mark optional: `field: T = default`
                    line = body.splitlines()[body[:m.start()].count('\n')]
                    if '=' in line.split(':', 1)[-1]:
                        optional.add(name)
                    else:
                        required.add(name)

    # A field can only be in one set — optional wins if conflict
    required -= optional
    return (required, optional)


def extract_return_type(body: str) -> str | None:
    """Extract a return type name from a function body string."""
    patterns = [
        r':\s*Promise<([A-Z][A-Za-z0-9_]*)>',          # TS: ): Promise<Order>
        r'Promise<([A-Z][A-Za-z0-9_]*)>',               # TS: Promise<Order>
        r'->\s*Optional\[([A-Z][A-Za-z0-9_]*)\]',       # Py: -> Optional[Order]
        r'->\s*([A-Z][A-Za-z0-9_]*)',                    # Py/TS: -> Order
        r'const\s+\w+\s*:\s*([A-Z][A-Za-z0-9_]*)\s*=', # TS: const o: Order =
        r'as\s+([A-Z][A-Za-z0-9_]*)',                    # TS: resp.data as Order
        r':\s*([A-Z][A-Za-z0-9_]*)\s*=\s*await',        # TS: order: Order = await
        r'Response<([A-Z][A-Za-z0-9_]*)>',              # Java/Kotlin
        r'Call<([A-Z][A-Za-z0-9_]*)>',
    ]
    for pattern in patterns:
        m = re.search(pattern, body)
        if m:
            name = m.group(1)
            if name in SKIP_TYPE_NAMES or len(name) < 2:
                continue
            return name
    return None


def normalise_type_name(name: str) -> str:
    """Normalise a type name for fuzzy schema matching."""
    # Step 1: strip one suffix (longest match first, remainder >= 1 char)
    for suffix in sorted(STRIP_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix) and len(name) - len(suffix) >= 1:
            name = name[: -len(suffix)]
            break

    # Step 2: strip one prefix (only if next char is uppercase)
    for prefix in STRIP_PREFIXES:
        if (
            name.startswith(prefix)
            and len(name) > len(prefix)
            and name[len(prefix)].isupper()
        ):
            name = name[len(prefix):]
            break

    # Step 3: snake_case to CamelCase
    if "_" in name:
        name = "".join(part.capitalize() for part in name.split("_"))

    return name


def get_schema_properties(schema_name: str, oas: dict) -> set[str]:
    """Return the properties key names for an OAS component schema. Resolve $ref if needed (one level)."""
    schemas = oas.get("components", {}).get("schemas", {})
    schema = schemas.get(schema_name, {})

    if "$ref" in schema and not schema.get("properties"):
        ref = schema["$ref"]
        if ref.startswith("#/"):
            parts = ref[2:].split("/")
            node = oas
            for part in parts:
                part = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node, dict):
                    return set()
                node = node.get(part, {})
            schema = node if isinstance(node, dict) else {}

    return set(schema.get("properties", {}).keys())


def structural_match(consumer_fields: set[str], oas: dict, threshold: float) -> tuple[str | None, float]:
    """Find the OAS component schema whose properties best contain consumer_fields."""
    if not consumer_fields:
        return (None, 0.0)

    schemas = oas.get("components", {}).get("schemas", {})
    best_name: str | None = None
    best_score = 0.0

    for schema_name in schemas:
        schema_props = get_schema_properties(schema_name, oas)
        if not schema_props:
            continue
        score = len(consumer_fields & schema_props) / len(consumer_fields)
        if score > best_score:
            best_score = score
            best_name = schema_name

    if best_score >= threshold:
        return (best_name, best_score)
    return (None, best_score)


def resolve_response_fields(
    type_name: str | None,
    consumer_fields: set[str],
    oas: dict,
) -> tuple[set[str] | None, int, str]:
    """Run through 4 tiers. Return (fields_or_None, tier, note)."""
    schemas = oas.get("components", {}).get("schemas", {})

    # Tier 1: exact name match
    if type_name is not None and type_name in schemas:
        fields = consumer_fields or get_schema_properties(type_name, oas)
        return (fields, 1, f"exact → {type_name}")

    # Tier 2: normalised name match
    if type_name is not None:
        norm = normalise_type_name(type_name)
        if norm in schemas:
            fields = consumer_fields or get_schema_properties(norm, oas)
            return (fields, 2, f"normalised → {norm}")

    # Tier 3: structural match
    schema, score = structural_match(consumer_fields, oas, STRUCTURAL_THRESHOLD)
    if schema is not None:
        return (consumer_fields, 3, f"structural → {schema} ({score:.0%})")

    # Tier 4: fallback
    return (None, 4, "no type match — OAS required[] used")


def get_routes_iterative(ripwire_bin: str, consumer_root: str, max_iter: int) -> list[dict]:
    """Run ripwire --for=RIPWIRE_TASK iteratively until confidence=="high" and not over_ceiling."""
    routes = []
    for attempt in range(1, max_iter + 1):
        try:
            xml_str = run_ripwire(ripwire_bin, consumer_root, [f"--for={RIPWIRE_TASK}"])
        except RuntimeError as e:
            raise RuntimeError(f"ripwire failed on attempt {attempt}: {e}") from e
        routes, confidence, over_ceiling = parse_routes_xml(xml_str)
        print(
            f"  ripwire attempt {attempt}: {len(routes)} route(s), "
            f"confidence={confidence}, over_ceiling={over_ceiling}",
            file=sys.stderr,
        )
        if confidence == "high" and not over_ceiling:
            break
        if attempt < max_iter:
            print("  confidence low or truncated — retrying with broader task", file=sys.stderr)
    return routes


def enrich_route_with_type(route: dict, ripwire_bin: str, consumer_root: str, oas: dict) -> dict:
    """Discover the consumer response type for a route and resolve its fields.

    If the route carries `_type_name` (set by response-type discovery), the
    function-body expansion step is skipped — the type is already known.
    Only required consumer fields (not optional ones) drive the denominator.
    """
    route = dict(route)

    # Response-type discovery pre-resolves the type; HTTP-call-site discovery does not.
    type_name: str | None = route.pop("_type_name", None)

    if type_name is None:
        body = ""
        if route.get("from"):
            try:
                expand_xml = run_ripwire(ripwire_bin, consumer_root, [f"--expand={route['from']}"])
            except RuntimeError:
                expand_xml = ""
            body = parse_body_xml(expand_xml)
        type_name = extract_return_type(body)

    required_fields: set[str] = set()
    optional_fields: set[str] = set()
    if type_name:
        try:
            type_xml = run_ripwire(ripwire_bin, consumer_root, [f"--for={type_name}"])
        except RuntimeError:
            type_xml = ""
        required_fields, optional_fields = parse_type_fields_xml(type_xml, type_name)

    # Only required fields drive the coverage denominator.
    # Optional fields (field?: T or field = default) are not gaps if absent from the pact.
    fields, tier, note = resolve_response_fields(type_name, required_fields, oas)

    route.update({
        "type_name": type_name,
        "consumer_fields": sorted(required_fields),
        "consumer_optional_fields": sorted(optional_fields),
        "resolved_fields": sorted(fields) if fields is not None else None,
        "tier": tier,
        "tier_note": note,
    })
    return route


# ─── Response-type discovery (fallback for unsupported HTTP clients) ───────────

_DESER_PATTERNS = [
    re.compile(r'([A-Z][A-Za-z0-9_]+)\s*\(\s*\*\*'),                            # TypeName(**
    re.compile(r'([A-Z][A-Za-z0-9_]+)\.(?:from_dict|model_validate|parse_obj'
               r'|parse_raw|from_json|model_construct)\s*\('),                   # TypeName.method(
    re.compile(r'(?:resp|response|res)\s*\.\s*\w+\s+as\s+([A-Z][A-Za-z0-9_]+)'), # resp.data as T
    re.compile(r'await\s+\w+\.json\s*\(\s*\)\s+as\s+([A-Z][A-Za-z0-9_]+)'),     # await r.json() as T
]


def extract_url_path(body: str) -> str | None:
    """Extract and normalise a URL path template from a function body.

    Handles Python f-strings (`f"{base}/orders/{id}"`),
    TypeScript template literals (`` `${base}/orders/${id}` ``),
    and plain string literals (`"/orders/1234"`).
    Returns an OAS-style path like `/orders/{param}` or None.
    """
    candidates: list[str] = []

    # f-strings and template literals: capture anything inside quotes/backticks
    for m in re.finditer(r'(?:f["\']|`)([^"\'`\n]+)(?:["\']|`)', body):
        text = m.group(1)
        path_m = re.search(
            r'(?:https?://[^/\s]*)?'                              # optional http://host
            r'(/(?:[\w%-]|\{[^}]+\}|\$\{[^}]+\})'               # first path segment
            r'(?:[/\w%-]|\{[^}]+\}|\$\{[^}]+\})*)',              # rest of path
            text,
        )
        if path_m:
            candidates.append(path_m.group(1))

    # Plain string literals starting with / or containing a full https?:// URL
    for m in re.finditer(r'["\']([^\'"]+)["\']', body):
        text = m.group(1)
        path_m = re.search(r'(?:https?://[^/\s]*)?(/[\w/-]{3,})', text)
        if path_m:
            candidates.append(path_m.group(1))

    if not candidates:
        return None

    # Prefer the path with the most segments (most specific)
    path = max(candidates, key=lambda p: p.count('/'))

    # Normalise interpolations → {param}
    path = re.sub(r'\$\{[^}]+\}', '{param}', path)   # TS: ${var}
    path = re.sub(r'\{[^}]+\}', '{param}', path)      # Python: {var}
    path = re.sub(r'/\d+(?=/|$)', '/{param}', path)   # literal IDs: /1234 → /{param}
    path = path.rstrip('/')
    return path if path.startswith('/') else None


def extract_http_method(body: str) -> str | None:
    """Extract the HTTP method used in a function body.

    Checks explicit method strings first, then client method-call patterns.
    Longer/rarer methods are checked before GET to avoid false matches.
    """
    # Explicit method attribute: method="POST" or method: "DELETE"
    for method in ('DELETE', 'PATCH', 'POST', 'PUT', 'GET'):
        if re.search(rf'\bmethod\s*[=:]\s*["\']?{method}["\']?\b', body, re.IGNORECASE):
            return method

    # Client method call: session.delete(, client.post(, requests.get(, etc.
    for method in ('delete', 'patch', 'post', 'put', 'get'):
        if re.search(
            rf'(?:session|client|self|requests|axios|httpx|http)\s*\.\s*{method}\s*\(',
            body, re.IGNORECASE,
        ):
            return method.upper()

    # Bare fetch(url) with no method option → GET
    if re.search(r'\bfetch\s*\(', body) and not re.search(r'\bmethod\b', body):
        return 'GET'

    return None


def parse_deserialization_xml(xml_str: str) -> list[dict]:
    """Find response-deserialization sites in ripwire XML function bodies.

    Scans <s t="fn|method|func"> elements for patterns like `TypeName(**data)`,
    `TypeName.model_validate(data)`, `resp.data as TypeName`, etc.
    Returns [{"type_name": ..., "function_name": ...}, ...].
    """
    try:
        root_el = ET.fromstring(xml_str)
    except ET.ParseError:
        return []

    hits: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for fn_elem in root_el.iter("s"):
        if fn_elem.get("t") not in ("fn", "method", "func"):
            continue
        func_name = fn_elem.get("n", "")
        for body_elem in fn_elem:
            if body_elem.tag != "body" or not body_elem.text:
                continue
            for pattern in _DESER_PATTERNS:
                for m in pattern.finditer(body_elem.text):
                    type_name = m.group(1)
                    if type_name in SKIP_TYPE_NAMES or len(type_name) < 2:
                        continue
                    key = (type_name, func_name)
                    if key not in seen:
                        seen.add(key)
                        hits.append({"type_name": type_name, "function_name": func_name})

    return hits


def get_routes_via_response_types(
    ripwire_bin: str,
    consumer_root: str,
    oas: dict,
    max_iter: int,
) -> list[dict]:
    """Alternative route discovery: find routes via response-type construction sites.

    Used when HTTP-call-site discovery (get_routes_iterative) finds nothing —
    e.g. when the consumer uses aiohttp, net/http, or another client ripwire
    doesn't recognise.

    Strategy:
      1. Ask ripwire for HTTP response body deserialization patterns.
      2. Scan returned function bodies for TypeName(**data) / TypeName.method(data).
      3. For each (function, type) hit, extract the URL path and HTTP method
         from the same function body.
      4. Return routes with `_type_name` pre-set so enrich_route_with_type
         skips the return-type extraction step.
    """
    last_xml = ""
    hits: list[dict] = []

    for attempt in range(1, max_iter + 1):
        try:
            xml_str = run_ripwire(ripwire_bin, consumer_root, [f"--for={RESPONSE_TYPE_TASK}"])
        except RuntimeError as e:
            print(f"  response-type attempt {attempt}: {e}", file=sys.stderr)
            break
        last_xml = xml_str
        hits = parse_deserialization_xml(xml_str)
        try:
            root_el = ET.fromstring(xml_str)
            confidence = root_el.get("confidence", "low")
            over_ceiling = root_el.get("over_ceiling", "0") == "1"
        except ET.ParseError:
            confidence, over_ceiling = "low", False
        print(
            f"  response-type attempt {attempt}: {len(hits)} deserialization site(s), "
            f"confidence={confidence}, over_ceiling={over_ceiling}",
            file=sys.stderr,
        )
        if confidence == "high" and not over_ceiling:
            break

    if not hits:
        return []

    # Build function_name → body map from the last ripwire result (avoids re-expanding)
    fn_bodies: dict[str, str] = {}
    try:
        root_el = ET.fromstring(last_xml)
        for fn_elem in root_el.iter("s"):
            if fn_elem.get("t") not in ("fn", "method", "func"):
                continue
            name = fn_elem.get("n", "")
            for body_elem in fn_elem:
                if body_elem.tag == "body" and body_elem.text:
                    fn_bodies[name] = body_elem.text
    except ET.ParseError:
        pass

    routes: list[dict] = []
    seen_paths: set[tuple[str, str]] = set()

    for hit in hits:
        func_name = hit["function_name"]
        type_name = hit["type_name"]

        body = fn_bodies.get(func_name, "")
        if not body:
            try:
                body_xml = run_ripwire(ripwire_bin, consumer_root, [f"--expand={func_name}"])
                body = parse_body_xml(body_xml)
            except RuntimeError:
                continue

        path = extract_url_path(body)
        method = extract_http_method(body)
        if not path or not method:
            continue

        key = (method.upper(), path)
        if key in seen_paths:
            continue
        seen_paths.add(key)

        routes.append({
            "method": method.upper(),
            "path": path,
            "from": func_name,
            "to": "",
            "_type_name": type_name,
        })

    return routes


# ─── Path matching ─────────────────────────────────────────────────────────────

def _oas_path_to_pattern(oas_path: str) -> re.Pattern:
    """Convert an OAS path template to a compiled regex anchored at both ends."""
    parts = re.split(r'(\{[^}]+\})', oas_path)
    regex = ""
    for part in parts:
        if part.startswith("{") and part.endswith("}"):
            regex += "[^/]+"
        else:
            regex += re.escape(part)
    return re.compile(f"^{regex}$")


def find_oas_operation(method: str, path: str, oas: dict) -> tuple[str, str] | None:
    """Find the matching OAS operation for a route (method, path). Returns (oas_path, method) or None."""
    method_lower = method.lower()
    paths = oas.get("paths", {})

    # Exact match
    if path in paths and isinstance(paths[path], dict) and method_lower in paths[path]:
        return (path, method_lower)

    # Regex match
    candidates = []
    for oas_path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        if method_lower not in path_item:
            continue
        pattern = _oas_path_to_pattern(oas_path)
        if pattern.match(path):
            param_count = oas_path.count("{")
            candidates.append((param_count, oas_path))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return (candidates[0][1], method_lower)


# ─── Filtered OAS builder ──────────────────────────────────────────────────────

def build_filtered_oas(routes: list[dict], oas: dict) -> tuple[dict, list[dict]]:
    """Build the filtered OAS dict. Returns (filtered_oas, enriched_routes)."""
    filtered: dict = {k: copy.deepcopy(v) for k, v in oas.items() if k != "paths"}
    filtered["paths"] = {}

    schemas = oas.get("components", {}).get("schemas", {})
    enriched_routes: list[dict] = []

    for route in routes:
        match = find_oas_operation(route["method"], route["path"], oas)
        if match is None:
            print(
                f"  SKIP: no OAS operation for {route['method']} {route['path']}",
                file=sys.stderr,
            )
            enriched_routes.append(route)
            continue

        oas_path, oas_method = match
        orig_path_item = oas.get("paths", {}).get(oas_path, {})

        # Initialise path item in filtered OAS if not already there
        if oas_path not in filtered["paths"]:
            filtered["paths"][oas_path] = {
                k: copy.deepcopy(v)
                for k, v in orig_path_item.items()
                if k not in _HTTP_METHODS
            }

        # Deep copy the operation
        operation = copy.deepcopy(orig_path_item.get(oas_method, {}))

        resolved_fields = route.get("resolved_fields")

        if resolved_fields is not None:
            resolved_set = set(resolved_fields)
            for _code, response_obj in operation.get("responses", {}).items():
                if not isinstance(response_obj, dict):
                    continue
                content = response_obj.get("content", {})
                if not isinstance(content, dict):
                    continue
                for _media_type, media_obj in content.items():
                    if not isinstance(media_obj, dict):
                        continue
                    schema = media_obj.get("schema", {})
                    if not isinstance(schema, dict):
                        continue

                    # Resolve $ref to get properties inline
                    if "$ref" in schema:
                        ref_name = schema["$ref"].split("/")[-1]
                        ref_schema = schemas.get(ref_name, {})
                        resolved_schema = copy.deepcopy(ref_schema)
                        media_obj["schema"] = resolved_schema
                        schema = resolved_schema

                    properties = schema.get("properties", {})
                    if properties:
                        narrowed = sorted(resolved_set & set(properties.keys()))
                    else:
                        narrowed = sorted(resolved_fields)

                    schema["required"] = narrowed

        # Add x-consumer-type-match annotation
        operation["x-consumer-type-match"] = {
            "tier": route.get("tier", 4),
            "note": route.get("tier_note", ""),
            "consumer-type": route.get("type_name"),
            "consumer-fields": list(route.get("consumer_fields") or []),
            "consumer-optional-fields": list(route.get("consumer_optional_fields") or []),
        }

        filtered["paths"][oas_path][oas_method] = operation
        enriched_routes.append(route)

    return filtered, enriched_routes


# ─── Summary ───────────────────────────────────────────────────────────────────

def print_summary(routes: list[dict], spec_path: str, output_path: str) -> bool:
    """Print a human-readable summary to stderr. Returns True if any Tier 4 fallbacks exist."""
    print(f"\nFiltered OAS written to: {output_path}", file=sys.stderr)
    print(f"Consumer routes analysed: {len(routes)}\n", file=sys.stderr)

    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for route in routes:
        tier = route.get("tier", 4)
        note = route.get("tier_note", "")
        method = route.get("method", "?")
        path = route.get("path", "?")
        print(f"  {method} {path}  [Tier {tier} — {note}]", file=sys.stderr)
        if tier in tier_counts:
            tier_counts[tier] += 1

    print("\nTier breakdown:", file=sys.stderr)
    print(f"  Tier 1 (exact type match):        {tier_counts[1]}", file=sys.stderr)
    print(f"  Tier 2 (normalised name match):   {tier_counts[2]}", file=sys.stderr)
    print(f"  Tier 3 (structural field match):  {tier_counts[3]}", file=sys.stderr)
    print(f"  Tier 4 (OAS fallback):            {tier_counts[4]}", file=sys.stderr)

    return tier_counts[4] > 0


# ─── Fallback route source ─────────────────────────────────────────────────────

def routes_from_json(routes_json: str) -> list[dict]:
    """Parse manually-supplied route list JSON (Tier 4, no type info).

    Accepts: [{"method": "GET", "path": "/orders/{id}"}, ...]
    Used for HTTP clients unsupported by ripwire (e.g. aiohttp).
    """
    import json

    try:
        raw = json.loads(routes_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"--routes JSON is invalid: {e}") from e

    if not isinstance(raw, list):
        raise ValueError("--routes JSON must be a JSON array")

    routes: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for item in raw:
        if not isinstance(item, dict):
            raise ValueError(f"--routes JSON items must be objects, got: {item!r}")
        method = (item.get("method") or "").strip().lower()
        path = (item.get("path") or "").strip()
        if not method or not path:
            raise ValueError(f"--routes JSON item missing 'method' or 'path': {item!r}")
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        routes.append({
            "method": method,
            "path": path,
            "from": item.get("from", ""),
            "to": item.get("to", ""),
            "type_name": None,
            "consumer_fields": [],
            "resolved_fields": None,
            "tier": 4,
            "tier_note": "manually supplied route (no type info)",
        })

    return routes


# ─── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter an OpenAPI spec to only what a consumer codebase uses.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--spec", required=True, help="Path to OpenAPI spec (YAML or JSON)")
    parser.add_argument(
        "--kg",
        help="Pre-generated ripwire XML (skips running ripwire for routes)",
    )
    parser.add_argument(
        "--consumer-root",
        help="Consumer codebase root (required if --kg not provided)",
    )
    parser.add_argument(
        "--ripwire",
        default="ripwire",
        help="Path to ripwire binary",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output path for filtered OAS (- for stdout)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=STRUCTURAL_THRESHOLD,
        help="Structural match threshold (default 0.8)",
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=MAX_ITER,
        help="Max ripwire iterations (default 3)",
    )
    parser.add_argument(
        "--routes",
        metavar="JSON",
        help=(
            'Manually-supplied route list as JSON: \'[{"method":"GET","path":"/orders/{id}"},...]\'. '
            "Use when ripwire doesn't support the consumer's HTTP client (e.g. aiohttp). "
            "Tier 4 fallback — no response-field narrowing. "
            "Identify routes by reading the consumer source code."
        ),
    )
    args = parser.parse_args()

    if not args.kg and not args.consumer_root and not args.routes:
        print(
            "ERROR: provide --kg, --consumer-root, or --routes\n"
            "  ripwire-based:  --kg kg.xml  or  --consumer-root ./src\n"
            "  manual fallback: --routes '[{\"method\":\"GET\",\"path\":\"/orders/{id}\"}]'",
            file=sys.stderr,
        )
        sys.exit(2)

    # Load OAS
    try:
        oas = load_oas(args.spec)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)

    # Get routes via ripwire, falling back to --routes if ripwire finds nothing
    routes: list[dict] = []
    ripwire_attempted = bool(args.kg or args.consumer_root)

    if args.kg:
        xml_str = Path(args.kg).read_text()
        routes, _confidence, _over_ceiling = parse_routes_xml(xml_str)
        if not routes:
            print("WARNING: no <route> elements found in KG XML", file=sys.stderr)
    elif args.consumer_root:
        try:
            routes = get_routes_iterative(args.ripwire, args.consumer_root, args.max_iter)
        except RuntimeError as e:
            print(f"WARNING: ripwire error — {e}", file=sys.stderr)
        if not routes:
            print(
                "WARNING: ripwire found no HTTP route calls in consumer codebase\n"
                "  (HTTP client may be unsupported — trying response-type discovery)",
                file=sys.stderr,
            )

    # Response-type discovery fallback: find routes by scanning for TypeName(**data) patterns.
    # Works for HTTP clients ripwire doesn't recognise (aiohttp, net/http, HttpClient, etc.)
    if not routes and args.consumer_root:
        print("INFO: running response-type discovery", file=sys.stderr)
        try:
            routes = get_routes_via_response_types(
                args.ripwire, args.consumer_root, oas, args.max_iter
            )
        except Exception as e:
            print(f"WARNING: response-type discovery failed — {e}", file=sys.stderr)
        if routes:
            print(f"INFO: response-type discovery found {len(routes)} route(s)", file=sys.stderr)
        else:
            print(
                "WARNING: response-type discovery also found nothing\n"
                "  (consumer may use a dynamic pattern not visible to static analysis)",
                file=sys.stderr,
            )

    # --routes fallback: manually-supplied route list
    if not routes and args.routes:
        print("INFO: using manually-supplied --routes", file=sys.stderr)
        try:
            routes = routes_from_json(args.routes)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(2)
        if routes:
            print(f"INFO: loaded {len(routes)} route(s) from --routes", file=sys.stderr)

    if not routes:
        msg = "ERROR: no routes found."
        if ripwire_attempted and not args.routes:
            msg += (
                "\n  Tip: if the consumer uses an unsupported HTTP client (e.g. aiohttp),"
                "\n  read the source code to identify which endpoints it calls, then pass:"
                "\n  --routes '[{\"method\":\"GET\",\"path\":\"/orders/{id}\"},...]'"
            )
        print(msg, file=sys.stderr)
        sys.exit(2)

    # Enrich with type info when consumer-root is available AND routes came from
    # ripwire (manual-fallback routes already carry Tier 4 annotations).
    routes_need_enrichment = [r for r in routes if "tier" not in r]
    routes_already_annotated = [r for r in routes if "tier" in r]

    if args.consumer_root and routes_need_enrichment:
        enriched = []
        for route in routes_need_enrichment:
            enriched.append(enrich_route_with_type(route, args.ripwire, args.consumer_root, oas))
        routes = enriched + routes_already_annotated
    elif routes_need_enrichment:
        # No type resolution possible without consumer-root — all Tier 4
        for route in routes_need_enrichment:
            route.update({
                "type_name": None,
                "consumer_fields": [],
                "consumer_optional_fields": [],
                "resolved_fields": None,
                "tier": 4,
                "tier_note": "no consumer-root — OAS required[] used",
            })
        routes = routes_need_enrichment + routes_already_annotated

    filtered_oas, routes = build_filtered_oas(routes, oas)

    # Write output
    out_yaml = yaml.dump(filtered_oas, default_flow_style=False, allow_unicode=True)
    if args.output == "-":
        print(out_yaml)
    else:
        Path(args.output).write_text(out_yaml)

    has_fallbacks = print_summary(routes, args.spec, args.output)
    sys.exit(1 if has_fallbacks else 0)


if __name__ == "__main__":
    main()
