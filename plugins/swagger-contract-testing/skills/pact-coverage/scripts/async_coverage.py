#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml~=6.0",
# ]
# ///
"""
async_coverage.py — Pact message-pact coverage against an AsyncAPI 3.x spec.

Used by parse_pact_coverage.py when --spec is an AsyncAPI document. Reports which
operations (channels), message variants, required payload fields and required header
fields are exercised by Pact message interactions (v3 `messages`, v4
`Asynchronous/Messages`).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import Any, TypedDict, cast

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

DEFAULT_ACTIONS = frozenset({"send"})


class AsyncMessage(TypedDict):
    key: str
    names: list[str]
    payload_required: set[str]
    fit_required: set[str]
    header_required: set[str]
    discriminators: dict[str, list[Any]]


class AsyncOp(TypedDict):
    action: str
    address: str
    messages: dict[str, AsyncMessage]


class PactMessage(TypedDict):
    description: str
    metadata: dict[str, Any]
    contents: dict[str, Any]
    fields: set[str]


# ─── Spec loading ──────────────────────────────────────────────────────────────


def load_asyncapi(path: str) -> dict[str, Any]:
    """Load an AsyncAPI spec (YAML or JSON). Raises ValueError on parse failure."""
    with open(path) as f:
        raw = f.read()
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ValueError(f"Could not parse spec '{path}': {e}") from e
    if not isinstance(data, dict):
        raise ValueError("spec did not parse to a mapping")
    return cast(dict[str, Any], data)


def is_asyncapi(path: str) -> bool:
    """True when the file parses and has a top-level `asyncapi` key."""
    try:
        return "asyncapi" in load_asyncapi(path)
    except (ValueError, OSError):
        return False


# ─── $ref handling and schema helpers ──────────────────────────────────────────


def _unescape(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")


def _ref_key(node: Any) -> str | None:
    """Last pointer segment of a node's local $ref, e.g. '#/channels/a' -> 'a'."""
    if isinstance(node, dict) and isinstance(node.get("$ref"), str):
        return _unescape(node["$ref"].rsplit("/", 1)[-1])
    return None


def _deref(spec: dict[str, Any], node: Any) -> dict[str, Any]:
    """Follow a chain of local `#/...` $refs. Returns {} for non-dicts, external refs and cycles."""
    seen: set[str] = set()
    while isinstance(node, dict) and isinstance(node.get("$ref"), str):
        ref = node["$ref"]
        if not ref.startswith("#/") or ref in seen:
            return {}
        seen.add(ref)
        target: Any = spec
        for part in ref[2:].split("/"):
            key = _unescape(part)
            if not isinstance(target, dict) or key not in target:
                return {}
            target = target[key]
        node = target
    return cast(dict[str, Any], node) if isinstance(node, dict) else {}


def _unwrap_schema(spec: dict[str, Any], schema: Any) -> dict[str, Any]:
    """Resolve $ref and unwrap an AsyncAPI multi-format schema object."""
    resolved = _deref(spec, schema)
    if "schemaFormat" in resolved and isinstance(resolved.get("schema"), dict):
        return _deref(spec, resolved["schema"])
    return resolved


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _required(spec: dict[str, Any], schema: Any, *, variants: bool = True, seen: set[int] | None = None) -> set[str]:
    """
    Required field names (top-level); unions allOf (and, with `variants`, anyOf/oneOf) like the HTTP checker.

    Each resolved schema node is visited once, so $ref cycles and shared branches stay linear.
    """
    node = _unwrap_schema(spec, schema)
    visited = seen if seen is not None else set()
    if not node or id(node) in visited:
        return set()
    visited.add(id(node))
    fields = {str(f) for f in _as_list(node.get("required"))}
    keywords = ("allOf", "anyOf", "oneOf") if variants else ("allOf",)
    for keyword in keywords:
        for branch in _as_list(node.get(keyword)):
            fields |= _required(spec, branch, variants=variants, seen=visited)
    return fields


