#!/usr/bin/env -S uv run --project scripts/generate
"""
Clone PactSwift and generate dsl.swift.md from its source.

Shallow-clones surpher/PactSwift, runs tree-sitter over the
relevant source files, and writes the DSL reference document consumed by
the pactflow AI skill.

Usage (from repo root):
    uv run --no-project scripts/generate/dsl_swift.py
    uv run --no-project scripts/generate/dsl_swift.py --check
    uv run --no-project scripts/generate/dsl_swift.py --local-repo /path/to/PactSwift
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import tree_sitter_swift as tsswift
from tree_sitter import Language, Node, Parser

REPO_URL = "https://github.com/surpher/PactSwift.git"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEST_PATH = (
    REPO_ROOT
    / "plugins"
    / "swagger-contract-testing"
    / "skills"
    / "pactflow"
    / "references"
    / "dsl.swift.md"
)

_LANGUAGE = Language(tsswift.language())
_PARSER = Parser(_LANGUAGE)

# ObjC bridge classes to suppress (their Swift counterparts already appear)
_OBJC_PREFIXES = ("Objc", "ObjC", "PF")
# Attributes to strip from output
_STRIP_ATTRS = {"@discardableResult", "@objc", "@JvmStatic", "@available"}


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


def _modifiers_text(src: bytes, node: Node) -> str:
    mods = next((c for c in node.children if c.type == "modifiers"), None)
    return _text(src, mods) if mods else ""


def _is_public(src: bytes, node: Node) -> bool:
    mods = _modifiers_text(src, node)
    return "public" in mods or "open" in mods


def _is_internal_or_private(src: bytes, node: Node) -> bool:
    mods = _modifiers_text(src, node)
    return "private" in mods or "fileprivate" in mods or "internal" in mods


def _keyword(src: bytes, node: Node) -> str:
    """Return class/struct/enum/extension keyword for a class_declaration node."""
    for c in node.children:
        if c.type in ("class", "struct", "enum", "extension", "actor"):
            return _text(src, c)
    return ""


def _type_name(src: bytes, node: Node) -> str:
    """Return the declared type name."""
    for c in node.children:
        if c.type in ("type_identifier", "user_type"):
            return _text(src, c)
    return ""


def _strip_body_attrs(sig: str) -> str:
    """Remove implementation-detail attributes from a signature string."""
    for attr in ("@discardableResult", "@objc", "@_implementationOnly", "@available(*, deprecated", "@available(macOS"):
        sig = sig.replace(attr, "")
    # Collapse multiple spaces
    import re
    sig = re.sub(r"[ \t]+", " ", sig).strip()
    return sig


# ---------------------------------------------------------------------------
# Signature extraction
# ---------------------------------------------------------------------------


def _init_sig(src: bytes, node: Node, indent: str = "    ", prefix: str = "", require_public: bool = False) -> str | None:
    """Format an init_declaration as a one-liner."""
    if _is_internal_or_private(src, node):
        return None
    if require_public and not _is_public(src, node):
        return None
    if "deprecated" in _modifiers_text(src, node):
        return None

    # Collect parameters
    params: list[str] = []
    for c in node.children:
        if c.type == "parameter":
            params.append(_text(src, c))
    params_str = ", ".join(params)

    # Optionality / throws
    throws_str = ""
    for c in node.children:
        if c.type in ("throws", "rethrows"):
            throws_str = f" {_text(src, c)}"

    import re
    mods = _modifiers_text(src, node)
    mods = re.sub(r"@available\([^)]*\)", "", mods).strip()
    display_mods = " ".join(
        w for w in mods.split()
        if w not in ("@discardableResult", "@objc", "convenience", "override")
    )
    mod_prefix = (display_mods + " ") if display_mods else ""

    return f"{indent}{mod_prefix}init({params_str}){throws_str}"


def _func_sig(src: bytes, node: Node, indent: str = "    ") -> str | None:
    """Format a function_declaration as a one-liner."""
    if _is_internal_or_private(src, node):
        return None
    if "deprecated" in _modifiers_text(src, node):
        return None

    name_node = next((c for c in node.children if c.type == "simple_identifier"), None)
    if name_node is None:
        return None
    name = _text(src, name_node)

    # Skip ObjC bridge methods
    if name.startswith("objC"):
        return None

    # Parameters between ( and )
    params: list[str] = []
    in_parens = False
    for c in node.children:
        if c.type == "(":
            in_parens = True
            continue
        if c.type == ")":
            in_parens = False
            continue
        if in_parens and c.type == "parameter":
            params.append(_text(src, c))
    params_str = ", ".join(params)

    # Return type (after ->)
    ret_str = ""
    saw_arrow = False
    for c in node.children:
        if c.type == "->":
            saw_arrow = True
            continue
        if saw_arrow and c.type not in ("function_body", "throws", "rethrows"):
            ret_str = f" -> {_text(src, c)}"
            break

    # async / throws
    async_str = ""
    throws_str = ""
    for c in node.children:
        if c.type == "async":
            async_str = " async"
        if c.type in ("throws", "rethrows"):
            throws_str = f" {_text(src, c)}"

    # Generic type params
    tp_node = next((c for c in node.children if c.type == "type_parameters"), None)
    tp_str = _text(src, tp_node) if tp_node else ""

    # Build modifier prefix, stripping noise
    mods = _modifiers_text(src, node)
    # Remove @available(...) blocks entirely using regex
    import re
    mods = re.sub(r"@available\([^)]*\)", "", mods).strip()
    display_mods = " ".join(
        w for w in mods.split()
        if w not in ("@discardableResult", "@objc", "convenience", "override", "open")
    )
    mod_prefix = (display_mods + " ") if display_mods else ""

    return f"{indent}{mod_prefix}func {name}{tp_str}({params_str}){async_str}{throws_str}{ret_str}"


def _enum_cases(src: bytes, body_node: Node) -> list[str]:
    """Extract case names from an enum body."""
    cases: list[str] = []
    for child in body_node.children:
        if child.type == "enum_entry":
            name_node = next((c for c in child.children if c.type == "simple_identifier"), None)
            if name_node:
                cases.append(f"    case {_text(src, name_node)}")
    return cases


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------


def _class_block(
    src: bytes,
    node: Node,
    *,
    include_inits: bool = True,
    include_funcs: bool = True,
    nested_prefix: str = "",
    skip_public_check: bool = False,
) -> str | None:
    """
    Format a top-level class/struct/open class as a code block.
    Returns None if the type is non-public or an ObjC bridge.
    """
    kw = _keyword(src, node)
    if kw not in ("class", "struct", "enum", "actor"):
        return None

    # Skip if not public (unless parent context already guarantees visibility)
    if not skip_public_check and not _is_public(src, node):
        return None

    name = _type_name(src, node)
    if not name:
        return None

    # Skip ObjC bridge types
    if any(name.startswith(p) for p in _OBJC_PREFIXES):
        return None

    # Inheritance/conformances
    inherit_nodes = [c for c in node.children if c.type in ("inheritance_specifier", "type_inheritance_clause")]
    inherit_str = ""
    if inherit_nodes:
        inherit_text = ", ".join(_text(src, n) for n in inherit_nodes)
        inherit_str = f": {inherit_text}"

    body = next((c for c in node.children if c.type in ("class_body", "enum_class_body")), None)
    members: list[str] = []

    if kw == "enum" and body:
        members.extend(_enum_cases(src, body))

    if body:
        for child in body.children:
            if include_inits and child.type == "init_declaration":
                sig = _init_sig(src, child)
                if sig:
                    members.append(sig)
            elif include_funcs and child.type == "function_declaration":
                sig = _func_sig(src, child)
                if sig:
                    members.append(sig)
            # Nested struct/class/enum inside class body
            elif child.type == "class_declaration":
                nested = _nested_type_block(src, child, parent_name=name)
                if nested:
                    members.append(nested)

    if not members and kw != "enum":
        return None

    inner = "\n".join(members)
    display_name = f"{nested_prefix}{name}" if nested_prefix else name
    return f"{kw} {display_name}{inherit_str} {{\n{inner}\n}}"


def _nested_type_block(src: bytes, node: Node, parent_name: str = "") -> str | None:
    """Format a nested struct/enum/class inside a class body."""
    kw = _keyword(src, node)
    if kw not in ("struct", "enum", "class"):
        return None

    if not _is_public(src, node):
        return None

    name = _type_name(src, node)
    if not name:
        return None
    if any(name.startswith(p) for p in _OBJC_PREFIXES):
        return None

    body = next((c for c in node.children if c.type in ("class_body", "enum_class_body")), None)
    members: list[str] = []

    if kw == "enum" and body:
        members.extend(_enum_cases(src, body))

    if body:
        for child in body.children:
            if child.type == "init_declaration":
                sig = _init_sig(src, child, indent="        ")
                if sig:
                    members.append(sig)
            elif child.type == "function_declaration":
                sig = _func_sig(src, child, indent="        ")
                if sig:
                    members.append(sig)
            elif child.type == "class_declaration":
                deep = _nested_type_block(src, child)
                if deep:
                    members.append("    " + deep.replace("\n", "\n    "))

    if not members and kw != "enum":
        return None

    inner = "\n".join(members)
    return f"    {kw} {name} {{\n{inner}\n    }}"


def _extension_block(
    src: bytes,
    node: Node,
    *,
    extended_type: str,
    include_inits: bool = True,
    include_funcs: bool = True,
    nested_struct_name: str | None = None,
) -> str | None:
    """
    Format members from an extension block.

    If nested_struct_name is given, look for a nested struct by that name and
    return its members formatted as `ExtType.StructName { ... }`.
    Otherwise return top-level methods/inits from the extension.
    """
    kw = _keyword(src, node)
    if kw != "extension":
        return None

    body = next((c for c in node.children if c.type == "class_body"), None)
    if body is None:
        return None

    if nested_struct_name:
        # Find the nested struct declaration inside the extension
        for child in body.children:
            if child.type == "class_declaration":
                n_kw = _keyword(src, child)
                n_name = _type_name(src, child)
                if n_name == nested_struct_name and n_kw in ("struct", "class", "enum"):
                    block = _class_block(src, child, include_inits=include_inits, include_funcs=include_funcs)
                    if block:
                        # Re-prefix with parent.Nested
                        return block.replace(f"{n_kw} {nested_struct_name}", f"{n_kw} {extended_type}.{nested_struct_name}", 1)
        return None

    # Top-level extension methods/inits
    members: list[str] = []
    for child in body.children:
        if include_inits and child.type == "init_declaration":
            sig = _init_sig(src, child)
            if sig:
                members.append(sig)
        elif include_funcs and child.type == "function_declaration":
            sig = _func_sig(src, child)
            if sig:
                members.append(sig)

    if not members:
        return None

    inner = "\n".join(members)
    return f"extension {extended_type} {{\n{inner}\n}}"


def _file_block(repo: Path, rel_path: str, **kwargs) -> str:
    """Parse a Swift source file and return a formatted code block."""
    path = repo / rel_path
    if not path.exists():
        return ""

    src, root = _parse(path)
    parts: list[str] = []

    for child in root.children:
        if child.type != "class_declaration":
            continue

        kw = _keyword(src, child)
        if kw in ("class", "struct", "enum", "actor"):
            block = _class_block(src, child, **kwargs)
            if block:
                parts.append(block)
        elif kw == "extension":
            block = _extension_block(src, child, extended_type=_type_name(src, child), **kwargs)
            if block:
                parts.append(block)

    if not parts:
        return ""

    content = "\n\n".join(parts)
    return f"File: ./{rel_path}\n```swift\n{content}\n```\n"


# ---------------------------------------------------------------------------
# Matcher namespace builder
# (Each matcher is defined as `public extension Matcher { struct Foo { ... } }`)
# ---------------------------------------------------------------------------


def _matcher_structs(repo: Path, matcher_files: list[str]) -> str:
    """Build a single code block showing all Matcher.* nested types."""
    entries: list[str] = []

    for rel_path in matcher_files:
        path = repo / rel_path
        if not path.exists():
            continue
        src, root = _parse(path)

        for top in root.children:
            if top.type != "class_declaration":
                continue
            kw = _keyword(src, top)
            if kw != "extension":
                continue

            # extension Matcher { struct Foo { ... } }
            body = next((c for c in top.children if c.type == "class_body"), None)
            if body is None:
                continue

            for child in body.children:
                if child.type != "class_declaration":
                    continue
                n_kw = _keyword(src, child)
                if n_kw not in ("struct", "enum"):
                    continue
                n_name = _text(src, next((c for c in child.children if c.type in ("type_identifier", "user_type")), child))
                if any(n_name.startswith(p) for p in _OBJC_PREFIXES):
                    continue

                n_body = next((c for c in child.children if c.type in ("class_body", "enum_class_body")), None)
                members: list[str] = []

                if n_kw == "enum" and n_body:
                    members.extend(_enum_cases(src, n_body))

                if n_body:
                    for m in n_body.children:
                        if m.type == "init_declaration":
                            sig = _init_sig(src, m, require_public=True)
                            if sig:
                                members.append(sig)
                        elif m.type == "class_declaration":
                            nested = _nested_type_block(src, m)
                            if nested:
                                members.append(nested)

                if members or n_kw == "enum":
                    inner = "\n".join(members)
                    entries.append(f"{n_kw} Matcher.{n_name} {{\n{inner}\n}}")

    if not entries:
        return ""

    return "```swift\n" + "\n\n".join(entries) + "\n```\n"


# ---------------------------------------------------------------------------
# ExampleGenerator namespace builder
# ---------------------------------------------------------------------------


def _generator_structs(repo: Path, generator_files: list[str]) -> str:
    """Build a single code block showing all ExampleGenerator.* nested types."""
    entries: list[str] = []

    for rel_path in generator_files:
        path = repo / rel_path
        if not path.exists():
            continue
        src, root = _parse(path)

        for top in root.children:
            if top.type != "class_declaration":
                continue
            kw = _keyword(src, top)
            if kw != "extension":
                continue

            body = next((c for c in top.children if c.type == "class_body"), None)
            if body is None:
                continue

            for child in body.children:
                if child.type != "class_declaration":
                    continue
                n_kw = _keyword(src, child)
                if n_kw not in ("struct", "enum"):
                    continue
                n_name = _text(src, next((c for c in child.children if c.type in ("type_identifier", "user_type")), child))
                if any(n_name.startswith(p) for p in _OBJC_PREFIXES):
                    continue

                n_body = next((c for c in child.children if c.type in ("class_body", "enum_class_body")), None)
                members: list[str] = []

                if n_kw == "enum" and n_body:
                    members.extend(_enum_cases(src, n_body))

                if n_body:
                    for m in n_body.children:
                        if m.type == "init_declaration":
                            sig = _init_sig(src, m, require_public=True)
                            if sig:
                                members.append(sig)
                        elif m.type == "class_declaration":
                            nested = _nested_type_block(src, m)
                            if nested:
                                members.append(nested)

                if members or n_kw == "enum":
                    inner = "\n".join(members)
                    entries.append(f"{n_kw} ExampleGenerator.{n_name} {{\n{inner}\n}}")

    if not entries:
        return ""

    return "```swift\n" + "\n\n".join(entries) + "\n```\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

_SRC = "Sources"
_MATCHERS_DIR = f"{_SRC}/Matchers"
_GENERATORS_DIR = f"{_SRC}/ExampleGenerators"


def _section_mock_service(repo: Path) -> str:
    parts = ["## MockService (Consumer Tests)\n"]

    # Primary MockService init + uponReceiving + run (callback)
    ms_path = repo / f"{_SRC}/MockService.swift"
    if ms_path.exists():
        src, root = _parse(ms_path)
        members: list[str] = []
        for top in root.children:
            if top.type != "class_declaration":
                continue
            if _keyword(src, top) not in ("class",):
                continue
            name = _type_name(src, top)
            if name != "MockService":
                continue
            body = next((c for c in top.children if c.type == "class_body"), None)
            if not body:
                continue
            for child in body.children:
                if child.type == "init_declaration":
                    if "internal" in _modifiers_text(src, child):
                        continue
                    sig = _init_sig(src, child)
                    if sig:
                        members.append(sig)
                elif child.type == "function_declaration":
                    sig = _func_sig(src, child)
                    if sig:
                        members.append(sig)
        if members:
            inner = "\n".join(members)
            parts.append(f"File: ./{_SRC}/MockService.swift\n```swift\nopen class MockService {{\n{inner}\n}}\n```\n")

    # Async run (from MockService+Concurrency.swift) — only from the public extension
    async_path = repo / f"{_SRC}/MockService+Concurrency.swift"
    if async_path.exists():
        src, root = _parse(async_path)
        members: list[str] = []
        for top in root.children:
            if top.type != "class_declaration":
                continue
            if _keyword(src, top) != "extension":
                continue
            # Only the public extension block
            if "public" not in _modifiers_text(src, top):
                continue
            body = next((c for c in top.children if c.type == "class_body"), None)
            if not body:
                continue
            for child in body.children:
                if child.type == "function_declaration":
                    sig = _func_sig(src, child)
                    if sig:
                        members.append(sig)
        if members:
            inner = "\n".join(members)
            parts.append(f"File: ./{_SRC}/MockService+Concurrency.swift\n```swift\n// Async/await API (macOS 12+, iOS 15+)\nextension MockService {{\n{inner}\n}}\n```\n")

    return "\n".join(p for p in parts if p)


def _section_interaction(repo: Path) -> str:
    parts = ["## Interaction Builder\n"]

    path = repo / f"{_SRC}/Model/Interaction.swift"
    if not path.exists():
        return ""

    src, root = _parse(path)
    members: list[str] = []

    for top in root.children:
        if top.type != "class_declaration":
            continue
        kw = _keyword(src, top)

        if kw in ("class",) and _type_name(src, top) == "Interaction":
            # Skip — class declaration has no public init
            pass

        if kw == "extension":
            ext_name = _type_name(src, top)
            if ext_name != "Interaction":
                continue
            body = next((c for c in top.children if c.type == "class_body"), None)
            if not body:
                continue
            for child in body.children:
                if child.type == "function_declaration":
                    sig = _func_sig(src, child)
                    if sig and not sig.strip().startswith("func objC"):
                        members.append(sig)

    if members:
        inner = "\n".join(members)
        parts.append(f"File: ./{_SRC}/Model/Interaction.swift\n```swift\nclass Interaction {{\n{inner}\n}}\n```\n")

    return "\n".join(p for p in parts if p)


def _section_matchers(repo: Path) -> str:
    matcher_files = sorted(
        str(p.relative_to(repo))
        for p in (repo / _MATCHERS_DIR).glob("*.swift")
        if p.name != "Matcher.swift"  # namespace placeholder only
    )
    block = _matcher_structs(repo, matcher_files)
    if not block:
        return ""
    return f"## Matchers\n\n{block}"


def _section_generators(repo: Path) -> str:
    generator_files = sorted(
        str(p.relative_to(repo))
        for p in (repo / _GENERATORS_DIR).glob("*.swift")
        if p.name != "ExampleGenerator.swift"  # namespace placeholder only
    )
    block = _generator_structs(repo, generator_files)
    if not block:
        return ""
    return f"## Example Generators\n\n{block}"


def _section_model(repo: Path) -> str:
    parts = ["## Supporting Types\n"]

    # PactHTTPMethod enum
    http_path = repo / f"{_SRC}/Model/PactHTTPMethod.swift"
    if http_path.exists():
        src, root = _parse(http_path)
        for top in root.children:
            if top.type == "class_declaration" and _keyword(src, top) == "enum":
                block = _class_block(src, top)
                if block:
                    parts.append(f"File: ./{_SRC}/Model/PactHTTPMethod.swift\n```swift\n{block}\n```\n")
                break

    # TransferProtocol enum
    tp_path = repo / f"{_SRC}/Model/TransferProtocol.swift"
    if tp_path.exists():
        src, root = _parse(tp_path)
        for top in root.children:
            if top.type == "class_declaration" and _keyword(src, top) == "enum":
                block = _class_block(src, top)
                if block:
                    parts.append(f"File: ./{_SRC}/Model/TransferProtocol.swift\n```swift\n{block}\n```\n")
                break

    # ProviderState struct
    ps_path = repo / f"{_SRC}/Model/ProviderState.swift"
    if ps_path.exists():
        src, root = _parse(ps_path)
        for top in root.children:
            if top.type == "class_declaration" and _keyword(src, top) == "struct":
                if _type_name(src, top) == "ProviderState":
                    block = _class_block(src, top)
                    if block:
                        parts.append(f"File: ./{_SRC}/Model/ProviderState.swift\n```swift\n{block}\n```\n")
                    break

    return "\n".join(p for p in parts if p)


def _section_provider_verifier(repo: Path) -> str:
    parts = ["## Provider Verifier\n"]

    # ProviderVerifier class
    pv_path = repo / f"{_SRC}/ProviderVerifier.swift"
    if pv_path.exists():
        src, root = _parse(pv_path)
        members: list[str] = []
        for top in root.children:
            if top.type != "class_declaration":
                continue
            if _keyword(src, top) == "class" and _type_name(src, top) == "ProviderVerifier":
                body = next((c for c in top.children if c.type == "class_body"), None)
                if body:
                    for child in body.children:
                        if child.type == "init_declaration" and _is_public(src, child):
                            sig = _init_sig(src, child)
                            if sig:
                                members.append(sig)
                        elif child.type == "function_declaration":
                            sig = _func_sig(src, child)
                            if sig:
                                members.append(sig)
        if members:
            inner = "\n".join(members)
            parts.append(f"File: ./{_SRC}/ProviderVerifier.swift\n```swift\npublic final class ProviderVerifier {{\n{inner}\n}}\n```\n")

    # Options struct (from ProviderVerifier+Options.swift)
    opts_path = repo / f"{_SRC}/Model/ProviderVerifier+Options.swift"
    if opts_path.exists():
        src, root = _parse(opts_path)
        for top in root.children:
            if top.type != "class_declaration" or _keyword(src, top) != "extension":
                continue
            body = next((c for c in top.children if c.type == "class_body"), None)
            if not body:
                continue
            # Find the Options struct
            for child in body.children:
                if child.type == "class_declaration" and _keyword(src, child) == "struct" and _type_name(src, child) == "Options":
                    block = _class_block(src, child, skip_public_check=True)
                    if block:
                        parts.append(f"File: ./{_SRC}/Model/ProviderVerifier+Options.swift\n```swift\n// ProviderVerifier.Options and its nested types\n{block.replace('struct Options', 'struct ProviderVerifier.Options', 1)}\n```\n")
                    break

    # Provider struct
    prov_path = repo / f"{_SRC}/Model/ProviderVerifier+Provider.swift"
    if prov_path.exists():
        src, root = _parse(prov_path)
        for top in root.children:
            if top.type != "class_declaration" or _keyword(src, top) != "extension":
                continue
            body = next((c for c in top.children if c.type == "class_body"), None)
            if not body:
                continue
            for child in body.children:
                if child.type == "class_declaration" and _keyword(src, child) == "struct" and _type_name(src, child) == "Provider":
                    block = _class_block(src, child, skip_public_check=True)
                    if block:
                        parts.append(f"File: ./{_SRC}/Model/ProviderVerifier+Provider.swift\n```swift\n{block.replace('struct Provider', 'struct ProviderVerifier.Provider', 1)}\n```\n")
                    break

    # PactBroker
    broker_path = repo / f"{_SRC}/Model/PactBroker.swift"
    if broker_path.exists():
        parts.append(_file_block(repo, f"{_SRC}/Model/PactBroker.swift"))

    # VersionSelector
    vs_path = repo / f"{_SRC}/Model/VersionSelector.swift"
    if vs_path.exists():
        src, root = _parse(vs_path)
        for top in root.children:
            if top.type == "class_declaration" and _keyword(src, top) == "struct" and _type_name(src, top) == "VersionSelector":
                block = _class_block(src, top)
                if block:
                    parts.append(f"File: ./{_SRC}/Model/VersionSelector.swift\n```swift\n{block}\n```\n")
                break

    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def build_doc(repo: Path) -> str:
    sections = [
        "While you already know this, here is a reminder of the key PactSwift"
        " classes and types you will need to use to create a Pact test in Swift"
        " (having omitted deprecated and implementation-detail members):\n",
        _section_mock_service(repo),
        _section_interaction(repo),
        _section_matchers(repo),
        _section_generators(repo),
        _section_model(repo),
        _section_provider_verifier(repo),
    ]
    return "\n\n".join(s for s in sections if s).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI / entrypoint
# ---------------------------------------------------------------------------


def _clone(ref: str, dest: Path) -> None:
    subprocess.run(
        [
            "git",
            "clone",
            "--depth=1",
            f"--branch={ref}",
            REPO_URL,
            str(dest),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default=os.environ.get("PACT_SWIFT_REF", "main"),
        help="Branch or tag to clone (default: $PACT_SWIFT_REF or 'main')",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEST_PATH,
        help=f"Output path (default: {DEST_PATH})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the output file would change (CI mode)",
    )
    parser.add_argument(
        "--local-repo",
        type=Path,
        default=None,
        metavar="PATH",
        help="Use a local checkout instead of cloning (for development)",
    )
    args = parser.parse_args()

    if args.local_repo:
        repo = args.local_repo.resolve()
        doc = build_doc(repo)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "PactSwift"
            _clone(args.ref, repo)
            doc = build_doc(repo)

    if args.check:
        existing = args.output.read_text() if args.output.exists() else ""
        if doc != existing:
            print(f"[check] {args.output} is out of date — run the generator to update", file=sys.stderr)
            sys.exit(1)
        print(f"[check] {args.output} is up to date")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
