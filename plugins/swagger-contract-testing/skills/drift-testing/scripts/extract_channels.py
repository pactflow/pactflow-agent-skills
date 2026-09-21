#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
extract_channels.py — Extract operations and message schemas from an AsyncAPI 3.x spec.

In summary mode (default), prints a table of every operation with its action type,
channel address, and message types. Flags messages with no payload example.

In scaffold mode (--scaffold), emits a ready-to-fill Drift `operations:` block with one
stub per operation+message — pre-wired with the correct execution mode, correlation-id
parameter, trigger/probe stubs, and FILL_IN markers for payload fields.

Supports AsyncAPI 3.x only (asyncapi: 3.0 or 3.1). Exits 2 if an AsyncAPI 2.x spec is
detected.

Usage:
  python3 extract_channels.py --spec service.asyncapi.yaml
  python3 extract_channels.py --spec service.asyncapi.yaml --scaffold > operations.yaml
  python3 extract_channels.py --spec service.asyncapi.yaml --scaffold --source async-svc
  python3 extract_channels.py --spec service.asyncapi.yaml --scaffold --only-missing drift.yaml
  python3 extract_channels.py --spec service.asyncapi.yaml --json

Exit codes:
  0 — success
  1 — messages with no payload example found (summary mode only)
  2 — error (could not parse spec, or AsyncAPI 2.x detected)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


# ─── $ref resolution ──────────────────────────────────────────────────────────


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return {}
    node: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict):
            return {}
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def resolve(obj: Any, root: dict[str, Any]) -> Any:
    """Recursively resolve $refs in obj (local refs only)."""
    if isinstance(obj, dict):
        if "$ref" in obj:
            return resolve(_resolve_ref(obj["$ref"], root), root)
        return {k: resolve(v, root) for k, v in obj.items()}
    if isinstance(obj, list):
        return [resolve(i, root) for i in obj]
    return obj


# ─── AsyncAPI spec parsing ────────────────────────────────────────────────────


def _channel_address(channel_ref: str, root: dict[str, Any]) -> str:
    """Resolve a channel $ref and return its address."""
    channel = _resolve_ref(channel_ref, root) if channel_ref.startswith("#/") else {}
    return str(channel.get("address", ""))


