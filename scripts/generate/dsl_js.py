#!/usr/bin/env -S uv run --project scripts/generate
"""
Clone pact-js and generate dsl.typescript.md and dsl.javascript.md from its source.

Shallow-clones pact-foundation/pact-js, runs tree-sitter over the
relevant source files, and writes DSL reference documents consumed by
the pactflow AI skill.

Usage (from repo root):
    uv run --no-project scripts/generate/dsl_js.py
    PACT_JS_REF=v16.3.0 uv run --no-project scripts/generate/dsl_js.py
    uv run --no-project scripts/generate/dsl_js.py --check
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

REPO_URL = "https://github.com/pact-foundation/pact-js.git"
REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_DIR = (
    REPO_ROOT
    / "plugins"
    / "swagger-contract-testing"
    / "skills"
    / "pactflow"
    / "references"
)
DEST_TS = REFERENCES_DIR / "dsl.typescript.md"
DEST_JS = REFERENCES_DIR / "dsl.javascript.md"

_LANGUAGE = Language(tsts.language_typescript())
_DEPRECATED_RE = re.compile(r"@deprecated", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Clone helpers
# ---------------------------------------------------------------------------


def _clone(ref: str) -> Path:
    """Shallow-clone pact-js at *ref* into a temp directory."""
    tmp = Path(tempfile.mkdtemp(prefix="pact-js-"))
    print(f"Cloning {REPO_URL} @ {ref} → {tmp} ...")  # noqa: T201
    subprocess.run(
        ["git", "clone", "--depth=1", "--branch", ref, REPO_URL, str(tmp)],
        check=True,
    )
    return tmp


# ---------------------------------------------------------------------------
# Tree-sitter helpers
# ---------------------------------------------------------------------------


def _make_parser() -> Parser:
    return Parser(_LANGUAGE)


def _parse_file(path: Path) -> tuple[bytes, Node]:
    source = path.read_bytes()
    return source, _make_parser().parse(source).root_node


def _text(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _norm(text: str) -> str:
    """Collapse internal whitespace to a single space."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Deprecation detection
# ---------------------------------------------------------------------------


def _preceding_comment(source: bytes, node: Node) -> str:
    """Return the text of the block comment immediately before this node."""
    start = node.start_byte
    prefix = source[:start].rstrip()
    if prefix.endswith(b"*/"):
        block_start = prefix.rfind(b"/*")
        if block_start >= 0:
            return prefix[block_start:].decode("utf-8", errors="replace")
    return ""


def _is_deprecated(source: bytes, node: Node) -> bool:
    return bool(_DEPRECATED_RE.search(_preceding_comment(source, node)))


# ---------------------------------------------------------------------------
# AST navigation helpers
# ---------------------------------------------------------------------------


def _unwrap_export(node: Node) -> Node | None:
    """Return the declaration wrapped by an export_statement, or the node itself if it's a declaration."""
    _DECL_TYPES = (
        "class_declaration",
        "interface_declaration",
        "type_alias_declaration",
        "function_declaration",
        "lexical_declaration",
        "ambient_declaration",
    )
    if node.type == "export_statement":
        for child in node.children:
            if child.type in _DECL_TYPES:
                return child
        return None
    return node if node.type in _DECL_TYPES else None


def _decl_name(source: bytes, decl: Node) -> str:
    name_node = decl.child_by_field_name("name")
    if name_node:
        return _text(source, name_node)
    if decl.type == "lexical_declaration":
        for child in decl.children:
            if child.type == "variable_declarator":
                n = child.child_by_field_name("name")
                if n:
                    return _text(source, n)
    return ""


def _find_decl(source: bytes, root: Node, decl_type: str, name: str) -> Node | None:
    for child in root.children:
        decl = _unwrap_export(child)
        if decl and decl.type == decl_type and _decl_name(source, decl) == name:
            return decl
    return None


# ---------------------------------------------------------------------------
# Parameter formatting
# ---------------------------------------------------------------------------


_PARAM_MODIFIER_RE = re.compile(r"\b(private|public|protected|readonly)\s+")


