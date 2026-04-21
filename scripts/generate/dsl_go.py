#!/usr/bin/env -S uv run --project scripts/generate
"""
Clone pact-go and generate dsl.golang.md from its source.

Shallow-clones pact-foundation/pact-go, runs tree-sitter over the
relevant source files, and writes the DSL reference document consumed by
the pactflow AI skill.

Usage (from repo root):
    uv run --no-project scripts/generate/dsl_go.py
    PACT_GO_REF=v2.4.2 uv run --no-project scripts/generate/dsl_go.py
    uv run --no-project scripts/generate/dsl_go.py --check
    uv run --no-project scripts/generate/dsl_go.py --local-repo /path/to/pact-go
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

import tree_sitter_go as tsgo
from tree_sitter import Language, Node, Parser

REPO_URL = "https://github.com/pact-foundation/pact-go.git"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEST_PATH = (
    REPO_ROOT
    / "plugins"
    / "swagger-contract-testing"
    / "skills"
    / "pactflow"
    / "references"
    / "dsl.golang.md"
)

_LANGUAGE = Language(tsgo.language())
_PARSER = Parser(_LANGUAGE)

_SKIP_METHODS = {"ExecuteTest"}

_GO_BUILTINS = frozenset({
    "bool", "byte", "complex64", "complex128", "error",
    "float32", "float64", "int", "int8", "int16", "int32", "int64",
    "rune", "string", "uint", "uint8", "uint16", "uint32", "uint64", "uintptr",
    "any", "comparable",
})

# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _text(src: bytes, node: Node) -> str:
    return src[node.start_byte : node.end_byte].decode()


def _is_exported(name: str) -> bool:
    return bool(name) and name[0].isupper()


def _parse(path: Path) -> tuple[bytes, Node]:
    src = path.read_bytes()
    tree = _PARSER.parse(src)
    return src, tree.root_node


def _package_name(src: bytes, root: Node) -> str:
    for child in root.children:
        if child.type == "package_clause":
            for c in child.children:
                if c.type == "package_identifier":
                    return _text(src, c)
    return "unknown"


# ---------------------------------------------------------------------------
# Type formatting helpers
# ---------------------------------------------------------------------------


def _struct_fields(src: bytes, struct_node: Node, indent: str = "\t") -> list[str]:
    """Return formatted lines for exported fields in a struct_type node."""
    lines: list[str] = []
    fdl = next(
        (c for c in struct_node.children if c.type == "field_declaration_list"),
        None,
    )
    if fdl is None:
        return lines

    for field in fdl.children:
        if field.type != "field_declaration":
            continue

        # Try to find a field_identifier (named field) vs embedded type
        name_node = next(
            (c for c in field.children if c.type == "field_identifier"), None
        )

        if name_node is not None:
            name = _text(src, name_node)
            if not _is_exported(name):
                continue
            raw = _text(src, field)
            # Strip struct tags
            raw = re.sub(r"`[^`]*`", "", raw)
            # Normalize whitespace: collapse to single space, then tab-prefix
            parts = raw.split()
            lines.append(indent + " ".join(parts))
        else:
            # Embedded type (no field_identifier)
            raw = _text(src, field).strip()
            embedded_name = raw.lstrip("*").split(".")[0]
            if _is_exported(embedded_name):
                lines.append(indent + raw)

    return lines


def _type_spec_text(src: bytes, spec_node: Node) -> str | None:
    name_node = spec_node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if not _is_exported(name):
        return None

    type_node = spec_node.child_by_field_name("type")
    if type_node is None:
        return None

    if type_node.type == "struct_type":
        fields = _struct_fields(src, type_node)
        if fields:
            return "type {} struct {{\n{}\n}}".format(name, "\n".join(fields))
        return f"type {name} struct {{}}"
    else:
        return f"type {name} {_text(src, type_node)}"


def _type_alias_text(src: bytes, alias_node: Node) -> str | None:
    name_node = alias_node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if not _is_exported(name):
        return None
    type_node = alias_node.child_by_field_name("type")
    if type_node is None:
        return None
    return f"type {name} = {_text(src, type_node)}"


def _type_decl(src: bytes, node: Node) -> str | None:
    """Format a type_declaration node, returning None if nothing exported."""
    parts: list[str] = []
    for child in node.children:
        if child.type == "type_spec":
            text = _type_spec_text(src, child)
            if text:
                parts.append(text)
        elif child.type == "type_alias":
            text = _type_alias_text(src, child)
            if text:
                parts.append(text)
    return "\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# Function / method signature helpers
# ---------------------------------------------------------------------------


def _has_unexported_custom_type(src: bytes, node: Node | None) -> bool:
    """Return True if any type_identifier in node is unexported and not a built-in."""
    if node is None:
        return False
    if node.type == "type_identifier":
        name = _text(src, node)
        return not _is_exported(name) and name not in _GO_BUILTINS
    return any(_has_unexported_custom_type(src, c) for c in node.children)


def _receiver_type_exported(src: bytes, receiver_node: Node) -> bool:
    """Return True if the receiver type is exported (starts with uppercase)."""
    for child in receiver_node.children:
        if child.type == "parameter_declaration":
            for c in child.children:
                if c.type == "type_identifier":
                    return _is_exported(_text(src, c))
                if c.type == "pointer_type":
                    for inner in c.children:
                        if inner.type == "type_identifier":
                            return _is_exported(_text(src, inner))
    return False


def _func_sig(src: bytes, node: Node) -> str | None:
    """Format a function_declaration node → 'func Name(params) Result'."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if not _is_exported(name):
        return None

    params_node = node.child_by_field_name("parameters")
    result_node = node.child_by_field_name("result")

    params = _text(src, params_node) if params_node else "()"
    result = (" " + _text(src, result_node)) if result_node else ""

    return f"func {name}{params}{result}"


