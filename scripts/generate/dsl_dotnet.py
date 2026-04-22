#!/usr/bin/env -S uv run --project scripts/generate
"""
Clone pact-net and generate dsl.dotnet.md from its source.

Shallow-clones pact-foundation/pact-net, runs tree-sitter over the
relevant source files, and writes the DSL reference document consumed by
the pactflow AI skill.

Usage (from repo root):
    uv run --no-project scripts/generate/dsl_dotnet.py
    PACT_NET_REF=5.0.0 uv run --no-project scripts/generate/dsl_dotnet.py
    uv run --no-project scripts/generate/dsl_dotnet.py --check
    uv run --no-project scripts/generate/dsl_dotnet.py --local-repo /path/to/pact-net
"""

from __future__ import annotations

import re
from pathlib import Path

import tree_sitter_c_sharp as tscs
from tree_sitter import Language, Node, Parser

from _common import REFERENCES_DIR, clone_shallow, run_main

REPO_URL = "https://github.com/pact-foundation/pact-net.git"
DEST_PATH = REFERENCES_DIR / "dsl.dotnet.md"

_LANGUAGE = Language(tscs.language())
_PARSER = Parser(_LANGUAGE)

# Properties to suppress (implementation details / noise)
_SKIP_PROPS = frozenset({"Scenarios"})
# Methods to suppress
_SKIP_METHODS = frozenset({"WriteLine", "Dispose"})

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _text(src: bytes, node: Node) -> str:
    return src[node.start_byte : node.end_byte].decode()


def _parse(path: Path) -> tuple[bytes, Node]:
    src = path.read_bytes()
    tree = _PARSER.parse(src)
    return src, tree.root_node


def _modifiers_text(src: bytes, node: Node) -> list[str]:
    return [_text(src, c) for c in node.children if c.type == "modifier"]


def _is_public(src: bytes, node: Node) -> bool:
    return "public" in _modifiers_text(src, node)