def _format_params_ts(source: bytes, params_node: Node | None) -> str:
    """Return parameter string with TypeScript type annotations (normalized to one line)."""
    if not params_node:
        return "()"
    text = _text(source, params_node)
    # Strip constructor-parameter accessibility modifiers (private/public/protected/readonly)
    text = _PARAM_MODIFIER_RE.sub("", text)
    # Normalise to single line
    return _norm(text) if "\n" in text else text


def _extract_param_names(source: bytes, params_node: Node) -> list[str]:
    """Extract just parameter names (no types) from a parameter node."""
    if params_node.type == "identifier":
        return [_text(source, params_node)]
    if params_node.type == "required_parameter":
        pattern = params_node.child_by_field_name("pattern")
        return [_text(source, pattern)] if pattern else []
    if params_node.type == "optional_parameter":
        pattern = params_node.child_by_field_name("pattern")
        return [_text(source, pattern)] if pattern else []
    if params_node.type != "formal_parameters":
        return []

    parts: list[str] = []
    for child in params_node.children:
        if child.type in ("(", ")", ",", "comment"):
            continue
        if child.type == "required_parameter":
            pattern = child.child_by_field_name("pattern")
            if pattern:
                parts.append(_text(source, pattern))
        elif child.type == "optional_parameter":
            pattern = child.child_by_field_name("pattern")
            if pattern:
                parts.append(_text(source, pattern))
        elif child.type == "rest_parameter":
            for c in child.children:
                if c.type == "identifier":
                    parts.append(f"...{_text(source, c)}")
                    break
        elif child.type == "identifier":
            parts.append(_text(source, child))
        elif child.type == "assignment_pattern":
            left = child.child_by_field_name("left")
            if left:
                parts.append(_text(source, left))
    return parts


def _format_params_js(source: bytes, params_node: Node | None) -> str:
    """Return parameter string without TypeScript type annotations."""
    if not params_node:
        return "()"
    return "(" + ", ".join(_extract_param_names(source, params_node)) + ")"


# ---------------------------------------------------------------------------
# Method signature formatting
# ---------------------------------------------------------------------------

_SKIP_ACCESSIBILITY = {"private", "protected"}


def _is_public_method(source: bytes, method_node: Node) -> bool:
    for child in method_node.children:
        if child.type == "accessibility_modifier":
            return _text(source, child) not in _SKIP_ACCESSIBILITY
    return True


_SKIP_METHOD_NAMES = {"setup", "toJSON"}


def _should_skip_method(source: bytes, method_node: Node) -> bool:
    if not _is_public_method(source, method_node):
        return True
    if _is_deprecated(source, method_node):
        return True
    name_node = method_node.child_by_field_name("name")
    if not name_node:
        return True
    name = _text(source, name_node)
    return name.startswith("_") or name in _SKIP_METHOD_NAMES


def _method_sig_ts(source: bytes, method_node: Node, indent: int = 4) -> str:
    name_node = method_node.child_by_field_name("name")
    type_params = method_node.child_by_field_name("type_parameters")
    params = method_node.child_by_field_name("parameters")
    ret = method_node.child_by_field_name("return_type")

    name = _text(source, name_node) if name_node else "?"
    tp = _text(source, type_params) if type_params else ""
    p = _format_params_ts(source, params)
    r = _norm(_text(source, ret)) if ret else ""

    pad = " " * indent
    return f"{pad}{name}{tp}{p}{r};"


def _method_sig_js(source: bytes, method_node: Node, indent: int = 4) -> str:
    name_node = method_node.child_by_field_name("name")
    params = method_node.child_by_field_name("parameters")

    name = _text(source, name_node) if name_node else "?"
    p = _format_params_js(source, params)

    pad = " " * indent
    return f"{pad}{name}{p};"


# ---------------------------------------------------------------------------
# Arrow function (const export) signature formatting
# ---------------------------------------------------------------------------