def _method_sig(src: bytes, node: Node) -> str | None:
    """Format a method_declaration node → 'func (r *T) Name(params) Result'."""
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    name = _text(src, name_node)
    if not _is_exported(name):
        return None
    if name in _SKIP_METHODS:
        return None

    receiver_node = node.child_by_field_name("receiver")
    if receiver_node and not _receiver_type_exported(src, receiver_node):
        return None

    params_node = node.child_by_field_name("parameters")
    result_node = node.child_by_field_name("result")

    if _has_unexported_custom_type(src, params_node) or _has_unexported_custom_type(
        src, result_node
    ):
        return None

    receiver = _text(src, receiver_node) if receiver_node else ""
    params = _text(src, params_node) if params_node else "()"
    result = (" " + _text(src, result_node)) if result_node else ""

    recv_prefix = f"{receiver} " if receiver else ""
    return f"func {recv_prefix}{name}{params}{result}"


# ---------------------------------------------------------------------------
# Const / var helpers
# ---------------------------------------------------------------------------


def _const_spec_text(src: bytes, spec_node: Node) -> str | None:
    name_node = next(
        (c for c in spec_node.children if c.type == "identifier"), None
    )
    if name_node is None:
        return None
    name = _text(src, name_node)
    if not _is_exported(name):
        return None
    # Return the raw spec text (e.g. "V2 SpecificationVersion = \"2.0.0\"")
    raw = _text(src, spec_node)
    return "\t" + " ".join(raw.split())


def _const_decl(src: bytes, node: Node) -> str | None:
    """Format a const_declaration with exported specs only."""
    specs: list[str] = []
    for child in node.children:
        if child.type == "const_spec":
            text = _const_spec_text(src, child)
            if text:
                specs.append(text)
    if not specs:
        return None
    if len(specs) == 1:
        return "const " + specs[0].strip()
    return "const (\n" + "\n".join(specs) + "\n)"


def _var_spec_text(src: bytes, spec_node: Node) -> str | None:
    name_node = next(
        (c for c in spec_node.children if c.type == "identifier"), None
    )
    if name_node is None:
        return None
    name = _text(src, name_node)
    if not _is_exported(name):
        return None
    raw = _text(src, spec_node)
    return "var " + " ".join(raw.split())


def _var_decl(src: bytes, node: Node) -> str | None:
    """Format a var_declaration with exported specs only."""
    parts: list[str] = []
    for child in node.children:
        if child.type == "var_spec":
            text = _var_spec_text(src, child)
            if text:
                parts.append(text)
    return "\n".join(parts) if parts else None


# ---------------------------------------------------------------------------
# File block builder
# ---------------------------------------------------------------------------


