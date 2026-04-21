#!/usr/bin/env -S uv run --project scripts/generate
"""
Clone pact-php and generate dsl.php.md from its source.

Shallow-clones pact-foundation/pact-php, runs tree-sitter over the
relevant source files, and writes the DSL reference document consumed by
the pactflow AI skill.

Usage (from repo root):
    uv run --no-project scripts/generate/dsl_php.py
    uv run --no-project scripts/generate/dsl_php.py --check
    uv run --no-project scripts/generate/dsl_php.py --local-repo /path/to/pact-php
"""

from __future__ import annotations

from pathlib import Path

import tree_sitter_php as tsphp
from tree_sitter import Language, Parser, Node

from _common import REFERENCES_DIR, clone_shallow, run_main

REPO_URL = "https://github.com/pact-foundation/pact-php.git"
DEST_PATH = REFERENCES_DIR / "dsl.php.md"

_LANGUAGE = Language(tsphp.language_php())
_PARSER = Parser(_LANGUAGE)

# Methods to suppress (internal / noise)
_SKIP_METHODS = frozenset({"newInteraction"})

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _text(src: bytes, node: Node) -> str:
    return src[node.start_byte : node.end_byte].decode()


def _parse(path: Path) -> tuple[bytes, Node]:
    src = path.read_bytes()
    tree = _PARSER.parse(src)
    return src, tree.root_node


def _find_all(node: Node, *types: str):
    if node.type in types:
        yield node
    for child in node.children:
        yield from _find_all(child, *types)


def _visibility(src: bytes, method_node: Node) -> str:
    for child in method_node.children:
        if child.type == "visibility_modifier":
            return _text(src, child)
    return ""


def _is_public(src: bytes, method_node: Node) -> bool:
    vis = _visibility(src, method_node)
    return vis == "public" or vis == ""


# ---------------------------------------------------------------------------
# Member formatting
# ---------------------------------------------------------------------------


def _method_sig(src: bytes, node: Node, indent: str = "    ", in_interface: bool = False) -> str | None:
    if not in_interface and not _is_public(src, node):
        return None
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if name in _SKIP_METHODS:
        return None

    params_node = node.child_by_field_name("parameters")
    rt_node = node.child_by_field_name("return_type")

    params = _text(src, params_node) if params_node else "()"
    ret = (": " + _text(src, rt_node)) if rt_node else ""

    # Build modifier prefix: skip for interfaces
    if in_interface:
        prefix = ""
    else:
        vis = _visibility(src, node)
        mods = [vis] if vis else []
        for child in node.children:
            if child.type in ("abstract_modifier", "static_modifier", "final_modifier"):
                t = _text(src, child)
                if t not in mods:
                    mods.append(t)
        mods = [m for m in mods if m not in ("abstract", "final")]
        prefix = (" ".join(mods) + " ") if mods else ""

    return f"{indent}{prefix}function {name}{params}{ret};"


# ---------------------------------------------------------------------------
# Declaration block builders
# ---------------------------------------------------------------------------


def _interface_block(src: bytes, node: Node, rel_path: str) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    # Extends clause — base_clause is a child node but not a named field in PHP grammar
    # The node text already includes the 'extends' keyword
    base_clause = next((c for c in node.children if c.type == "base_clause"), None)
    extends_str = (" " + _text(src, base_clause)) if base_clause else ""

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for md in _find_all(body, "method_declaration"):
            sig = _method_sig(src, md, indent="    ", in_interface=True)
            if sig:
                members.append(sig)

    inner = "\n".join(members)
    return f"interface {name}{extends_str}\n{{\n{inner}\n}}"


def _class_block(src: bytes, node: Node, rel_path: str, include_abstract: bool = False) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    # Class modifier (abstract)
    is_abstract = any(c.type == "abstract_modifier" for c in node.children)
    if is_abstract and not include_abstract:
        return None

    # Implements / extends clauses — not named fields in PHP grammar, search by type
    base_clause = next((c for c in node.children if c.type == "base_clause"), None)
    interfaces = next((c for c in node.children if c.type == "class_interface_clause"), None)
    # base_clause and class_interface_clause text already include the keywords
    prefix_mods = "abstract " if is_abstract else ""
    extends_str = (" " + _text(src, base_clause)) if base_clause else ""
    impl_str = (" " + _text(src, interfaces)) if interfaces else ""

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for md in _find_all(body, "method_declaration"):
            sig = _method_sig(src, md, indent="    ")
            if sig:
                members.append(sig)

    if not members:
        return None

    inner = "\n".join(members)
    return f"{prefix_mods}class {name}{extends_str}{impl_str}\n{{\n{inner}\n}}"