def _arrow_params(value: Node) -> Node | None:
    """Return the parameter(s) node of an arrow_function, trying multiple strategies."""
    # Try the documented field name first
    param = value.child_by_field_name("parameter")
    if param is not None:
        return param
    # Some grammar versions use "parameters"
    param = value.child_by_field_name("parameters")
    if param is not None:
        return param
    # Fall back: scan named children for formal_parameters or identifier
    for child in value.children:
        if child.type == "formal_parameters":
            return child
        if child.type == "identifier" and child.is_named:
            return child
    return None


def _arrow_sig_ts(source: bytes, name: str, vd_node: Node, indent: int = 4) -> str:
    """Format `export const name = <T>(params): ReturnType => ...` for TypeScript."""
    value = vd_node.child_by_field_name("value")
    if not value or value.type != "arrow_function":
        return ""

    type_params = value.child_by_field_name("type_parameters")
    param = _arrow_params(value)
    ret = value.child_by_field_name("return_type")

    tp = _text(source, type_params) if type_params else ""
    p = _format_params_ts(source, param)
    # strip leading ": " from return type annotation
    ret_type = _norm(_text(source, ret))[2:] if ret else "void"

    pad = " " * indent
    return f"{pad}const {name}: {tp}{p} => {ret_type};"


def _arrow_sig_js(source: bytes, name: str, vd_node: Node, indent: int = 4) -> str:
    """Format `export const name = (params) => ...` without types for JavaScript."""
    value = vd_node.child_by_field_name("value")
    if not value or value.type != "arrow_function":
        return ""

    param = _arrow_params(value)
    p = _format_params_js(source, param)

    pad = " " * indent
    return f"{pad}function {name}{p};"


# ---------------------------------------------------------------------------
# Class block builder
# ---------------------------------------------------------------------------


def _class_block(
    source: bytes, root: Node, class_name: str, *, ts: bool = True
) -> str:
    decl = _find_decl(source, root, "class_declaration", class_name)
    lines: list[str] = [f"class {class_name} {{"]
    if not decl:
        lines.append("}")
        return "\n".join(lines)

    body = decl.child_by_field_name("body")
    if not body:
        lines.append("}")
        return "\n".join(lines)

    seen: set[str] = set()
    for child in body.children:
        if child.type != "method_definition":
            continue
        if _should_skip_method(source, child):
            continue
        name_node = child.child_by_field_name("name")
        if not name_node:
            continue
        name = _text(source, name_node)
        if name in seen:
            continue
        seen.add(name)
        lines.append(_method_sig_ts(source, child) if ts else _method_sig_js(source, child))

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MatchersV3 namespace block (collected from module-level exports)
# ---------------------------------------------------------------------------

_MATCHERS_V3_SKIP = {
    "isMatcher",
    "matcherValueOrString",
    "extractPayload",
    "validateExample",
}


def _matchers_v3_block(source: bytes, root: Node, *, ts: bool = True) -> str:
    lines: list[str] = []

    for child in root.children:
        if child.type != "export_statement":
            continue
        if _is_deprecated(source, child):
            continue

        decl = _unwrap_export(child)
        if not decl:
            continue

        if decl.type == "function_declaration":
            name_node = decl.child_by_field_name("name")
            if not name_node:
                continue
            name = _text(source, name_node)
            if name in _MATCHERS_V3_SKIP or name.startswith("_"):
                continue

            if ts:
                tp = decl.child_by_field_name("type_parameters")
                params = decl.child_by_field_name("parameters")
                ret = decl.child_by_field_name("return_type")
                tp_text = _text(source, tp) if tp else ""
                p = _format_params_ts(source, params)
                r = _norm(_text(source, ret)) if ret else ""
                lines.append(f"    function {name}{tp_text}{p}{r};")
            else:
                params = decl.child_by_field_name("parameters")
                p = _format_params_js(source, params)
                lines.append(f"    function {name}{p};")

        elif decl.type == "lexical_declaration":
            for vd in decl.children:
                if vd.type != "variable_declarator":
                    continue
                name_node = vd.child_by_field_name("name")
                if not name_node:
                    continue
                name = _text(source, name_node)
                if name in _MATCHERS_V3_SKIP or name.startswith("_"):
                    continue

                value = vd.child_by_field_name("value")
                if not value:
                    continue

                if value.type == "arrow_function":
                    sig = _arrow_sig_ts(source, name, vd, indent=4) if ts else _arrow_sig_js(source, name, vd, indent=4)
                    if sig:
                        lines.append(sig)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Interface / type-alias extraction (TypeScript output only)