def _accessor_summary(src: bytes, accessor_list: Node) -> str:
    """Reduce a full accessor_list to a compact form like '{ get; }' or '{ get; set; }'."""
    has_get = any(
        _text(src, c) == "get"
        for c in accessor_list.children
        if c.type == "accessor_declaration"
        for kw in c.children
        if kw.type in ("get", "identifier") and _text(src, kw) == "get"
    )
    has_set = any(
        _text(src, c) == "set"
        for c in accessor_list.children
        if c.type == "accessor_declaration"
        for kw in c.children
        if kw.type in ("set", "identifier") and _text(src, kw) == "set"
    )
    # simpler: just look for 'get' / 'set' keywords in children
    tokens = []
    for c in accessor_list.children:
        if c.type == "accessor_declaration":
            for kw in c.children:
                t = _text(src, kw)
                if t in ("get", "set"):
                    tokens.append(t + ";")
                    break
    if tokens:
        return "{ " + " ".join(tokens) + " }"
    # fallback: raw text stripped of block bodies
    raw = _text(src, accessor_list)
    raw = re.sub(r"\{[^}]*\}", ";", raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Member formatting
# ---------------------------------------------------------------------------


def _prop_sig(src: bytes, node: Node, indent: str = "    ", in_interface: bool = False) -> str | None:
    if not in_interface and not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    type_node = node.child_by_field_name("type")
    acc_node = node.child_by_field_name("accessors")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if name in _SKIP_PROPS:
        return None
    type_str = _text(src, type_node) if type_node else "?"
    acc_str = _accessor_summary(src, acc_node) if acc_node else "{ get; }"
    mods = _modifiers_text(src, node)
    mods_str = (" ".join(m for m in mods if m not in ("override", "virtual", "abstract")) + " ") if (mods and not in_interface) else ""
    return f"{indent}{mods_str}{type_str} {name} {acc_str}"


def _method_sig(src: bytes, node: Node, indent: str = "    ", in_interface: bool = False) -> str | None:
    if not in_interface and not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if name in _SKIP_METHODS:
        return None
    returns_node = node.child_by_field_name("returns")
    params_node = node.child_by_field_name("parameters")
    type_params_node = node.child_by_field_name("type_parameters")

    ret = _text(src, returns_node) if returns_node else "void"
    params = _text(src, params_node) if params_node else "()"
    tp = _text(src, type_params_node) if type_params_node else ""
    mods = _modifiers_text(src, node)
    mods_str = (" ".join(m for m in mods if m not in ("override", "virtual", "sealed", "abstract")) + " ") if (mods and not in_interface) else ""
    return f"{indent}{mods_str}{ret} {name}{tp}{params};"


def _ctor_sig(src: bytes, node: Node, indent: str = "    ") -> str | None:
    if not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    params_node = node.child_by_field_name("parameters")
    if name_node is None:
        return None
    name = _text(src, name_node)
    params = _text(src, params_node) if params_node else "()"
    return f"{indent}public {name}{params};"


# ---------------------------------------------------------------------------
# Declaration block builders
# ---------------------------------------------------------------------------


def _interface_block(src: bytes, node: Node, indent: str = "") -> str | None:
    if not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    # Base list
    base_list = node.child_by_field_name("bases")
    bases_str = (" : " + _text(src, base_list).lstrip(": ").strip()) if base_list else ""

    # Generic type params
    tp_node = node.child_by_field_name("type_parameters")
    tp_str = _text(src, tp_node) if tp_node else ""

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for m in body.children:
            if m.type == "method_declaration":
                sig = _method_sig(src, m, indent="        ", in_interface=True)
                if sig:
                    members.append(sig)
            elif m.type == "property_declaration":
                sig = _prop_sig(src, m, indent="        ", in_interface=True)
                if sig:
                    members.append(sig)

    inner = "\n".join(members)
    return f"{indent}    public interface {name}{tp_str}{bases_str}\n{indent}    {{\n{inner}\n{indent}    }}"


def _class_block(src: bytes, node: Node, indent: str = "") -> str | None:
    if not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    mods = _modifiers_text(src, node)
    mods_str = (" ".join(m for m in mods) + " ") if mods else ""

    base_list = node.child_by_field_name("bases")
    bases_str = (" : " + _text(src, base_list).lstrip(": ").strip()) if base_list else ""

    tp_node = node.child_by_field_name("type_parameters")
    tp_str = _text(src, tp_node) if tp_node else ""

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for m in body.children:
            if m.type == "property_declaration":
                sig = _prop_sig(src, m, indent="        ")
                if sig:
                    members.append(sig)
            elif m.type == "constructor_declaration":
                sig = _ctor_sig(src, m, indent="        ")
                if sig:
                    members.append(sig)
            elif m.type == "method_declaration":
                sig = _method_sig(src, m, indent="        ")
                if sig:
                    members.append(sig)

    inner = "\n".join(members)
    return f"{indent}    {mods_str}class {name}{tp_str}{bases_str}\n{indent}    {{\n{inner}\n{indent}    }}"


def _enum_block(src: bytes, node: Node, indent: str = "") -> str | None:
    if not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for m in body.children:
            if m.type == "enum_member_declaration":
                val_node = m.child_by_field_name("name")
                if val_node:
                    members.append("        " + _text(src, val_node))

    inner = ",\n".join(members)
    return f"{indent}    public enum {name}\n{indent}    {{\n{inner}\n{indent}    }}"


# ---------------------------------------------------------------------------
# Namespace + file block builders
# ---------------------------------------------------------------------------


def _ns_block(src: bytes, ns_node: Node) -> str | None:
    """Format one namespace_declaration into a code block fragment."""
    name_node = ns_node.child_by_field_name("name")
    ns_name = _text(src, name_node) if name_node else "unknown"

    body = ns_node.child_by_field_name("body")
    if body is None:
        return None

    parts: list[str] = []
    for child in body.children:
        if child.type == "interface_declaration":
            block = _interface_block(src, child)
            if block:
                parts.append(block)
        elif child.type == "class_declaration":
            block = _class_block(src, child)
            if block:
                parts.append(block)
        elif child.type == "enum_declaration":
            block = _enum_block(src, child)
            if block:
                parts.append(block)

    if not parts:
        return None

    inner = "\n\n".join(parts)
    return f"namespace {ns_name}\n{{\n{inner}\n}}"


def _file_block(repo: Path, rel_path: str) -> str:
    """Generate the annotated code block for one C# source file."""
    path = repo / rel_path
    if not path.exists():
        return ""

    src, root = _parse(path)

    ns_blocks: list[str] = []
    for child in root.children:
        if child.type == "namespace_declaration":
            block = _ns_block(src, child)
            if block:
                ns_blocks.append(block)

    if not ns_blocks:
        return ""

    content = "\n\n".join(ns_blocks)
    return f"File: ./{rel_path}\n```csharp\n{content}\n```\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

# Abstractions root
_ABSTR = "src/PactNet.Abstractions"
_IMPL = "src/PactNet"


def _section_matchers(repo: Path) -> str:
    parts = [
        "## Matchers\n",
        _file_block(repo, f"{_ABSTR}/Matchers/IMatcher.cs"),
        _file_block(repo, f"{_ABSTR}/Matchers/Match.cs"),
    ]
    return "\n".join(p for p in parts if p)


def _section_pact(repo: Path) -> str:
    parts = [
        "## Pact\n",
        _file_block(repo, f"{_ABSTR}/IPact.cs"),
        _file_block(repo, f"{_ABSTR}/Pact.cs"),
        _file_block(repo, f"{_ABSTR}/PactConfig.cs"),
        _file_block(repo, f"{_ABSTR}/LogLevel.cs"),
        _file_block(repo, f"{_ABSTR}/ProviderState.cs"),
        _file_block(repo, f"{_ABSTR}/IConsumerContext.cs"),
    ]
    return "\n".join(p for p in parts if p)


def _section_http_consumer(repo: Path) -> str:
    parts = [
        "## HTTP Consumer\n",
        _file_block(repo, f"{_ABSTR}/IPactBuilder.cs"),
        _file_block(repo, f"{_ABSTR}/IRequestBuilder.cs"),
        _file_block(repo, f"{_ABSTR}/IResponseBuilder.cs"),
    ]
    return "\n".join(p for p in parts if p)


def _section_message_consumer(repo: Path) -> str:
    parts = [
        "## Message Consumer\n",
        _file_block(repo, f"{_ABSTR}/IMessagePactBuilder.cs"),
        _file_block(repo, f"{_ABSTR}/IMessageBuilder.cs"),
        _file_block(repo, f"{_ABSTR}/IConfiguredMessageVerifier.cs"),
    ]
    return "\n".join(p for p in parts if p)


def _section_extensions(repo: Path) -> str:
    parts = [
        "## Extension Methods\n",
        _file_block(repo, f"{_IMPL}/PactExtensions.cs"),
    ]
    return "\n".join(p for p in parts if p)


def _section_provider(repo: Path) -> str:
    parts = [
        "## Provider Verifier\n",
        _file_block(repo, f"{_ABSTR}/Verifier/IPactVerifier.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/IPactVerifierSource.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/IPactBrokerOptions.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/IPactBrokerPublishOptions.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/PactVerifierConfig.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/ConsumerVersionSelector.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/Messaging/IMessageScenarios.cs"),
        _file_block(repo, f"{_ABSTR}/Verifier/Messaging/IMessageScenarioBuilder.cs"),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def build_doc(repo: Path) -> str:
    sections = [
        "While you already know this, here is a reminder of the key PactNet interfaces,"
        " types, and methods you will need to use to create a Pact test in .NET"
        " (having omitted deprecated and implementation-detail members):\n",
        _section_matchers(repo),
        _section_pact(repo),
        _section_http_consumer(repo),
        _section_message_consumer(repo),
        _section_extensions(repo),
        _section_provider(repo),
    ]
    return "\n\n".join(s for s in sections if s).rstrip() + "\n"


if __name__ == "__main__":
    run_main(build_doc, DEST_PATH, REPO_URL, "pact-net", "PACT_NET_REF", "master", __doc__)