def _discriminators(spec: dict[str, Any], schema: Any, seen: set[int] | None = None) -> dict[str, list[Any]]:
    """Properties constrained by `const` or `enum`: {field: [allowed values]}."""
    node = _unwrap_schema(spec, schema)
    visited = seen if seen is not None else set()
    found: dict[str, list[Any]] = {}
    if not node or id(node) in visited:
        return found
    visited.add(id(node))
    for branch in _as_list(node.get("allOf")):
        found.update(_discriminators(spec, branch, visited))
    props = node.get("properties", {})
    if isinstance(props, dict):
        for name, sub in props.items():
            prop = _deref(spec, sub)
            if "const" in prop:
                found[str(name)] = [prop["const"]]
            elif isinstance(prop.get("enum"), list):
                found[str(name)] = list(prop["enum"])
    return found


# ─── AsyncAPI operations ───────────────────────────────────────────────────────


def _build_message(spec: dict[str, Any], key: str, node: Any) -> AsyncMessage:
    msg = _deref(spec, node)
    names = [key] + [str(msg[k]) for k in ("messageId", "name", "title") if msg.get(k)]
    payload = msg.get("payload", {})
    return {
        "key": key,
        "names": names,
        "payload_required": _required(spec, payload),
        "fit_required": _required(spec, payload, variants=False),
        "header_required": _required(spec, msg.get("headers", {})),
        "discriminators": _discriminators(spec, payload),
    }


def extract_async_operations(
    spec: dict[str, Any],
    actions: frozenset[str] = DEFAULT_ACTIONS,
    channels: set[str] | None = None,
) -> dict[str, AsyncOp]:
    """
    Operations in scope, keyed by the spec's operation key.

    `actions` limits by operation action (send/receive); `channels` limits to channel addresses.
    An operation without a `messages` list covers every message on its channel.
    """
    raw_ops = spec.get("operations", {})
    if not isinstance(raw_ops, dict):
        return {}
    result: dict[str, AsyncOp] = {}
    for op_key, op_node in raw_ops.items():
        op = _deref(spec, op_node)
        action = str(op.get("action", ""))
        if action not in actions:
            continue
        channel_node = op.get("channel")
        channel = _deref(spec, channel_node)
        address = str(channel.get("address") or _ref_key(channel_node) or "")
        if channels is not None and address not in channels:
            continue
        listed = op.get("messages")
        picked: dict[str, Any] = {}
        if isinstance(listed, list) and listed:
            for i, ref in enumerate(listed):
                picked[_ref_key(ref) or f"message{i}"] = ref
        elif isinstance(channel.get("messages"), dict):
            picked = dict(channel["messages"])
        result[str(op_key)] = {
            "action": action,
            "address": address,
            "messages": {k: _build_message(spec, k, n) for k, n in picked.items()},
        }
    return result


# ─── Pact messages ─────────────────────────────────────────────────────────────


def build_pact_message(description: Any, contents: Any, metadata: Any) -> PactMessage:
    """Normalise one pact message. Non-object or unparseable contents yield no fields."""
    if isinstance(contents, str):
        try:
            contents = json.loads(contents)
        except json.JSONDecodeError:
            contents = {}
    body = cast(dict[str, Any], contents) if isinstance(contents, dict) else {}
    meta = cast(dict[str, Any], metadata) if isinstance(metadata, dict) else {}
    return {
        "description": str(description or ""),
        "metadata": meta,
        "contents": body,
        "fields": set(body.keys()),
    }


def extract_pact_messages(pact: dict[str, Any]) -> list[PactMessage]:
    """Message interactions from a pact: v3 `messages[]` and v4 `Asynchronous/Messages`."""
    found: list[PactMessage] = []
    for m in _as_list(pact.get("messages")):
        if isinstance(m, dict):
            found.append(build_pact_message(m.get("description"), m.get("contents"), m.get("metadata")))
    for ix in _as_list(pact.get("interactions")):
        if isinstance(ix, dict) and ix.get("type") == "Asynchronous/Messages":
            contents = ix.get("contents")
            if isinstance(contents, dict) and "content" in contents:
                contents = contents["content"]
            found.append(build_pact_message(ix.get("description"), contents, ix.get("metadata")))
    return found