# ---------------------------------------------------------------------------


def _interface_text(source: bytes, root: Node, iface_name: str) -> str:
    """Return source text of an interface declaration (without export keyword)."""
    for child in root.children:
        decl = _unwrap_export(child)
        if decl and decl.type == "interface_declaration":
            name_node = decl.child_by_field_name("name")
            if name_node and _text(source, name_node) == iface_name:
                return _text(source, decl)
    return f"interface {iface_name} {{}}"


def _type_alias_text(source: bytes, root: Node, type_name: str) -> str:
    """Return source text of a type alias (without export keyword)."""
    for child in root.children:
        decl = _unwrap_export(child)
        if decl and decl.type == "type_alias_declaration":
            name_node = decl.child_by_field_name("name")
            if name_node and _text(source, name_node) == type_name:
                return _text(source, decl)
    return f"type {type_name} = unknown;"


# ---------------------------------------------------------------------------
# Interface method-signature formatting (for type-state interfaces like V4)
# ---------------------------------------------------------------------------


def _interface_method_sig_ts(source: bytes, method_node: Node, indent: int = 4) -> str:
    """Format an interface method_signature for TypeScript output."""
    name_node = method_node.child_by_field_name("name")
    type_params = method_node.child_by_field_name("type_parameters")
    params = method_node.child_by_field_name("parameters")
    ret = method_node.child_by_field_name("return_type")

    name = _text(source, name_node) if name_node else "?"
    tp = _text(source, type_params) if type_params else ""
    p = _format_params_ts(source, params)
    r = _norm(_text(source, ret)) if ret else ""

    pad = " " * indent
    return f"{pad}{name}{tp}{p}{r};"


def _interface_method_sig_js(source: bytes, method_node: Node, indent: int = 4) -> str:
    """Format an interface method_signature for JavaScript output (no types)."""
    name_node = method_node.child_by_field_name("name")
    params = method_node.child_by_field_name("parameters")

    name = _text(source, name_node) if name_node else "?"
    p = _format_params_js(source, params)

    pad = " " * indent
    return f"{pad}{name}{p};"


def _interface_block_js(source: bytes, root: Node, iface_name: str) -> str:
    """Build an interface as a JS pseudo-object shape (method names + params, no types)."""
    for child in root.children:
        decl = _unwrap_export(child)
        if not decl or decl.type != "interface_declaration":
            continue
        name_node = decl.child_by_field_name("name")
        if not name_node or _text(source, name_node) != iface_name:
            continue
        body = decl.child_by_field_name("body")
        if not body:
            return f"// {iface_name}: {{}}"
        lines = [f"// {iface_name}:", "{"]
        for item in body.children:
            if item.type == "method_signature":
                lines.append(_interface_method_sig_js(source, item))
        lines.append("}")
        return "\n".join(lines)
    return f"// {iface_name}: {{}}"


# ---------------------------------------------------------------------------
# Parse helper
# ---------------------------------------------------------------------------


def _parse(repo: Path, rel_path: str) -> tuple[bytes, Node]:
    return _parse_file(repo / "src" / rel_path)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _section_v3_pact(repo: Path, *, ts: bool = True) -> str:
    source, root = _parse(repo, "v3/pact.ts")
    block = _class_block(source, root, "PactV3", ts=ts)
    lang = "typescript" if ts else "javascript"
    import_line = (
        '// import { PactV3 } from "@pact-foundation/pact";'
        if ts
        else '// const { PactV3 } = require("@pact-foundation/pact");'
    )
    return f"""\
File: src/v3/pact.ts
```{lang}
{import_line}
{block}
```"""