def _message_ids_from_op(op: dict[str, Any], root: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """
    Return list of (local_id, msg_name, resolved_msg_dict) tuples for an operation.
    message_local_id is the key under channels.<channelId>.messages.
    message_name is the name from components.messages.
    """
    results = []
    for msg_ref_obj in op.get("messages", []):
        ref = msg_ref_obj.get("$ref", "")
        # ref looks like "#/channels/<channelId>/messages/<msgLocalId>"
        # or "#/components/messages/<MsgName>"
        parts = ref.split("/")
        # strip leading empty string from "#/..." split
        if parts and parts[0] == "#":
            parts = parts[1:]
        if len(parts) >= 4 and parts[0] == "channels" and parts[2] == "messages":
            local_id = parts[3]
            # Resolve to get the actual message definition
            msg = _resolve_ref(ref, root)
            if "$ref" in msg:
                # It's a $ref to components.messages
                inner = _resolve_ref(msg["$ref"], root)
                msg_name = msg["$ref"].split("/")[-1]
            else:
                inner = msg
                msg_name = inner.get("name", local_id)
            results.append((local_id, msg_name, resolve(inner, root)))
        elif len(parts) >= 3 and parts[0] == "components" and parts[1] == "messages":
            msg_name = parts[2]
            msg = resolve(_resolve_ref(ref, root), root)
            results.append((msg_name, msg_name, msg))
    return results


def _has_reply(op: dict[str, Any]) -> bool:
    return bool(op.get("reply"))


def _payload_required_fields(msg: dict[str, Any]) -> list[str]:
    payload = msg.get("payload", {})
    return payload.get("required", []) if isinstance(payload, dict) else []


def load_operations(spec_path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Parse an AsyncAPI 3.x spec and return list of operation dicts.

    Each dict:
      operationId, action, channel_address, has_reply,
      messages: list of {local_id, name, payload_required, payload_schema}
    """
    with open(spec_path) as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise yaml.YAMLError(f"Expected a YAML mapping, got {type(raw).__name__}")

    version = str(raw.get("asyncapi", ""))
    if not version:
        raise ValueError("Not an AsyncAPI document (missing 'asyncapi:' field)")
    if version.startswith("2."):
        raise ValueError(f"AsyncAPI {version} is not supported by Drift. Only AsyncAPI 3.x is supported.")
    if not version.startswith("3."):
        raise ValueError(f"Unknown AsyncAPI version: {version}")

    ops = []
    for op_id, op_body in raw.get("operations", {}).items():
        if not isinstance(op_body, dict):
            continue
        action = op_body.get("action", "")
        channel_ref = op_body.get("channel", {}).get("$ref", "")
        channel_addr = _channel_address(channel_ref, raw)
        has_reply_block = _has_reply(op_body)
        msgs = _message_ids_from_op(op_body, raw)

        ops.append(
            {
                "operationId": op_id,
                "action": action,
                "channel_address": channel_addr,
                "has_reply": has_reply_block,
                "messages": [
                    {
                        "local_id": local_id,
                        "name": msg_name,
                        "payload_required": _payload_required_fields(msg),
                        "payload_schema": msg.get("payload", {}),
                    }
                    for local_id, msg_name, msg in msgs
                ],
            }
        )
    return ops, raw


def _execution_mode(op: dict[str, Any]) -> str:
    action = op["action"]
    if action == "send" and op["has_reply"]:
        return "async-request-reply"
    if action == "send":
        return "async-observe"
    return "async-inject"  # receive — probe vs inject-capture decided at test-writing time


# ─── Summary output ───────────────────────────────────────────────────────────


def print_summary(ops: list[dict[str, Any]]) -> bool:
    needs_fill = False
    for op in ops:
        mode = _execution_mode(op)
        print(f"  {op['operationId']}")
        print(f"    action:   {op['action']}")
        print(f"    mode:     {mode}")
        print(f"    channel:  {op['channel_address']}")
        for msg in op["messages"]:
            req = ", ".join(msg["payload_required"]) or "(none)"
            print(f"    message:  {msg['name']}  required: {req}")
            if not msg["payload_required"]:
                print("              ⚠ no required payload fields — FILL_IN payload manually")
                needs_fill = True
        print()
    return needs_fill


# ─── Scaffold output ──────────────────────────────────────────────────────────


def _op_name(op_id: str, msg_name: str, total_msgs: int, mode: str) -> str:
    """Generate the Drift operation name."""
    # Capitalise first letter of operationId for readability
    base = op_id[0].upper() + op_id[1:] if op_id else op_id
    if total_msgs == 1:
        # Single message: use mode suffix
        mode_suffix = {
            "async-observe": "Observe",
            "async-inject": "Inject",
            "async-request-reply": "SendReceive",
        }.get(mode, "Test")
        return f"{base}_{mode_suffix}"
    else:
        # Multiple messages: use message name as variant
        return f"{base}_{msg_name}"


def scaffold_observe(op: dict[str, Any], msg: dict[str, Any], op_name: str, source: str, variant_idx: int = 1) -> str:
    """Scaffold stub for async-observe (send, no reply)."""
    lines = [
        f"  {op_name}:",
        f"    target: {source}:{op['operationId']}:{msg['local_id']}",
        '    description: "FILL_IN — describe what event this observes"',
        "    parameters:",
        f"      correlation-id: {op['operationId'].lower()}-{variant_idx:03d}",
        "      timeout-ms: 5000",
    ]
    for field in msg["payload_required"]:
        lines.append(f"      {field}: FILL_IN  # required payload field")
    lines += [
        "    trigger:",
        "      executable-type: command",
        "      value: python3",
        "      parameters:",
        "        args:",
        f"          - ./hooks/trigger-{op['operationId'].lower()}.py",
        "          - --correlation-id",
        "          - ${parameters.correlation-id}",
        "          # FILL_IN — add args for payload fields your trigger needs",
        "      timeout-ms: 2000",
        "    expected:",
        "      headers:",
        "        correlation-id: ${parameters.correlation-id}",
        "      payload:",
        "        # FILL_IN — assert specific payload fields or omit to use schema validation",
    ]
    return "\n".join(lines)


def scaffold_inject(op: dict[str, Any], msg: dict[str, Any], op_name: str, source: str, variant_idx: int = 1) -> str:
    """Scaffold stub for async-inject (receive, probe command)."""
    lines = [
        f"  {op_name}:",
        f"    target: {source}:{op['operationId']}:{msg['local_id']}",
        '    description: "FILL_IN — describe what command this injects"',
        "    parameters:",
        f"      correlation-id: {op['operationId'].lower()}-{variant_idx:03d}",
        "      payload:",
    ]
    for field in msg["payload_required"]:
        lines.append(f"        {field}: FILL_IN  # required")
    if not msg["payload_required"]:
        lines.append("        # FILL_IN — see message schema for required fields")
    lines += [
        "    probe:",
        "      executable-type: command",
        "      value: python3",
        "      parameters:",
        "        args:",
        f"          - ./hooks/probe-{op['operationId'].lower()}.py",
        "          - --correlation-id",
        "          - ${parameters.correlation-id}",
        "      timeout-ms: 3000",
        "    expected:",
        "      # FILL_IN — matches probe stdout JSON",
        "      # correlationId: ${parameters.correlation-id}",
        "      # status: processed",
    ]
    return "\n".join(lines)


def scaffold_request_reply(
    op: dict[str, Any], msg: dict[str, Any], op_name: str, source: str, variant_idx: int = 1
) -> str:
    """Scaffold stub for async-request-reply (send with reply block)."""
    lines = [
        f"  {op_name}:",
        f"    target: {source}:{op['operationId']}:{msg['local_id']}",
        '    description: "FILL_IN — describe this request/reply interaction"',
        "    parameters:",
        f"      correlation-id: {op['operationId'].lower()}-{variant_idx:03d}",
        "      timeout-ms: 5000",
        "      payload:",
    ]
    for field in msg["payload_required"]:
        lines.append(f"        {field}: FILL_IN  # required")
    if not msg["payload_required"]:
        lines.append("        # FILL_IN — see request message schema")
    lines += [
        "      headers:",
        "        correlation-id: ${parameters.correlation-id}",
        "    # No trigger needed — Drift is the publisher for async-request-reply",
        "    expected:",
        "      payload:",
        "        # FILL_IN — describe the REPLY message payload (not the request)",
        "      headers:",
        "        correlation-id: ${parameters.correlation-id}",
    ]
    return "\n".join(lines)


def scaffold_all(
    ops: list[dict[str, Any]],
    source: str,
    only_missing_ops: set[str] | None = None,
) -> str:
    out = ["operations:"]
    for op in ops:
        mode = _execution_mode(op)
        total_msgs = len(op["messages"])
        if only_missing_ops and op["operationId"] in only_missing_ops:
            continue
        out.append(f"\n  # ── {op['action'].upper()} {op['operationId']} [{mode}] channel: {op['channel_address']}")
        for idx, msg in enumerate(op["messages"], start=1):
            name = _op_name(op["operationId"], msg["local_id"], total_msgs, mode)
            out.append("")
            if mode == "async-observe":
                out.append(scaffold_observe(op, msg, name, source, idx))
            elif mode == "async-request-reply":
                out.append(scaffold_request_reply(op, msg, name, source, idx))
            else:
                out.append(scaffold_inject(op, msg, name, source, idx))
    return "\n".join(out)


# ─── Load existing test coverage (for --only-missing) ─────────────────────────


def load_existing_op_ids(test_file: str) -> set[str]:
    """Return set of operationIds already covered in a Drift test file."""
    try:
        with open(test_file) as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        print(f"WARNING: Could not read {test_file}: {e}", file=sys.stderr)
        return set()

    covered: set[str] = set()
    for _name, op in (data or {}).get("operations", {}).items():
        if not isinstance(op, dict):
            continue
        target = op.get("target", "")
        parts = target.split(":")
        # target format: source:operationId or source:operationId:messageId
        if len(parts) >= 2:
            covered.add(parts[1])
    return covered


# ─── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract operations and messages from an AsyncAPI 3.x spec.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--spec", required=True, help="Path to AsyncAPI 3.x spec")
    parser.add_argument("--scaffold", action="store_true", help="Emit Drift test stubs instead of summary")
    parser.add_argument("--source", default="async-svc", help="Drift source name for targets (default: async-svc)")
    parser.add_argument(
        "--only-missing", metavar="DRIFT_YAML", help="Only scaffold operations not already in this test file"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        ops, raw = load_operations(args.spec)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except (OSError, yaml.YAMLError) as e:
        print(f"ERROR: Could not parse spec: {e}", file=sys.stderr)
        sys.exit(2)

    if not ops:
        print("No operations found. Check --spec path.", file=sys.stderr)
        sys.exit(2)

    # JSON mode
    if args.json:
        out = []
        for op in ops:
            out.append(
                {
                    "operationId": op["operationId"],
                    "action": op["action"],
                    "channel": op["channel_address"],
                    "executionMode": _execution_mode(op),
                    "hasReply": op["has_reply"],
                    "messages": [
                        {
                            "localId": m["local_id"],
                            "name": m["name"],
                            "payloadRequiredFields": m["payload_required"],
                        }
                        for m in op["messages"]
                    ],
                }
            )
        print(json.dumps(out, indent=2))
        return

    # Scaffold mode
    if args.scaffold:
        existing: set[str] | None = None
        if args.only_missing:
            existing = load_existing_op_ids(args.only_missing)
        print(scaffold_all(ops, args.source, existing))
        return

    # Summary mode
    print(f"Spec: {args.spec}")
    print(f"Operations: {len(ops)}")
    print()
    needs_fill = print_summary(ops)
    if needs_fill:
        print()
        print("⚠  Some messages have no required payload fields — fill in FILL_IN markers manually.")
        sys.exit(1)


if __name__ == "__main__":
    main()
