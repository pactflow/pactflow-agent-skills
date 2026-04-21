#!/usr/bin/env -S uv run --project scripts/generate
"""
Clone pact-jvm and generate dsl.kotlin.md and dsl.java.md from its source.

Shallow-clones pact-foundation/pact-jvm, runs tree-sitter over the
relevant Kotlin and Java source files, and writes DSL reference documents
consumed by the pactflow AI skill.

Usage (from repo root):
    uv run --no-project scripts/generate/dsl_jvm.py
    uv run --no-project scripts/generate/dsl_jvm.py --check
    uv run --no-project scripts/generate/dsl_jvm.py --local-repo /path/to/pact-jvm
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

import tree_sitter_kotlin as tskotlin
import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser

from _common import REFERENCES_DIR, clone_shallow

REPO_URL = "https://github.com/pact-foundation/pact-jvm.git"
DEST_KOTLIN = REFERENCES_DIR / "dsl.kotlin.md"
DEST_JAVA = REFERENCES_DIR / "dsl.java.md"

_KT_LANGUAGE = Language(tskotlin.language())
_KT_PARSER = Parser(_KT_LANGUAGE)

_JAVA_LANGUAGE = Language(tsjava.language())
_JAVA_PARSER = Parser(_JAVA_LANGUAGE)

# Methods to suppress — implementation details / noise
_KT_SKIP_METHODS = frozenset({"putObjectPrivate", "putArrayPrivate", "toString"})
_JAVA_SKIP_METHODS = frozenset({"getPactDslObject", "getPactDslJsonArray"})

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _text(src: bytes, node: Node) -> str:
    return src[node.start_byte : node.end_byte].decode()


def _parse_kt(path: Path) -> tuple[bytes, Node]:
    src = path.read_bytes()
    tree = _KT_PARSER.parse(src)
    return src, tree.root_node


def _parse_java(path: Path) -> tuple[bytes, Node]:
    src = path.read_bytes()
    tree = _JAVA_PARSER.parse(src)
    return src, tree.root_node


def _find_all(node: Node, *types: str):
    if node.type in types:
        yield node
    for child in node.children:
        yield from _find_all(child, *types)


# ---------------------------------------------------------------------------
# Kotlin helpers
# ---------------------------------------------------------------------------


def _kt_is_private_or_internal(src: bytes, node: Node) -> bool:
    """Return True if the function/property has private, protected, or internal visibility."""
    mods = next((c for c in node.children if c.type == "modifiers"), None)
    if mods is None:
        return False
    for child in mods.children:
        if child.type == "visibility_modifier":
            vis = _text(src, child)
            if vis in ("private", "protected", "internal"):
                return True
    return False


def _kt_return_type(src: bytes, fn_node: Node) -> str:
    """Extract return type text after the ':' in a function declaration."""
    colon_seen = False
    for child in fn_node.children:
        if child.type == ":":
            colon_seen = True
            continue
        if colon_seen and child.type not in ("function_body",):
            return _text(src, child)
    return ""


def _kt_fun_sig(src: bytes, node: Node, indent: str = "    ") -> str | None:
    """Format a Kotlin function_declaration as a single-line signature."""
    if _kt_is_private_or_internal(src, node):
        return None
    name_node = next((c for c in node.children if c.type == "identifier"), None)
    if name_node is None:
        return None
    name = _text(src, name_node)
    if name in _KT_SKIP_METHODS:
        return None
    params_node = next((c for c in node.children if c.type == "function_value_parameters"), None)
    params = _text(src, params_node) if params_node else "()"
    ret = _kt_return_type(src, node)
    ret_str = f": {ret}" if ret else ""
    return f"{indent}fun {name}{params}{ret_str}"


def _kt_class_keyword(src: bytes, node: Node) -> str:
    """Return 'class', 'interface', or '' for a class_declaration."""
    kw = next((c for c in node.children if c.type in ("class", "interface", "object")), None)
    return _text(src, kw) if kw else ""


def _kt_is_annotation_class(src: bytes, node: Node) -> bool:
    mods = next((c for c in node.children if c.type == "modifiers"), None)
    if mods is None:
        return False
    return any(
        c.type == "class_modifier" and _text(src, c) == "annotation"
        for c in mods.children
    )


def _kt_class_block(src: bytes, node: Node, include_companion: bool = False) -> str | None:
    """
    Format a Kotlin class_declaration as a code block.
    Returns None if the class has no relevant public functions.
    """
    if _kt_is_annotation_class(src, node):
        return None

    kw = _kt_class_keyword(src, node)
    if not kw:
        return None

    name_node = next((c for c in node.children if c.type == "identifier"), None)
    if name_node is None:
        return None
    name = _text(src, name_node)

    # Primary constructor
    ctor_node = next((c for c in node.children if c.type == "primary_constructor"), None)
    ctor_str = _text(src, ctor_node) if ctor_node else ""

    # Supertype list
    super_node = next((c for c in node.children if c.type == "delegation_specifiers"), None)
    super_str = f" : {_text(src, super_node)}" if super_node else ""

    body = next((c for c in node.children if c.type == "class_body"), None)
    members: list[str] = []

    if body:
        for child in body.children:
            if child.type == "function_declaration":
                sig = _kt_fun_sig(src, child)
                if sig:
                    members.append(sig)
            elif child.type == "companion_object" and include_companion:
                comp_body = next((c for c in child.children if c.type == "class_body"), None)
                if comp_body:
                    comp_funs: list[str] = []
                    for fn in comp_body.children:
                        if fn.type == "function_declaration":
                            sig = _kt_fun_sig(src, fn, indent="        ")
                            if sig:
                                comp_funs.append(sig)
                    if comp_funs:
                        members.append("    companion object {")
                        members.extend(comp_funs)
                        members.append("    }")

    if not members and kw != "interface":
        return None

    inner = "\n".join(members)
    return f"{kw} {name}{ctor_str}{super_str} {{\n{inner}\n}}"


def _kt_annotation_class_block(src: bytes, node: Node) -> str | None:
    """Format a Kotlin annotation class as a single-line declaration."""
    if not _kt_is_annotation_class(src, node):
        return None
    name_node = next((c for c in node.children if c.type == "identifier"), None)
    if name_node is None:
        return None
    name = _text(src, name_node)
    ctor = next((c for c in node.children if c.type == "primary_constructor"), None)
    ctor_str = _text(src, ctor) if ctor else ""
    return f"annotation class {name}{ctor_str}"


def _kt_file_block(
    repo: Path,
    rel_path: str,
    *,
    include_companion: bool = False,
    annotations_only: bool = False,
) -> str:
    path = repo / rel_path
    if not path.exists():
        return ""

    src, root = _parse_kt(path)
    parts: list[str] = []

    for child in root.children:
        if child.type == "class_declaration":
            if annotations_only:
                block = _kt_annotation_class_block(src, child)
            else:
                block = _kt_class_block(src, child, include_companion=include_companion)
            if block:
                parts.append(block)

    if not parts:
        return ""

    content = "\n\n".join(parts)
    return f"File: ./{rel_path}\n```kotlin\n{content}\n```\n"


# ---------------------------------------------------------------------------
# Java helpers
# ---------------------------------------------------------------------------


def _java_is_public(src: bytes, node: Node) -> bool:
    mods = next((c for c in node.children if c.type == "modifiers"), None)
    if mods is None:
        return False
    return "public" in _text(src, mods)


def _java_is_static(src: bytes, node: Node) -> bool:
    mods = next((c for c in node.children if c.type == "modifiers"), None)
    if mods is None:
        return False
    return "static" in _text(src, mods)


def _java_method_sig(src: bytes, node: Node, indent: str = "    ") -> str | None:
    if not _java_is_public(src, node):
        return None
    name_node = next((c for c in node.children if c.type == "identifier"), None)
    if name_node is None:
        return None
    name = _text(src, name_node)
    if name in _JAVA_SKIP_METHODS:
        return None

    # Return type: first non-modifiers named child before identifier
    ret_node = None
    for c in node.children:
        if c.type == "modifiers":
            continue
        if c.type == "identifier":
            break
        if c.is_named:
            ret_node = c

    ret = _text(src, ret_node) if ret_node else "void"
    params_node = next((c for c in node.children if c.type == "formal_parameters"), None)
    params = _text(src, params_node) if params_node else "()"

    mods_node = next((c for c in node.children if c.type == "modifiers"), None)
    mods_text = _text(src, mods_node) if mods_node else ""
    is_static = "static" in mods_text
    static_str = "static " if is_static else ""

    return f"{indent}public {static_str}{ret} {name}{params};"


def _java_class_block(src: bytes, node: Node) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)

    body = node.child_by_field_name("body")
    members: list[str] = []
    if body:
        for m in _find_all(body, "method_declaration"):
            # Only direct children, not nested
            if m.parent != body:
                continue
            sig = _java_method_sig(src, m)
            if sig:
                members.append(sig)

    if not members:
        return None

    inner = "\n".join(members)
    return f"class {name} {{\n{inner}\n}}"


def _java_file_block(repo: Path, rel_path: str) -> str:
    path = repo / rel_path
    if not path.exists():
        return ""

    src, root = _parse_java(path)
    parts: list[str] = []

    for child in _find_all(root, "class_declaration"):
        block = _java_class_block(src, child)
        if block:
            parts.append(block)
            break  # one class per file

    if not parts:
        return ""

    content = "\n\n".join(parts)
    return f"File: ./{rel_path}\n```java\n{content}\n```\n"


# ---------------------------------------------------------------------------
# Kotlin section builders
# ---------------------------------------------------------------------------

_CONSUMER_KT = "consumer/src/main/kotlin/au/com/dius/pact/consumer"
_PROVIDER_KT = "provider/src/main/kotlin/au/com/dius/pact/provider"
_JUNIT5_CONSUMER_KT = "consumer/junit5/src/main/kotlin/au/com/dius/pact/consumer/junit5"
_JUNIT5_PROVIDER_KT = "provider/junit5/src/main/kotlin/au/com/dius/pact/provider/junit5"


def _kt_section_http_consumer(repo: Path) -> str:
    parts = [
        "## HTTP Consumer DSL\n",
        _kt_file_block(repo, f"{_CONSUMER_KT}/ConsumerPactBuilder.kt", include_companion=True),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslWithProvider.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslWithState.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslRequestWithoutPath.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslRequestWithPath.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslResponse.kt"),
    ]
    return "\n".join(p for p in parts if p)


def _kt_section_body_dsl(repo: Path) -> str:
    parts = [
        "## Body / Matching DSL\n",
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslJsonBody.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactDslJsonArray.kt"),
    ]
    return "\n".join(p for p in parts if p)


def _kt_section_message_consumer(repo: Path) -> str:
    parts = [
        "## Message Consumer DSL\n",
        _kt_file_block(repo, f"{_CONSUMER_KT}/MessagePactBuilder.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/SynchronousMessagePactBuilder.kt"),
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/SynchronousMessageInteractionBuilder.kt"),
    ]
    return "\n".join(p for p in parts if p)


def _kt_section_v4_builder(repo: Path) -> str:
    parts = [
        "## V4 Pact Builder\n",
        _kt_file_block(repo, f"{_CONSUMER_KT}/dsl/PactBuilder.kt"),
    ]
    return "\n".join(p for p in parts if p)


def _kt_section_junit5_consumer(repo: Path) -> str:
    parts = [
        "## JUnit 5 Consumer Annotations\n",
        _kt_file_block(repo, f"{_JUNIT5_CONSUMER_KT}/PactTestFor.kt", annotations_only=True),
    ]
    return "\n".join(p for p in parts if p)


def _kt_section_provider(repo: Path) -> str:
    parts = [
        "## Provider Annotations & Verification\n",
        _kt_file_block(repo, f"{_PROVIDER_KT}/junitsupport/Provider.kt", annotations_only=True),
        _kt_file_block(repo, f"{_PROVIDER_KT}/junitsupport/Consumer.kt", annotations_only=True),
        _kt_file_block(repo, f"{_JUNIT5_PROVIDER_KT}/PactVerificationContext.kt"),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Java section builders
# ---------------------------------------------------------------------------

_CONSUMER_JAVA = "consumer/src/main/java/au/com/dius/pact/consumer/dsl"


def _java_section_lambda_dsl(repo: Path) -> str:
    parts = [
        "## Lambda DSL Entry Points\n",
        _java_file_block(repo, f"{_CONSUMER_JAVA}/LambdaDsl.java"),
    ]
    return "\n".join(p for p in parts if p)


def _java_section_lambda_body(repo: Path) -> str:
    parts = [
        "## Lambda DSL Body Builders\n",
        _java_file_block(repo, f"{_CONSUMER_JAVA}/LambdaDslObject.java"),
        _java_file_block(repo, f"{_CONSUMER_JAVA}/LambdaDslJsonBody.java"),
        _java_file_block(repo, f"{_CONSUMER_JAVA}/LambdaDslJsonArray.java"),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def build_kotlin_doc(repo: Path) -> str:
    sections = [
        "While you already know this, here is a reminder of the key pact-jvm Kotlin"
        " classes and methods you will need to use to create a Pact test in Kotlin"
        " (having omitted deprecated and implementation-detail members):\n",
        _kt_section_http_consumer(repo),
        _kt_section_body_dsl(repo),
        _kt_section_message_consumer(repo),
        _kt_section_v4_builder(repo),
        _kt_section_junit5_consumer(repo),
        _kt_section_provider(repo),
    ]
    return "\n\n".join(s for s in sections if s).rstrip() + "\n"


def build_java_doc(repo: Path) -> str:
    sections = [
        "While you already know this, here is a reminder of the key pact-jvm Java"
        " lambda DSL classes and methods you will need to use to create a Pact test"
        " in Java (having omitted deprecated and implementation-detail members):\n",
        _java_section_lambda_dsl(repo),
        _java_section_lambda_body(repo),
    ]
    return "\n\n".join(s for s in sections if s).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI / entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default=os.environ.get("PACT_JVM_REF", "master"),
        help="Branch or tag to clone (default: $PACT_JVM_REF or 'master')",
    )
    parser.add_argument(
        "--output-kotlin",
        type=Path,
        default=DEST_KOTLIN,
        help=f"Kotlin output path (default: {DEST_KOTLIN})",
    )
    parser.add_argument(
        "--output-java",
        type=Path,
        default=DEST_JAVA,
        help=f"Java output path (default: {DEST_JAVA})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if either output file would change (CI mode)",
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
        kotlin_doc = build_kotlin_doc(repo)
        java_doc = build_java_doc(repo)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "pact-jvm"
            clone_shallow(REPO_URL, args.ref, repo)
            kotlin_doc = build_kotlin_doc(repo)
            java_doc = build_java_doc(repo)

    if args.check:
        up_to_date = True
        for path, content in [(args.output_kotlin, kotlin_doc), (args.output_java, java_doc)]:
            existing = path.read_text() if path.exists() else ""
            if content != existing:
                print(f"[check] {path} is out of date — run the generator to update", file=sys.stderr)
                up_to_date = False
        if up_to_date:
            print("[check] dsl.kotlin.md and dsl.java.md are up to date")
        return 0 if up_to_date else 1

    for path, content in [(args.output_kotlin, kotlin_doc), (args.output_java, java_doc)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        print(f"Wrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