def _section_v3_matchers(repo: Path, *, ts: bool = True) -> str:
    source, root = _parse(repo, "v3/matchers.ts")
    entries = _matchers_v3_block(source, root, ts=ts)
    lang = "typescript" if ts else "javascript"
    import_line = (
        '// import { MatchersV3 } from "@pact-foundation/pact";'
        if ts
        else '// const { MatchersV3 } = require("@pact-foundation/pact");'
    )
    return f"""\
File: src/v3/matchers.ts
```{lang}
{import_line}
namespace MatchersV3 {{
{entries}
}}
```"""


def _section_v3_xml(repo: Path, *, ts: bool = True) -> str:
    builder_src, builder_root = _parse(repo, "v3/xml/xmlBuilder.ts")
    builder_block = _class_block(builder_src, builder_root, "XmlBuilder", ts=ts)

    elem_src, elem_root = _parse(repo, "v3/xml/xmlElement.ts")
    elem_block = _class_block(elem_src, elem_root, "XmlElement", ts=ts)

    lang = "typescript" if ts else "javascript"

    extra = ""
    if ts:
        try:
            opts_text = _interface_text(elem_src, elem_root, "EachLikeOptions")
            extra = f"\n\n{opts_text}"
        except Exception:
            pass

    return f"""\
File: src/v3/xml/xmlBuilder.ts
```{lang}
{builder_block}
```

File: src/v3/xml/xmlElement.ts
```{lang}
{elem_block}{extra}
```"""


def _section_v4(repo: Path, *, ts: bool = True) -> str:
    """V4 API: PactV4 class + type-state builder interfaces for HTTP and messages."""
    v4_src, v4_root = _parse(repo, "v4/index.ts")
    http_src, http_root = _parse(repo, "v4/http/types.ts")
    msg_src, msg_root = _parse(repo, "v4/message/types.ts")

    pactv4_block = _class_block(v4_src, v4_root, "PactV4", ts=ts)
    lang = "typescript" if ts else "javascript"
    import_line = (
        '// import { PactV4 } from "@pact-foundation/pact";'
        if ts
        else '// const { PactV4 } = require("@pact-foundation/pact");'
    )

    _HTTP_IFACES = (
        "V4UnconfiguredInteraction",
        "V4InteractionWithRequest",
        "V4InteractionWithResponse",
        "V4RequestBuilder",
        "V4ResponseBuilder",
    )
    _MSG_IFACES = (
        "V4UnconfiguredAsynchronousMessage",
        "V4AsynchronousMessageWithContent",
        "V4AsynchronousMessageBuilder",
    )

    if ts:
        opts_text = _interface_text(http_src, http_root, "PactV4Options")
        http_ifaces = "\n\n".join(
            _interface_text(http_src, http_root, n) for n in _HTTP_IFACES
        )
        msg_ifaces = "\n\n".join(
            _interface_text(msg_src, msg_root, n) for n in _MSG_IFACES
        )
        return f"""\
File: src/v4/index.ts
```{lang}
{import_line}
{pactv4_block}
```

File: src/v4/http/types.ts  (type-state chain for HTTP interactions)
```{lang}
{opts_text}

{http_ifaces}
```

File: src/v4/message/types.ts  (async message interactions)
```{lang}
{msg_ifaces}
```"""

    # JavaScript output: show chain as pseudo-code + simplified object shapes
    chain_comment = """\
// V4 HTTP interaction builder chain:
// pact.addInteraction()
//   .given(state, params)          // optional, repeatable
//   .uponReceiving(description)
//   .withRequest(method, path, (b) => { b.query(...); b.jsonBody(...); })
//   .willRespondWith(status, (b) => { b.headers(...); b.jsonBody(...); })
//   .executeTest(async (mockserver) => { ... });
//
// Async message chain:
// pact.addAsynchronousInteraction()
//   .given(state)
//   .expectsToReceive(description, (b) => { b.withJSONContent(...); })
//   .executeTest(async (m) => { ... });"""

    http_shapes = "\n\n".join(
        _interface_block_js(http_src, http_root, n)
        for n in ("V4UnconfiguredInteraction", "V4RequestBuilder", "V4ResponseBuilder")
    )
    msg_shapes = "\n\n".join(
        _interface_block_js(msg_src, msg_root, n)
        for n in ("V4UnconfiguredAsynchronousMessage", "V4AsynchronousMessageBuilder")
    )

    return f"""\
File: src/v4/index.ts
```{lang}
{import_line}
{pactv4_block}
```

File: src/v4/http/types.ts
```{lang}
{chain_comment}

{http_shapes}
```

File: src/v4/message/types.ts
```{lang}
{msg_shapes}
```"""