def _file_block(repo: Path, rel_path: str) -> str:
    """Generate the annotated code block for one Go source file."""
    path = repo / rel_path
    if not path.exists():
        return ""

    src, root = _parse(path)
    pkg = _package_name(src, root)

    lines: list[str] = [f"package {pkg}", ""]

    for child in root.children:
        if child.type == "function_declaration":
            sig = _func_sig(src, child)
            if sig:
                lines.append(sig)
        elif child.type == "method_declaration":
            sig = _method_sig(src, child)
            if sig:
                lines.append(sig)
        elif child.type == "type_declaration":
            text = _type_decl(src, child)
            if text:
                lines.append(text)
        elif child.type == "const_declaration":
            text = _const_decl(src, child)
            if text:
                lines.append(text)
        elif child.type == "var_declaration":
            text = _var_decl(src, child)
            if text:
                lines.append(text)

    # Remove trailing blank lines
    while lines and not lines[-1]:
        lines.pop()

    content = "\n".join(lines)
    return f"File: ./{rel_path}\n```go\n{content}\n```\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_models(repo: Path) -> str:
    parts = [
        "## Models\n",
        _file_block(repo, "models/pact_file.go"),
        _file_block(repo, "models/provider_state.go"),
    ]
    return "\n".join(p for p in parts if p)


def _section_log(repo: Path) -> str:
    parts = [
        "## Log\n",
        _file_block(repo, "log/log.go"),
    ]
    return "\n".join(p for p in parts if p)


def _section_matchers(repo: Path) -> str:
    parts = [
        "## Matchers\n",
        "### V2 Matchers\n",
        _file_block(repo, "matchers/matcher.go"),
        "### V3 Matchers\n",
        _file_block(repo, "matchers/matcher_v3.go"),
    ]
    return "\n".join(p for p in parts if p)


def _section_consumer(repo: Path) -> str:
    parts = [
        "## Consumer\n",
        "### HTTP V2\n",
        _file_block(repo, "consumer/http_v2.go"),
        "### HTTP V3\n",
        _file_block(repo, "consumer/http_v3.go"),
        "### HTTP V4\n",
        _file_block(repo, "consumer/http_v4.go"),
        "### HTTP Config\n",
        _file_block(repo, "consumer/http.go"),
        "### Interaction\n",
        _file_block(repo, "consumer/interaction.go"),
        "### Request / Response\n",
        _file_block(repo, "consumer/request.go"),
        _file_block(repo, "consumer/response.go"),
    ]
    return "\n".join(p for p in parts if p)


def _section_message(repo: Path) -> str:
    parts = [
        "## Message\n",
        _file_block(repo, "message/message.go"),
        "### V3 Async Message\n",
        _file_block(repo, "message/v3/asynchronous_message.go"),
        "### V3 Sync Message\n",
        _file_block(repo, "message/v3/message.go"),
        "### V4 Sync Message\n",
        _file_block(repo, "message/v4/synchronous_message.go"),
        "### V4 Async Message\n",
        _file_block(repo, "message/v4/asynchronous_message.go"),
    ]
    return "\n".join(p for p in parts if p)


def _section_provider(repo: Path) -> str:
    parts = [
        "## Provider\n",
        _file_block(repo, "provider/verifier.go"),
        _file_block(repo, "provider/verify_request.go"),
        _file_block(repo, "provider/consumer_version_selector.go"),
        _file_block(repo, "provider/transport.go"),
    ]
    return "\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def build_doc(repo: Path) -> str:
    sections = [
        "While you already know this, here is a reminder of the key Pact Go interfaces,"
        " types, structs and methods you will need to use to create a Pact test in"
        " Golang (having omitted deprecated and unadvised methods):\n",
        _section_models(repo),
        _section_log(repo),
        _section_matchers(repo),
        _section_consumer(repo),
        _section_message(repo),
        _section_provider(repo),
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
        default=os.environ.get("PACT_GO_REF", "master"),
        help="Branch or tag to clone (default: $PACT_GO_REF or 'master')",
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
            repo = Path(tmp) / "pact-go"
            _clone(args.ref, repo)
            doc = build_doc(repo)

    if args.check:
        existing = args.output.read_text() if args.output.exists() else ""
        if doc != existing:
            print(
                f"[check] {args.output} is out of date — run the generator to update",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[check] {args.output} is up to date")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