# ─── Matching ──────────────────────────────────────────────────────────────────

CHANNEL_META_KEYS = ("topic", "kafka_topic", "queue", "routingkey", "channel")

Pair = tuple[str, str]


def _channel_hints(msg: PactMessage) -> set[str]:
    lowered = {str(k).lower(): v for k, v in msg["metadata"].items()}
    return {v for k in CHANNEL_META_KEYS if isinstance((v := lowered.get(k)), str)}


def _fits(msg: PactMessage, am: AsyncMessage) -> bool:
    if not am["fit_required"] and not am["discriminators"]:
        return False  # nothing to match on structurally; only channel/name can identify it
    if not am["fit_required"] <= msg["fields"]:
        return False
    return all(msg["contents"][f] in allowed for f, allowed in am["discriminators"].items() if f in msg["contents"])


def match_message(msg: PactMessage, ops: dict[str, AsyncOp]) -> tuple[str, list[Pair]]:
    """
    Match one pact message to AsyncAPI messages.

    Returns ("matched" | "ambiguous" | "unmatched", [(operation key, message key), ...]).
    """

    def identity(pair: Pair) -> Pair:
        return (ops[pair[0]]["address"], pair[1])

    pairs: list[Pair] = [(ok, mk) for ok, op in ops.items() for mk in op["messages"]]
    narrowed = False

    hints = _channel_hints(msg)
    by_channel = [p for p in pairs if ops[p[0]]["address"] in hints]
    if by_channel:
        pairs, narrowed = by_channel, True
    elif hints:
        return "unmatched", []  # the pact names a channel that is not in scope

    description = msg["description"]
    by_name = [p for p in pairs if description and description in ops[p[0]]["messages"][p[1]]["names"]]
    if by_name:
        pairs, narrowed = by_name, True

    if narrowed and len({identity(p) for p in pairs}) == 1:
        return "matched", pairs

    fitting = [p for p in pairs if _fits(msg, ops[p[0]]["messages"][p[1]])]
    if not fitting:
        return "unmatched", []
    if len({identity(p) for p in fitting}) == 1:
        return "matched", fitting
    return "ambiguous", fitting


# ─── Coverage ──────────────────────────────────────────────────────────────────


def _field_result(required: set[str], present: set[str], *, fold_case: bool = False) -> dict[str, list[str]]:
    have = {p.lower() for p in present} if fold_case else present
    missing = [r for r in sorted(required) if (r.lower() if fold_case else r) not in have]
    return {"required": sorted(required), "missing": missing}


def compute_async_coverage(ops: dict[str, AsyncOp], pact_messages: list[PactMessage]) -> dict[str, Any]:
    """Match every pact message, then measure operation, message, payload and header coverage."""
    matched: dict[Pair, list[PactMessage]] = defaultdict(list)
    ambiguous: list[dict[str, Any]] = []
    unmatched: list[dict[str, str]] = []
    for pm in pact_messages:
        status, pairs = match_message(pm, ops)
        if status == "matched":
            for pair in pairs:
                matched[pair].append(pm)
        elif status == "ambiguous":
            candidates = sorted(f"{ops[ok]['address']}/{mk}" for ok, mk in pairs)
            ambiguous.append({"description": pm["description"], "candidates": candidates})
        else:
            unmatched.append({"description": pm["description"]})

    operations: dict[str, Any] = {}
    messages: dict[str, Any] = {}
    payload_fields: dict[str, Any] = {}
    header_fields: dict[str, Any] = {}
    for op_key, op in ops.items():
        operations[op_key] = {
            "action": op["action"],
            "address": op["address"],
            "covered": any((op_key, mk) in matched for mk in op["messages"]),
        }
        for msg_key, am in op["messages"].items():
            key = f"{op_key}/{msg_key}"
            hits = matched.get((op_key, msg_key), [])
            messages[key] = {"covered": bool(hits)}
            if not hits:
                continue
            fields = {f for pm in hits for f in pm["fields"]}
            meta_keys = {str(k) for pm in hits for k in pm["metadata"]}
            payload_fields[key] = _field_result(am["payload_required"], fields)
            header_fields[key] = _field_result(am["header_required"], meta_keys, fold_case=True)

    has_gaps = (
        not all(o["covered"] for o in operations.values())
        or not all(m["covered"] for m in messages.values())
        or any(r["missing"] for r in payload_fields.values())
        or any(r["missing"] for r in header_fields.values())
    )
    return {
        "operations": operations,
        "messages": messages,
        "payload_fields": payload_fields,
        "header_fields": header_fields,
        "ambiguous": ambiguous,
        "unmatched": unmatched,
        "has_gaps": has_gaps,
    }