def _section_v2_interaction(repo: Path, *, ts: bool = True) -> str:
    source, root = _parse(repo, "dsl/interaction.ts")
    block = _class_block(source, root, "Interaction", ts=ts)
    lang = "typescript" if ts else "javascript"

    if ts:
        ifaces = "\n\n".join(
            _interface_text(source, root, n)
            for n in ("RequestOptions", "ResponseOptions", "InteractionObject")
        )
        return f"""\
File: src/dsl/interaction.ts
```{lang}
{ifaces}

{block}
```"""

    return f"""\
File: src/dsl/interaction.ts
```{lang}
{block}
```"""


def _section_v2_options(repo: Path) -> str:
    source, root = _parse(repo, "dsl/options.ts")
    pact_opts = _interface_text(source, root, "PactV2Options")
    return f"""\
File: src/dsl/options.ts
```typescript
{pact_opts}
```"""


def _section_state_handler_types(repo: Path) -> str:
    source, root = _parse(repo, "dsl/verifier/proxy/types.ts")
    parts: list[str] = []
    for iface_name in ("StateHandlers", "ProviderState"):
        try:
            parts.append(_interface_text(source, root, iface_name))
        except Exception:
            pass
    for type_name in ("StateAction", "StateFunc", "StateFuncWithSetup", "StateHandler"):
        try:
            parts.append(_type_alias_text(source, root, type_name))
        except Exception:
            pass
    return f"""\
File: src/dsl/verifier/proxy/types.ts
```typescript
{chr(10).join(parts)}
```"""


def _section_verifier(repo: Path, *, ts: bool = True) -> str:
    source, root = _parse(repo, "dsl/verifier/verifier.ts")
    block = _class_block(source, root, "Verifier", ts=ts)
    lang = "typescript" if ts else "javascript"
    import_line = (
        '// import { Verifier } from "@pact-foundation/pact";'
        if ts
        else '// const { Verifier } = require("@pact-foundation/pact");'
    )
    return f"""\
File: src/dsl/verifier/verifier.ts
```{lang}
{import_line}
{block}
```"""


def _read_example(path: Path, max_lines: int = 80) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8").splitlines()[:max_lines])


def _section_examples(repo: Path, *, ts: bool = True) -> str:
    lang = "typescript" if ts else "javascript"

    # V3 consumer example
    if ts:
        v3_consumer_path = repo / "examples" / "v3" / "typescript" / "test" / "user.spec.ts"
        src_v3_consumer = "examples/v3/typescript/test/user.spec.ts"
    else:
        v3_consumer_path = repo / "examples" / "v3" / "e2e" / "test" / "consumer.spec.js"
        src_v3_consumer = "examples/v3/e2e/test/consumer.spec.js"

    # V4 consumer example (TypeScript only in the repo, usable for both)
    v4_consumer_path = repo / "examples" / "v4" / "typescript" / "test" / "get-dog.spec.ts"
    src_v4_consumer = "examples/v4/typescript/test/get-dog.spec.ts"

    # Provider example (JS)
    provider_path = repo / "examples" / "v3" / "e2e" / "test" / "provider.spec.js"
    src_provider = "examples/v3/e2e/test/provider.spec.js"

    v3_consumer_text = _read_example(v3_consumer_path)
    v4_consumer_text = _read_example(v4_consumer_path)
    provider_text = _read_example(provider_path)

    return f"""\
---

## V3 Consumer Test ({lang.capitalize()})

> Source: [`{src_v3_consumer}`]({src_v3_consumer})

```{lang}
{v3_consumer_text}
```

---

## V4 Consumer Test (TypeScript)

> Source: [`{src_v4_consumer}`]({src_v4_consumer})

```typescript
{v4_consumer_text}
```

---

## Provider Verification

> Source: [`{src_provider}`]({src_provider})

```javascript
{provider_text}
```"""


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------