def _trait_block(src: bytes, node: Node) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for md in _find_all(body, "method_declaration"):
            sig = _method_sig(src, md, indent="    ")
            if sig:
                members.append(sig)

    if not members:
        return None

    inner = "\n".join(members)
    return f"trait {name}\n{{\n{inner}\n}}"


# ---------------------------------------------------------------------------
# File block builder
# ---------------------------------------------------------------------------


def _ns_name(src: bytes, root: Node) -> str:
    for child in root.children:
        if child.type == "namespace_definition":
            nm = child.child_by_field_name("name")
            if nm:
                return _text(src, nm)
    return ""


def _file_block(
    repo: Path,
    rel_path: str,
    *,
    include_abstract: bool = False,
    trait_only: bool = False,
) -> str:
    path = repo / rel_path
    if not path.exists():
        return ""

    src, root = _parse(path)

    parts: list[str] = []
    for child in root.children:
        if child.type == "interface_declaration":
            block = _interface_block(src, child, rel_path)
            if block:
                parts.append(block)
        elif child.type == "class_declaration" and not trait_only:
            block = _class_block(src, child, rel_path, include_abstract=include_abstract)
            if block:
                parts.append(block)
        elif child.type == "trait_declaration":
            block = _trait_block(src, child)
            if block:
                parts.append(block)

    if not parts:
        return ""

    content = "\n\n".join(parts)
    return f"File: ./{rel_path}\n```php\n{content}\n```\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

_SRC = "src/PhpPact"


def _section_config(repo: Path) -> str:
    parts = [
        "## Config\n",
        _file_block(repo, f"{_SRC}/Config/PactConfigInterface.php"),
        _file_block(repo, f"{_SRC}/Standalone/MockService/MockServerConfigInterface.php"),
    ]
    return "\n".join(p for p in parts if p)


def _section_matchers(repo: Path) -> str:
    parts = [
        "## Matchers\n",
        _file_block(repo, f"{_SRC}/Consumer/Matcher/Matcher.php"),
    ]
    return "\n".join(p for p in parts if p)


def _section_http_consumer(repo: Path) -> str:
    parts = [
        "## HTTP Consumer\n",
        _file_block(repo, f"{_SRC}/Consumer/BuilderInterface.php"),
        _file_block(repo, f"{_SRC}/Consumer/InteractionBuilder.php"),
        # ConsumerRequest model (assembled from traits)
        _file_block(repo, f"{_SRC}/Consumer/Model/Interaction/MethodTrait.php", trait_only=True),
        _file_block(repo, f"{_SRC}/Consumer/Model/Interaction/PathTrait.php", trait_only=True),
        _file_block(repo, f"{_SRC}/Consumer/Model/Interaction/QueryTrait.php", trait_only=True),
        _file_block(repo, f"{_SRC}/Consumer/Model/Interaction/HeadersTrait.php", trait_only=True),
        _file_block(repo, f"{_SRC}/Consumer/Model/Interaction/BodyTrait.php", trait_only=True),
        _file_block(repo, f"{_SRC}/Consumer/Model/Interaction/StatusTrait.php", trait_only=True),
    ]
    return "\n".join(p for p in parts if p)


def _section_message_consumer(repo: Path) -> str:
    parts = [
        "## Message Consumer\n",
        _file_block(repo, f"{_SRC}/Consumer/AbstractMessageBuilder.php", include_abstract=True),
        _file_block(repo, f"{_SRC}/Consumer/MessageBuilder.php"),
        _file_block(repo, f"{_SRC}/SyncMessage/SyncMessageBuilder.php"),
    ]
    return "\n".join(p for p in parts if p)


def _section_provider(repo: Path) -> str:
    parts = [
        "## Provider Verifier\n",
        _file_block(repo, f"{_SRC}/Standalone/ProviderVerifier/Verifier.php"),
        _file_block(repo, f"{_SRC}/Standalone/ProviderVerifier/Model/VerifierConfigInterface.php"),
        _file_block(repo, f"{_SRC}/Standalone/ProviderVerifier/Model/Source/UrlInterface.php"),
        _file_block(repo, f"{_SRC}/Standalone/ProviderVerifier/Model/Source/BrokerInterface.php"),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def build_doc(repo: Path) -> str:
    sections = [
        "While you already know this, here is a reminder of the key PhpPact classes,"
        " interfaces, and methods you will need to use to create a Pact test in PHP"
        " (having omitted deprecated and implementation-detail members):\n",
        _section_config(repo),
        _section_matchers(repo),
        _section_http_consumer(repo),
        _section_message_consumer(repo),
        _section_provider(repo),
    ]
    return "\n\n".join(s for s in sections if s).rstrip() + "\n"


if __name__ == "__main__":
    run_main(build_doc, DEST_PATH, REPO_URL, "pact-php", "PACT_PHP_REF", "master", __doc__)