# ─── Report ────────────────────────────────────────────────────────────────────


def _mark(ok: bool) -> str:
    return "✓" if ok else "✗"


def print_async_report(
    report: dict[str, Any], spec_path: str, pact_files: list[str], *, consumer_filtered: bool
) -> None:
    print("PACT COVERAGE (AsyncAPI)")
    print(f"Spec:  {spec_path}")
    print(f"Pacts: {', '.join(pact_files)}")
    if not consumer_filtered:
        print("NOTE:  no --consumer-channels given; channels the consumer does not use will show as gaps.")

    print("\n1 · CHANNEL / OPERATION")
    for op_key, op in report["operations"].items():
        suffix = "" if op["covered"] else "  NOT COVERED"
        print(f"  {_mark(op['covered'])} {op['action']} {op['address']}  ({op_key}){suffix}")

    print("\n2 · MESSAGE VARIANTS")
    for key, m in report["messages"].items():
        print(f"  {_mark(m['covered'])} {key}{'' if m['covered'] else '  NOT COVERED'}")

    sections = (("3 · PAYLOAD REQUIRED FIELDS", "payload_fields"), ("4 · HEADER REQUIRED FIELDS", "header_fields"))
    for title, section in sections:
        print(f"\n{title}")
        for key, r in report[section].items():
            if not r["required"]:
                print(f"  - {key}  n/a (no required fields in spec)")
            elif r["missing"]:
                print(f"  ✗ {key}  missing: {', '.join(r['missing'])}")
            else:
                print(f"  ✓ {key}")

    if report["ambiguous"]:
        print("\nAMBIGUOUS PACT MESSAGES (matched several AsyncAPI messages; not counted)")
        for a in report["ambiguous"]:
            print(f"  ? {a['description']!r} -> {', '.join(a['candidates'])}")
    if report["unmatched"]:
        print("\nUNMATCHED PACT MESSAGES (matched no AsyncAPI message in scope)")
        for u in report["unmatched"]:
            print(f"  ? {u['description']!r}")

    print(f"\nResult: {'GAPS FOUND' if report['has_gaps'] else 'FULL COVERAGE'}")


def run(
    spec_path: str,
    pact_messages: list[PactMessage],
    pact_files: list[str],
    *,
    include_actions: frozenset[str],
    consumer_channels: set[str] | None,
    as_json: bool,
) -> int:
    """Compute and print async coverage. Returns the process exit code (0, 1 or 2)."""
    try:
        spec = load_asyncapi(spec_path)
    except (ValueError, OSError) as e:
        print(f"ERROR: Could not parse spec '{spec_path}': {e}", file=sys.stderr)
        return 2
    version = str(spec.get("asyncapi", ""))
    if not version.startswith("3."):
        print(f"ERROR: AsyncAPI 3.x is required, found '{version}'.", file=sys.stderr)
        return 2
    ops = extract_async_operations(spec, include_actions, consumer_channels)
    if not ops:
        scope = f" on channels {sorted(consumer_channels)}" if consumer_channels else ""
        print(f"ERROR: No operations found in spec for actions {sorted(include_actions)}{scope}.", file=sys.stderr)
        return 2

    report = compute_async_coverage(ops, pact_messages)
    report["consumer_filtered"] = consumer_channels is not None
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print_async_report(report, spec_path, pact_files, consumer_filtered=consumer_channels is not None)
    return 1 if report["has_gaps"] else 0