def build_doc(repo: Path, *, ts: bool = True) -> str:
    lang_name = "TypeScript" if ts else "JavaScript"
    sections = [
        f"While you already know this, here is a reminder of the Pact-JS classes"
        f" and methods you will need to use to create a Pact test in {lang_name}"
        f" (having omitted deprecated and unadvised methods):\n",
        f"> **Auto-generated** from pact-js source by"
        f" `scripts/generate/dsl_js.py` in pact-agent-skills."
        f" Do not edit this file directly — run the workflow or the script instead.\n",
        "## V3 API\n",
        _section_v3_pact(repo, ts=ts),
        _section_v3_matchers(repo, ts=ts),
        _section_v3_xml(repo, ts=ts),
        "## V4 API\n",
        _section_v4(repo, ts=ts),
        "## V2 (Legacy) DSL\n",
        _section_v2_interaction(repo, ts=ts),
    ]

    if ts:
        sections.append(_section_v2_options(repo))
        sections.append(_section_state_handler_types(repo))

    sections.append(_section_verifier(repo, ts=ts))
    sections.append(_section_examples(repo, ts=ts))

    return "\n\n".join(s.rstrip() for s in sections if s) + "\n"


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> int:
    """Clone pact-js, generate dsl.typescript.md and dsl.javascript.md, write or check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref",
        default=os.getenv("PACT_JS_REF", "master"),
        help="Branch/tag to clone (default: $PACT_JS_REF or 'master')",
    )
    parser.add_argument(
        "--output-ts",
        default=str(DEST_TS),
        help="TypeScript output path",
    )
    parser.add_argument(
        "--output-js",
        default=str(DEST_JS),
        help="JavaScript output path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if either file would change (use in CI)",
    )
    parser.add_argument(
        "--local-repo",
        default=None,
        help="Use a local pact-js checkout instead of cloning (for development)",
    )
    args = parser.parse_args()

    out_ts = Path(args.output_ts)
    out_js = Path(args.output_js)

    if args.local_repo:
        repo = Path(args.local_repo)
        cleanup_repo = False
    else:
        repo = _clone(args.ref)
        cleanup_repo = True
    try:
        content_ts = build_doc(repo, ts=True)
        content_js = build_doc(repo, ts=False)
    finally:
        if cleanup_repo:
            import shutil

            shutil.rmtree(repo, ignore_errors=True)

    if args.check:
        up_to_date = True
        if not out_ts.exists() or out_ts.read_text(encoding="utf-8") != content_ts:
            print(f"✗ {out_ts} is out of date")  # noqa: T201
            up_to_date = False
        if not out_js.exists() or out_js.read_text(encoding="utf-8") != content_js:
            print(f"✗ {out_js} is out of date")  # noqa: T201
            up_to_date = False
        if up_to_date:
            print("✓ dsl.typescript.md and dsl.javascript.md are up to date")  # noqa: T201
            return 0
        print(  # noqa: T201
            "Run: uv run --no-project scripts/generate/dsl_js.py"
        )
        return 1

    out_ts.parent.mkdir(parents=True, exist_ok=True)
    out_ts.write_text(content_ts, encoding="utf-8")
    print(f"Written: {out_ts}")  # noqa: T201

    out_js.parent.mkdir(parents=True, exist_ok=True)
    out_js.write_text(content_js, encoding="utf-8")
    print(f"Written: {out_js}")  # noqa: T201

    return 0


if __name__ == "__main__":
    sys.exit(main())
