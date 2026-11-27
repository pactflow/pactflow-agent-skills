#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml~=6.0",
#   "jsonref~=1.0",
#   "jsonschema>=4",
# ]
# ///
"""
consumer_coverage.py — consumer coverage artifact (schema 1.0.0) from a discovery manifest.

The code sets the denominator: coverage items come from the provider operations the consumer's code
calls (the manifest). Pact interactions say which items are Tested. A provider specification, when
given, only adds detail to operations the code already calls.

Discovery (an agent or code-intelligence tool) writes a manifest tied to a commit; this script is a
plain, deterministic calculation over that manifest: the same inputs always give the same output
(no timestamps, no random ids). It NEVER fails the build: it always exits 0.

Usage:
  uv run consumer_coverage.py --manifest consumer-manifest.json --pacts "pacts/*.json" \\
      [--spec provider-openapi.yaml] [--locations full|hashed|none] \\
      [--exclude-statuses 418 ...] [--pairwise-cap 20] [--verifications v.json] [--out coverage-artifact.json]

Manifest format: see references/consumer-manifest.md.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import itertools
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
MODEL = "consumer-fixed-1"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
DEFAULT_PAIRWISE_CAP = 20
DEFAULT_LARGE_ENUM_LIMIT = 5
MAX_CANDIDATES = 20000
# handledStatuses the code treats as a class: any client error, or any non-2xx. Tested by any matching interaction.
BLANKET_ERROR = {"NON-2XX", "ERROR"}
KNOWN_CALL_KEYS = {
    "notes",
    "method",
    "path",
    "callSite",
    "successStatus",
    "handledStatuses",
    "handlers",
    "nearestTest",
    "inputs",
    "responseFields",
    "unresolvedReason",
    "readsNothing",
    "passThrough",
}
KNOWN_INPUT_KEYS = {"parameters", "body", "headers"}
KNOWN_PARAM_KEYS = {"name", "in", "values", "optional", "notes"}

Json = dict[str, Any]


# ─── helpers ───────────────────────────────────────────────────────────────────


def _sha(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:n]


def _norm_template(path: str) -> str:
    """Path template with parameter names erased, so `/p/{id}` and `/p/{productId}` compare equal."""
    return re.sub(r"\{[^}]*\}|:[A-Za-z_]\w*", "{}", path).rstrip("/") or "/"


def _template_regex(path: str) -> re.Pattern[str]:
    parts = re.split(r"(\{[^}]*\})", path)
    body = "".join("[^/]+" if p.startswith("{") else re.escape(p) for p in parts)
    return re.compile(f"^{body}$")


def _is_success(status: str) -> bool:
    return bool(re.fullmatch(r"2\d\d|2XX", status.upper()))


def _status_matches(actual: int, wanted: str) -> bool:
    w = wanted.upper()
    if w == "2XX":
        return 200 <= actual < 300
    if w == "4XX":
        return 400 <= actual < 500
    if w in BLANKET_ERROR:
        return not 200 <= actual < 300
    return str(actual) == w


def _exclusion_reason(status: str, policy_excluded: set[str]) -> str | None:
    s = status.upper()
    if s in policy_excluded:
        return f"status {status} excluded by policy (excludeStatuses)"
    if s == "4XX" or s in BLANKET_ERROR:
        return None
    if s == "DEFAULT":
        return "default response: not a specific status the code can handle (default model)"
    if re.fullmatch(r"[1-5]XX", s):
        return f"status-code range {status}: not measured by the default model"
    if s.startswith("5"):
        return "5xx response: server errors are excluded by the default model"
    if s.startswith("3"):
        return "3xx response: redirects are excluded by the default model"
    return None


def _pct(tested: int, not_tested: int) -> float | None:
    denom = tested + not_tested
    return round(100.0 * tested / denom, 1) if denom else None


def _total(states: list[str]) -> Json:
    tested, not_tested, excluded = states.count("tested"), states.count("notTested"), states.count("excluded")
    return {
        "tested": tested,
        "notTested": not_tested,
        "excluded": excluded,
        "total": len(states),
        "percent": _pct(tested, not_tested),
    }


def _get_path(body: Any, dotted: str) -> tuple[bool, Any]:
    cur = body
    for part in (p.removesuffix("[]") for p in dotted.split(".")):
        if isinstance(cur, list) and cur:
            cur = cur[0]
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _top_fields(body: Any, prefix: str = "", depth: int = 3) -> list[str]:
    """Field paths present in a body (objects only; arrays descend into their first element)."""
    if isinstance(body, list):
        body = body[0] if body else None
    if not isinstance(body, dict):
        return []
    out: list[str] = []
    for key, value in body.items():
        path = f"{prefix}{key}"
        out.append(path)
        if depth > 1:
            out.extend(_top_fields(value, f"{path}.", depth - 1))
    return out


def _over_specified(body: Any, read: set[str], prefix: str = "", depth: int = 3) -> list[str]:
    """Field paths a pact includes that the code never reads. A path the code reads whole, or any part of, is not
    flagged; one whose siblings are read but which is not itself read is, at any depth up to `depth`."""
    if isinstance(body, list):
        body = body[0] if body else None
    if not isinstance(body, dict) or depth < 1:
        return []
    out: list[str] = []
    for key, value in body.items():
        path = f"{prefix}{key}"
        if path in read:
            continue
        if any(r.startswith(f"{path}.") for r in read):
            out.extend(_over_specified(value, read, f"{path}.", depth - 1))
        else:
            out.append(path)
    return out


# ─── locations ─────────────────────────────────────────────────────────────────


class Locations:
    """Report-level location table. `full` publishes paths/lines/symbols, `hashed` hashes only, `none` nothing."""

    def __init__(self, mode: str, commit: str) -> None:
        self.mode = mode
        self.commit = commit
        self.table: dict[str, Json] = {}

    def ref(self, kind: str, loc: Json | None, extra: str = "") -> str | None:
        if self.mode == "none" or not isinstance(loc, dict) or not loc:
            return None
        file, symbol = str(loc.get("file", "")), str(loc.get("symbol", ""))
        digest = str(loc.get("hash") or _sha(f"{kind}|{file}|{loc.get('line', '')}|{symbol}"))
        loc_id = f"loc-{_sha(f'{kind}|{digest}', 12)}"
        if loc_id not in self.table:
            entry: Json = {"kind": kind, "commit": self.commit, "hash": digest}
            if self.mode == "hashed":  # a local agent finds the code by hashing its own paths and symbols
                if file:
                    entry["fileHash"] = _sha(file)
                if symbol:
                    entry["symbolHash"] = _sha(symbol)
            if self.mode == "full":
                if file:
                    entry["file"] = file
                if isinstance(loc.get("line"), int) and loc["line"] >= 1:
                    entry["line"] = loc["line"]
                if symbol:
                    entry["symbol"] = symbol
            self.table[loc_id] = entry
        return loc_id

    def refs(self, kind: str, locs: list[Json | None], extra: str = "") -> list[str]:
        out: list[str] = []
        for loc in locs:
            ref = self.ref(kind, loc, extra)
            if ref and ref not in out:
                out.append(ref)
        return out


# ─── pact interactions ─────────────────────────────────────────────────────────


def _content_type(part: Json) -> str:
    for key, value in (part.get("headers") or {}).items():
        if str(key).lower() == "content-type":
            return str(value[0] if isinstance(value, list) and value else value).lower()
    body = part.get("body")
    if isinstance(body, dict) and body.get("contentType"):
        return str(body["contentType"]).lower()
    return ""


def _body_of(part: Json, v4: bool) -> Any:
    body = part.get("body")
    if v4 and isinstance(body, dict) and "content" in body:
        body = body["content"]
    if isinstance(body, str) and "x-www-form-urlencoded" in _content_type(part):
        parsed = urllib.parse.parse_qs(body, keep_blank_values=True)
        return {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}
    return body


def _parse_query(raw: Any) -> dict[str, list[str]]:
    if isinstance(raw, dict):
        return {str(k): [str(x) for x in (v if isinstance(v, list) else [v])] for k, v in raw.items()}
    if isinstance(raw, str) and raw:
        out: dict[str, list[str]] = {}
        for pair in raw.split("&"):
            k, _, v = pair.partition("=")
            out.setdefault(k, []).append(v)
        return out
    return {}


def _interactions_from_pact(pact: Json, name: str) -> tuple[list[Json], int]:
    """HTTP interactions of one pact, and how many non-HTTP (message) interactions were skipped."""
    result: list[Json] = []
    skipped = len(pact.get("messages") or [])
    for ix in pact.get("interactions", []):
        if not isinstance(ix, dict):
            continue
        ix_type = ix.get("type")
        if ix_type not in (None, "Synchronous/HTTP"):
            skipped += 1
            continue
        v4 = ix_type == "Synchronous/HTTP"
        req, resp = ix.get("request") or {}, ix.get("response") or {}
        states = ix.get("providerStates")
        if states is None and ix.get("providerState"):
            states = [{"name": ix["providerState"]}]
        try:
            status = int(resp.get("status", 0))
        except (TypeError, ValueError):
            status = 0
        result.append(
            {
                "pact": name,
                "description": str(ix.get("description", "")),
                "providerStates": [str(s.get("name", "")) for s in (states or []) if isinstance(s, dict)],
                "method": str(req.get("method", "")).upper(),
                "path": str(req.get("path", "")),
                "query": _parse_query(req.get("query")),
                "headers": {str(k).lower(): v for k, v in (req.get("headers") or {}).items()},
                "reqBody": _body_of(req, v4),
                "status": status,
                "respBody": _body_of(resp, v4),
            }
        )
    return result, skipped


def pact_info(pact: Json, name: str, origin: str, raw: bytes) -> Json:
    """Where a pact came from: file or broker, its hash, and the consumer version when the pact says."""
    info: Json = {"name": name, "from": origin, "sha256": hashlib.sha256(raw).hexdigest()}
    links = pact.get("_links") or {}
    version = (links.get("pb:consumer-version") or {}).get("name") or (pact.get("metadata") or {}).get(
        "consumerVersion"
    )
    if version:
        info["consumerVersion"] = str(version)
    info["consumer"] = str((pact.get("consumer") or {}).get("name", ""))
    info["provider"] = str((pact.get("provider") or {}).get("name", ""))
    return info


def load_pacts(pact_paths: list[str]) -> tuple[list[Json], list[Json]]:
    """(interactions, per-pact provenance) from Pact v2/v3/v4 files, in a stable order."""
    interactions: list[Json] = []
    infos: list[Json] = []
    for path in sorted(pact_paths):
        raw = Path(path).read_bytes()
        pact = json.loads(raw)
        if not isinstance(pact, dict):
            continue
        name = os.path.basename(path)
        ixs, skipped = _interactions_from_pact(pact, name)
        info = pact_info(pact, name, "file", raw)
        info["interactions"], info["messagesSkipped"] = len(ixs), skipped
        interactions.extend(ixs)
        infos.append(info)
    return interactions, infos


def load_interactions(pact_paths: list[str]) -> list[Json]:
    """HTTP interactions from Pact v2/v3/v4 files, in a stable order."""
    return load_pacts(pact_paths)[0]


def fetch_broker_pact(
    base_url: str, token: str, consumer: str, provider: str, save_dir: str | None = None
) -> tuple[list[Json], Json]:
    """Latest pact for a consumer/provider pair from a broker (read-only GET); optionally saved to save_dir."""
    quote = urllib.parse.quote
    url = f"{base_url.rstrip('/')}/pacts/provider/{quote(provider, safe='')}/consumer/{quote(consumer, safe='')}/latest"
    request = urllib.request.Request(
        url, headers={"Accept": "application/hal+json", "Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - https broker URL given by the caller
            raw = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError(
                f"the broker has no pact for {consumer} -> {provider}; rerun with --no-pacts if that is expected"
            ) from exc
        raise
    pact = json.loads(raw)
    name = f"{consumer}-{provider}.json"
    if save_dir:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        (Path(save_dir) / name).write_bytes(raw)
    ixs, skipped = _interactions_from_pact(pact, name)
    info = pact_info(pact, name, "broker", raw)
    info["interactions"], info["messagesSkipped"] = len(ixs), skipped
    return ixs, info


# ─── specification (optional detail) ───────────────────────────────────────────


def load_spec_operations(spec_path: str) -> tuple[Json, dict[tuple[str, str], list[str]]]:
    """Return (spec info, {(METHOD, normalised template): declared response keys})."""
    import yaml

    with open(spec_path) as f:
        spec = yaml.safe_load(f)
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        raise ValueError("specification has no 'paths'")
    ops: dict[tuple[str, str], list[str]] = {}
    for path, item in spec["paths"].items():
        for method, op in (item or {}).items():
            if method in HTTP_METHODS and isinstance(op, dict):
                ops[(method.upper(), _norm_template(path))] = [str(c) for c in (op.get("responses") or {})]
    info: Json = {"format": "openapi"}
    meta = spec.get("info") or {}
    if meta.get("title"):
        info["title"] = str(meta["title"])
    if meta.get("version"):
        info["version"] = str(meta["version"])
    return info, ops


# ─── pairwise covering array ───────────────────────────────────────────────────


def covering_array(
    params: dict[str, list[str]], covered: set[tuple[tuple[str, str], tuple[str, str]]], cap: int
) -> tuple[list[Json], bool]:
    """Greedy pairwise array over the pairs not already covered. Returns (rows, truncated)."""
    names = sorted(params)
    universe: set[tuple[tuple[str, str], tuple[str, str]]] = set()
    for a, b in itertools.combinations(names, 2):
        for va in params[a]:
            for vb in params[b]:
                universe.add(((a, va), (b, vb)))
    remaining = universe - covered
    candidates = list(itertools.islice(itertools.product(*(params[n] for n in names)), MAX_CANDIDATES))
    rows: list[Json] = []
    while remaining:
        if len(rows) >= cap:
            return rows, True
        best: tuple[int, dict[str, str], set[tuple[tuple[str, str], tuple[str, str]]]] | None = None
        for cand in candidates:
            row = dict(zip(names, cand, strict=True))
            gained = {p for p in remaining if row[p[0][0]] == p[0][1] and row[p[1][0]] == p[1][1]}
            if best is None or len(gained) > best[0]:
                best = (len(gained), row, gained)
        if best is None or best[0] == 0:
            break
        rows.append(best[1])
        remaining -= best[2]
    # Pairs can only be left when the candidate pool was cut at MAX_CANDIDATES: say so, never claim completeness.
    return rows, bool(remaining)


# ─── core calculation ──────────────────────────────────────────────────────────


def _check_call(call: Json, warn: list[str]) -> None:
    """Warnings for a manifest call: unknown keys, template syntax left in a path, thin call sites."""
    label = f"{call.get('method', '?')} {call.get('path', '?')}"
    for key in call:
        if key not in KNOWN_CALL_KEYS:
            warn.append(f"call {label}: unknown key '{key}' is ignored")
    path = str(call.get("path") or "")
    if re.search(r"\$\{|\{\{|`", path):
        warn.append(f"call {label}: path contains template syntax and is matched literally: {path}")
    site = call.get("callSite")
    if not isinstance(site, dict) or not site:
        warn.append(f"call {label}: no callSite, so no location is published for it")
    else:
        missing = [k for k in ("file", "line", "symbol") if not site.get(k)]
        if missing:
            warn.append(f"call {label}: callSite lacks {', '.join(missing)}")
    inputs = call.get("inputs") or {}
    for key in inputs:
        if key not in KNOWN_INPUT_KEYS:
            warn.append(f"call {label}: unknown inputs key '{key}' is ignored")
    for group in ("parameters", "body", "headers"):
        for entry in inputs.get(group) or []:
            for key in entry:
                if key not in KNOWN_PARAM_KEYS:
                    warn.append(f"call {label}: unknown key '{key}' on input '{entry.get('name')}' is ignored")


def _merge_calls(
    calls: list[Json], warnings: list[str] | None = None
) -> tuple[dict[tuple[str, str], Json], list[Json]]:
    """Group resolvable calls by (METHOD, path template); return (operations, unresolved calls)."""
    warn = warnings if warnings is not None else []
    ops: dict[tuple[str, str], Json] = {}
    unresolved: list[Json] = []
    for call in calls:
        _check_call(call, warn)
        method, path = str(call.get("method") or "").upper(), str(call.get("path") or "")
        if call.get("unresolvedReason") or not method or not path:
            unresolved.append(call)
            continue
        op = ops.setdefault(
            (method, path),
            {
                "method": method,
                "path": path,
                "callSites": [],
                "handlers": [],
                "nearest": [],
                "successStatus": None,
                "handled": [],
                "params": {},
                "optional": set(),
                "body": {},
                "fields": {},
                "readsNothing": False,
                "passThrough": set(),
            },
        )
        op["callSites"].append(call.get("callSite"))
        op["handlers"].extend(call.get("handlers") or [])
        op["nearest"].append(call.get("nearestTest"))
        op["successStatus"] = op["successStatus"] or call.get("successStatus")
        for s in call.get("handledStatuses") or []:
            if str(s) not in op["handled"]:
                op["handled"].append(str(s))
        inputs = call.get("inputs") or {}
        for p in [*(inputs.get("parameters") or []), *({**h, "in": "header"} for h in inputs.get("headers") or [])]:
            key = f"{p.get('in', 'query')}:{p['name']}"
            vals = op["params"].setdefault(key, [])
            vals.extend(str(v) for v in p.get("values") or [] if str(v) not in vals)
            if p.get("optional"):
                op["optional"].add(key)
        for b in inputs.get("body") or []:
            vals = op["body"].setdefault(b["name"], [])
            vals.extend(str(v) for v in b.get("values") or [] if str(v) not in vals)
            if b.get("optional"):
                op["optional"].add(f"body:{b['name']}")
        for status, fields in (call.get("responseFields") or {}).items():
            cur = op["fields"].setdefault(str(status), [])
            cur.extend(f.replace("[]", "").lstrip(".") for f in fields if f.replace("[]", "").lstrip(".") not in cur)
        if call.get("readsNothing"):
            op["readsNothing"] = True
        pass_through = call.get("passThrough")
        if pass_through is True:
            op["passThrough"].add("success")
        elif isinstance(pass_through, list):
            op["passThrough"].update(str(s) for s in pass_through)
    return ops, unresolved


def _ix_sends(ix: Json, key: str, value: str | None) -> bool:
    where, _, name = key.partition(":")
    if where == "path":
        return True  # matched the path template, so the path parameter was sent
    if where == "query":
        vals = ix["query"].get(name)
        return vals is not None and (value is None or value in vals)
    if where == "header":
        v = ix["headers"].get(name.lower())
        return v is not None and (value is None or str(v) == value)
    if where == "body":
        found, v = _get_path(ix["reqBody"], name)
        return found and (value is None or str(v) == value)
    return False


def build_artifact(
    manifest: Json,
    interactions: list[Json],
    spec_info: Json | None = None,
    spec_ops: dict[tuple[str, str], list[str]] | None = None,
    locations_mode: str = "full",
    exclude_statuses: list[str] | None = None,
    pairwise_cap: int = DEFAULT_PAIRWISE_CAP,
    large_enum_limit: int = DEFAULT_LARGE_ENUM_LIMIT,
    verifications: dict[str, str] | None = None,
    pact_meta: list[Json] | None = None,
    extra_warnings: list[str] | None = None,
) -> Json:
    commit = str(manifest.get("commit", "unknown"))
    policy_excluded = {s.upper() for s in (exclude_statuses or [])}
    locs = Locations(locations_mode, commit)
    test_locs: Json = manifest.get("tests") or {}
    warnings: list[str] = list(extra_warnings or [])
    raw_defaults = manifest.get("defaults")
    defaults: Json = raw_defaults if isinstance(raw_defaults, dict) else {}
    calls_in = [
        {**{k: v for k, v in defaults.items() if k in ("handledStatuses", "handlers")}, **c}
        if isinstance(c, dict) and "unresolvedReason" not in c
        else c
        for c in (manifest.get("calls") or [])
    ]
    ops, unresolved_calls = _merge_calls(calls_in, warnings)

    # Match pact interactions to operations the code calls (never to spec-only operations).
    regexes = {key: _template_regex(key[1]) for key in ops}
    by_op: dict[tuple[str, str], list[Json]] = {key: [] for key in ops}
    unmatched: list[Json] = []
    for ix in interactions:
        cands = [k for k in ops if k[0] == ix["method"] and regexes[k].match(ix["path"])]
        if not cands:
            unmatched.append(ix)
            continue
        cands.sort(key=lambda k: (k[1].count("{"), k[1]))
        by_op[cands[0]].append(ix)

    used_test_keys: set[str] = set()

    def test_location(ix: Json) -> Json | None:
        keys = [f"{ix['pact']}#{ix['description']}"]
        if ix["providerStates"]:
            keys.append(f"{ix['description']}#{ix['providerStates'][0]}")
        keys.append(ix["description"])
        for k in keys:
            if k in test_locs:
                used_test_keys.add(k)
                return test_locs[k]  # type: ignore[no-any-return]
        return None

    def test_ref(ix: Json) -> Json:
        ref: Json = {
            "type": "pact",
            "pact": ix["pact"],
            "description": ix["description"],
            "providerStates": ix["providerStates"],
        }
        loc = locs.ref("test", test_location(ix), ix["pact"])
        if loc:
            ref["location"] = loc
        link = (verifications or {}).get(f"{ix['pact']}#{ix['description']}") or (verifications or {}).get(
            ix["description"]
        )
        if link:  # a failed verification never changes coverage (Rule H3); the item only links to it
            ref["verification"] = str(link)
        return ref

    operations: list[Json] = []
    observations: list[Json] = []
    report_cross_states: list[str] = []
    for key in sorted(ops, key=lambda k: (k[1], k[0])):
        op, ixs = ops[key], by_op[key]
        method, path = key
        op_id = f"{method} {path}"
        spec_codes = (spec_ops or {}).get((method, _norm_template(path)))
        matched_by = "spec" if spec_codes is not None else "code"
        derived = locs.refs("call-site", op["callSites"], op_id)
        handler_refs = locs.refs("handler", op["handlers"], op_id)
        nearest = locs.refs("test", op["nearest"], op_id)

        def item(
            suffix: str,
            level: str,
            label: str,
            state: str,
            tests: list[Json] | None = None,
            derived_from: list[str] | None = None,
            reason: str | None = None,
            status: str | None = None,
            _op_id: str = op_id,
            _derived: list[str] = derived,
            _nearest: list[str] = nearest,
        ) -> Json:
            out: Json = {"id": f"{_op_id}#{suffix}", "level": level, "label": label, "state": state}
            if reason:
                out["excludedReason"] = reason
            if status:
                out["status"] = status
            if derived_from or _derived:
                out["derivedFrom"] = derived_from or _derived
            if _nearest and state == "notTested":
                out["nearestTests"] = _nearest
            if tests:
                out["tests"] = tests
            return out

        items: list[Json] = []

        # Responses: success + handled statuses; everything else the model leaves out is Excluded.
        spec_success = sorted(c for c in (spec_codes or []) if re.fullmatch(r"2\d\d", c))
        if op["successStatus"]:
            success = str(op["successStatus"])
        elif spec_success:  # no status pinned: the documented 2xx an interaction returns, else the lowest
            success = next(
                (c for c in spec_success if any(_status_matches(ix["status"], c) for ix in ixs)), spec_success[0]
            )
        else:
            success = "2XX"
        shown: list[str] = []
        statuses = [success] + [s for s in op["handled"] if s != success]
        for status in statuses:
            reason = _exclusion_reason(status, policy_excluded) if status != success else None
            covering = [ix for ix in ixs if _status_matches(ix["status"], status)]
            if reason:
                state = "excluded"
            else:
                state = "tested" if covering else "notTested"
            label = f"{status} success response" if status == success else f"{status} handled response"
            handlers = handler_refs if status != success else None
            items.append(
                item(
                    f"response:{status}",
                    "response",
                    label,
                    state,
                    [test_ref(ix) for ix in covering],
                    handlers,
                    reason,
                    status,
                )
            )
            shown.append(status)
        for code in spec_codes or []:  # declared in the spec but left out by the default model
            if code in shown:
                continue
            reason = _exclusion_reason(code, policy_excluded)
            if reason:
                items.append(
                    item(
                        f"response:{code}",
                        "response",
                        f"{code} declared response",
                        "excluded",
                        None,
                        None,
                        reason,
                        code,
                    )
                )

        # Valid inputs: what the code sends.
        param_values: dict[str, list[str]] = {}
        entries: list[tuple[str, list[str]]] = [
            (k, v) for k, v in sorted(op["params"].items()) if not k.startswith("path:")
        ]
        entries += [(f"body:{k}", v) for k, v in sorted(op["body"].items())]
        for key_name, values in entries:
            if values:
                param_values[key_name] = values
                for v in values:
                    covering = [ix for ix in ixs if _ix_sends(ix, key_name, v)]
                    items.append(
                        item(
                            f"input:{key_name}={v}",
                            "validInput",
                            f"{key_name} = {v}",
                            "tested" if covering else "notTested",
                            [test_ref(ix) for ix in covering],
                        )
                    )
            else:
                covering = [ix for ix in ixs if _ix_sends(ix, key_name, None)]
                items.append(
                    item(
                        f"input:{key_name}",
                        "validInput",
                        key_name,
                        "tested" if covering else "notTested",
                        [test_ref(ix) for ix in covering],
                    )
                )

        # Response fields the code reads (consumer only).
        fields_by_status: dict[str, list[str]] = {}
        for status, fields in sorted(op["fields"].items()):
            alias = success if status in ("success", "2XX") else status
            if alias in policy_excluded or _exclusion_reason(alias, policy_excluded) and alias != success:
                continue
            cur = fields_by_status.setdefault(alias, [])
            cur.extend(f for f in fields if f not in cur)
        read_by_status: dict[str, set[str]] = {}
        for alias, fields in fields_by_status.items():
            read_by_status[alias] = set(fields)
            for field in fields:
                covering = [
                    ix for ix in ixs if _status_matches(ix["status"], alias) and _get_path(ix["respBody"], field)[0]
                ]
                items.append(
                    item(
                        f"field:{alias}:{field}",
                        "responseField",
                        f"{alias} {field}",
                        "tested" if covering else "notTested",
                        [test_ref(ix) for ix in covering],
                        handler_refs or None,
                        None,
                        alias,
                    )
                )
        if op["readsNothing"]:
            read_by_status.setdefault(success, set())
        for passed in op["passThrough"]:
            read_by_status[success if passed in ("success", "2XX") else passed] = {"*"}

        # Input -> response: the pact interactions themselves.
        seen_ix: dict[str, int] = {}
        for ix in ixs:
            base = f"interaction:{ix['pact']}:{ix['description']}"
            seen_ix[base] = seen_ix.get(base, 0) + 1
            ix_id = base if seen_ix[base] == 1 else f"{base}#{seen_ix[base]}"
            items.append(
                item(ix_id, "inputResponse", f"{ix['description']} -> {ix['status']}", "tested", [test_ref(ix)])
            )

        # Observations: response fields the pact includes but the handler never reads, and pact statuses the code
        # does not handle. Neither has a denominator, a state or a percentage.
        for ix in ixs:
            for status, read in read_by_status.items():
                if "*" in read or not _status_matches(ix["status"], status):
                    continue
                for field in _over_specified(ix["respBody"], read):
                    obs: Json = {
                        "kind": "overSpecifiedResponseField",
                        "operation": op_id,
                        "status": str(ix["status"]),
                        "field": field,
                        "interaction": test_ref(ix),
                    }
                    if handler_refs:
                        obs["handlerChecked"] = handler_refs
                    observations.append(obs)
            if not any(_status_matches(ix["status"], s) for s in statuses):
                observations.append(
                    {
                        "kind": "unhandledResponseStatus",
                        "operation": op_id,
                        "status": str(ix["status"]),
                        "interaction": test_ref(ix),
                    }
                )

        operation: Json = {
            "id": op_id,
            "method": method,
            "path": path,
            "state": "tested" if ixs else "notTested",
            "matchedBy": matched_by,
            "items": items,
        }
        if derived:
            operation["callSites"] = derived

        # Pairwise suggestions: only where the code really varies its inputs. Axes are input values,
        # optional inputs (present/absent) and the handled responses (Rule H8).
        axes: dict[str, list[str]] = {k: v for k, v in param_values.items() if len(v) >= 2}
        for k in sorted(op["optional"]):
            if not param_values.get(k):
                axes[k] = ["absent", "present"]
        live = [s for s in statuses if not _exclusion_reason(s, policy_excluded) or s == success]
        if len(live) >= 2:
            axes["response"] = sorted(live)

        input_axes = {k: sorted(v)[:large_enum_limit] for k, v in axes.items() if k != "response"}
        if len(input_axes) >= 2:  # Rule H8: only where the code really varies its inputs
            cross, cross_states = _cross_coverage(ixs, input_axes, axes, op["optional"], param_values, test_ref)
            if any(len(axes[k]) > large_enum_limit for k in input_axes):
                cross["valuesLimited"] = True
            operation["crossCoverage"] = cross
            report_cross_states.extend(cross_states)

        has_gap = any(i["state"] == "notTested" for i in items if i["level"] in ("validInput", "response"))
        if len(axes) >= 2 and has_gap:
            limited = {k: sorted(v)[:large_enum_limit] for k, v in axes.items()}
            seen: set[tuple[tuple[str, str], tuple[str, str]]] = set()
            for ix in ixs:
                sent: dict[str, str] = {
                    k: val
                    for k in limited
                    if (val := _axis_value(ix, k, axes, op["optional"], param_values)) is not None
                }
                for a, b in itertools.combinations(sorted(sent), 2):
                    seen.add(((a, sent[a]), (b, sent[b])))
            rows, truncated = covering_array(limited, seen, pairwise_cap)
            if rows:
                arr: Json = {
                    "strength": 2,
                    "parameters": sorted(limited),
                    "rows": rows,
                    "cap": pairwise_cap,
                    "truncated": truncated,
                }
                if any(len(v) > large_enum_limit for v in axes.values()):
                    arr["valuesLimited"] = True
                operation["suggestions"] = {"coveringArray": arr}
        operations.append(operation)

    unresolved: list[Json] = []
    for call in unresolved_calls:
        entry: Json = {
            "kind": "call",
            "reason": str(call.get("unresolvedReason") or "call target could not be worked out"),
        }
        loc = locs.ref("call-site", call.get("callSite"), "unresolved")
        if loc:
            entry["location"] = loc
        if call.get("method"):
            entry["method"] = str(call["method"]).upper()
        if call.get("path"):
            entry["path"] = str(call["path"])
        unresolved.append(entry)
    for ix in unmatched:
        unresolved.append(
            {
                "kind": "interaction",
                "reason": "pact interaction path matches no operation the consumer code calls",
                "interaction": test_ref(ix),
                "method": ix["method"],
                "path": ix["path"],
            }
        )

    all_items = [i for o in operations for i in o["items"]]

    def level(name: str) -> Json:
        return _total([i["state"] for i in all_items if i["level"] == name])

    ir = level("inputResponse")
    ir["percent"] = None  # no denominator: interactions are evidence, not a list the code asks for
    source: Json = {"commit": commit}
    if (manifest.get("consumer") or {}).get("repository"):
        source["repository"] = manifest["consumer"]["repository"]
    if spec_info:
        source["specification"] = spec_info
    source["analysis"] = {
        "tool": str(manifest.get("tool", "unknown")),
        "manifestVersion": str(manifest.get("manifestVersion", "1.0.0")),
        "manifestSha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
    }
    policy: Json = {
        "model": MODEL,
        "responses": "handled",
        "excludeStatuses": sorted(policy_excluded),
        "locations": locations_mode,
        "pairwiseCap": pairwise_cap,
        "largeEnumLimit": large_enum_limit,
    }
    source["analysis"]["configSha256"] = hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()
    messages_skipped = 0
    if pact_meta:
        pacts_read: list[Json] = []
        for info in pact_meta:
            pact_entry: Json = {
                k: info[k] for k in ("name", "from", "sha256", "consumerVersion", "interactions") if k in info
            }
            version = str(info.get("consumerVersion") or "")
            if version and commit != "unknown":
                a_, b_ = version.lower(), commit.lower()
                if not (a_.startswith(b_) or b_.startswith(a_)):
                    pact_entry["commitMismatch"] = True
                    warnings.append(
                        f"pact {info['name']} is consumer version {version}, not the manifest commit {commit}"
                    )
            messages_skipped += int(info.get("messagesSkipped", 0))
            pacts_read.append(pact_entry)
        source["pacts"] = pacts_read
    if messages_skipped:
        warnings.append(f"{messages_skipped} message interaction(s) skipped: the consumer artifact measures HTTP only")
    for key_unused in sorted(set(test_locs) - used_test_keys)[:20] if interactions else []:
        warnings.append(f"tests key '{key_unused}' matches no pact interaction")
    no_tests = sorted({ix["description"] for ix in interactions if test_location(ix) is None})
    if no_tests:
        shown_tests = ", ".join(no_tests[:5]) + (" ..." if len(no_tests) > 5 else "")
        warnings.append(f"{len(no_tests)} pact interaction(s) have no tests entry, so no test location: {shown_tests}")
    artifact: Json = {
        "schemaVersion": SCHEMA_VERSION,
        "participant": {"role": "consumer", "name": str((manifest.get("consumer") or {}).get("name", "unknown"))},
        "counterparty": {"name": str((manifest.get("provider") or {}).get("name", "unknown"))},
        "source": source,
        "policy": policy,
    }
    if locs.table:
        artifact["locations"] = dict(sorted(locs.table.items()))
    artifact["operations"] = operations
    if report_cross_states:
        artifact["crossCoverage"] = {"strength": 2, "totals": _total(report_cross_states)}
    artifact["observations"] = observations
    artifact["unresolved"] = unresolved
    if messages_skipped:
        artifact["notMeasured"] = [
            {"location": "message interactions", "reason": "messagePacts", "count": messages_skipped}
        ]
    artifact["warnings"] = warnings
    artifact["totals"] = {
        "operations": _total([o["state"] for o in operations]),
        "responses": level("response"),
        "inputs": {"valid": level("validInput"), "invalid": None},
        "responseFields": level("responseField"),
        "inputResponse": ir,
        "unresolved": len(unresolved),
    }
    return artifact


def _cross_coverage(
    ixs: list[Json],
    limited: dict[str, list[str]],
    axes: dict[str, list[str]],
    optional: set[str],
    values: dict[str, list[str]],
    test_ref: Any,
) -> tuple[Json, list[str]]:
    """Measured pairwise coverage of the input axes: a pair is tested when one interaction sends both values."""
    field_pairs: list[Json] = []
    states: list[str] = []
    sent = [{k: _axis_value(ix, k, axes, optional, values) for k in limited} for ix in ixs]
    for a, b in itertools.combinations(sorted(limited), 2):
        covered: list[Json] = []
        for va in limited[a]:
            for vb in limited[b]:
                hits = [ix for ix, s in zip(ixs, sent, strict=True) if s[a] == va and s[b] == vb]
                if hits:
                    covered.append({"values": [va, vb], "state": "tested", "tests": [test_ref(ix) for ix in hits]})
        total = len(limited[a]) * len(limited[b])
        field_pairs.append({"fields": [a, b], "total": total, "covered": covered})
        states += ["tested"] * len(covered) + ["notTested"] * (total - len(covered))
    return {"strength": 2, "fieldPairs": field_pairs, "totals": _total(states)}, states


def _axis_value(
    ix: Json, name: str, axes: dict[str, list[str]], optional: set[str], values: dict[str, list[str]]
) -> str | None:
    """The value an interaction takes on one covering-array axis (None when it does not say)."""
    if name == "response":
        return next((s for s in axes[name] if _status_matches(ix["status"], s)), None)
    if name in optional and not values.get(name):
        return "present" if _ix_sends(ix, name, None) else "absent"
    v = _value_sent(ix, name)
    return None if v is None else str(v)


def _value_sent(ix: Json, key: str) -> Any:
    where, _, name = key.partition(":")
    if where == "query":
        vals = ix["query"].get(name)
        return vals[0] if vals else None
    if where == "header":
        return ix["headers"].get(name.lower())
    if where == "body":
        found, v = _get_path(ix["reqBody"], name)
        return v if found else None
    return None


# ─── CLI ───────────────────────────────────────────────────────────────────────


def _summary_checks(artifact: Json) -> list[str]:
    """Self-check lines: locations, derivedFrom, why a level is n/a, and the warnings count."""
    items = [i for o in artifact["operations"] for i in o["items"]]
    locs = artifact.get("locations") or {}
    missing = sum(1 for i in items if not i.get("derivedFrom"))
    lines = [f"  Locations: {len(locs)}  Items without derivedFrom: {missing} of {len(items)}"]
    if (artifact.get("policy") or {}).get("locations") == "full" and locs:
        thin = sum(1 for lc in locs.values() if not (lc.get("file") and lc.get("line") and lc.get("symbol")))
        if thin:
            lines.append(f"  {thin} location(s) lack a file, line or symbol (add them to the manifest)")
    if artifact["totals"]["responseFields"]["total"] == 0:
        lines.append(
            "  Response fields n/a: the manifest records no reads (readsNothing / passThrough say it is deliberate)"
        )
    count = len(artifact.get("warnings") or [])
    lines.append(
        f"  Warnings: {count} (listed under 'warnings' in the artifact)" if count else "  Warnings: none (checks ran)"
    )
    return lines


def format_summary(artifact: Json) -> str:
    t = artifact["totals"]

    def line(name: str, lv: Json) -> str:
        pct = "n/a" if lv["percent"] is None else f"{lv['percent']}%"
        return f"  {name:<16}{pct:>7}  ({lv['tested']} tested, {lv['notTested']} not tested, {lv['excluded']} excluded)"

    return "\n".join(
        [
            f"Consumer coverage: {artifact['participant']['name']} -> {artifact['counterparty']['name']}",
            line("Operations", t["operations"]),
            line("Responses", t["responses"]),
            line("Valid inputs", t["inputs"]["valid"]),
            line("Response fields", t["responseFields"]),
            f"  {'Invalid inputs':<16}{'not measured':>13}",
            f"  Unresolved: {t['unresolved']}  Observations: {len(artifact['observations'])}",
            *_summary_checks(artifact),
        ]
    )


def _schema_check(artifact: Json) -> str:
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ImportError:
        return "schema check skipped: jsonschema is not installed (uv run --with jsonschema ...)"
    schema_path = Path(__file__).resolve().parent.parent / "references" / "coverage-artifact-1.0.0.schema.json"
    errors = list(jsonschema.Draft202012Validator(json.loads(schema_path.read_text())).iter_errors(artifact))
    return (
        "schema check: valid"
        if not errors
        else f"schema check: {len(errors)} error(s), first: {errors[0].message[:160]}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consumer coverage artifact (schema 1.0.0) from a discovery manifest.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pacts", nargs="*", default=[], help="pact files or globs (optional with --no-pacts)")
    parser.add_argument(
        "--no-pacts", action="store_true", help="run with no pacts on purpose: every item is Not tested"
    )
    parser.add_argument("--save-pacts", metavar="DIR", help="with --broker-url: also write the fetched pact into DIR")
    parser.add_argument("--broker-url", help="fetch the latest pact for the pair from this broker (read-only GET)")
    parser.add_argument("--broker-token", help="broker bearer token (default: PACT_BROKER_TOKEN)")
    parser.add_argument("--consumer", help="consumer pacticipant (default: manifest consumer.name)")
    parser.add_argument("--provider", help="provider pacticipant (default: manifest provider.name)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when the calculation fails (default: always 0)")
    parser.add_argument(
        "--check", action="store_true", help="validate the artifact against the 1.0.0 schema (needs jsonschema)"
    )
    parser.add_argument("--spec", help="optional provider OpenAPI spec (adds detail only)")
    parser.add_argument("--locations", choices=["full", "hashed", "none"], default="full")
    parser.add_argument("--exclude-statuses", nargs="*", default=[])
    parser.add_argument("--pairwise-cap", type=int, default=DEFAULT_PAIRWISE_CAP)
    parser.add_argument("--large-enum-limit", type=int, default=DEFAULT_LARGE_ENUM_LIMIT)
    parser.add_argument(
        "--verifications",
        help="optional JSON map of '<pact file>#<description>' (or description) to a provider verification result URL",
    )
    parser.add_argument("--out", help="write the artifact here (default: stdout)")
    parser.add_argument("--quiet", action="store_true", help="suppress the human summary on stderr")
    try:
        args = parser.parse_args(argv)
    except SystemExit:  # usage errors must not fail the build either (--help exits 0 as usual)
        return 0
    try:
        manifest = json.loads(Path(args.manifest).read_text())
        files = sorted({f for pattern in args.pacts for f in glob.glob(pattern)})
        interactions, infos = load_pacts(files)
        consumer = args.consumer or (manifest.get("consumer") or {}).get("name")
        provider = args.provider or (manifest.get("provider") or {}).get("name")
        notes: list[str] = []
        kept: list[Json] = []
        for info in infos:  # a pact for another pair would silently mix providers
            other = [
                f"{what} {info[what]}"
                for what, want in (("consumer", consumer), ("provider", provider))
                if want and info.get(what) and str(info[what]).lower() != str(want).lower()
            ]
            if other:
                notes.append(f"pact {info['name']} skipped: it is for {', '.join(other)}, not {consumer} -> {provider}")
                interactions = [ix for ix in interactions if ix["pact"] != info["name"]]
            else:
                kept.append(info)
        if args.broker_url:
            if not (consumer and provider):
                raise ValueError("--broker-url needs a consumer and a provider (flags or manifest names)")
            token = args.broker_token or os.environ.get("PACT_BROKER_TOKEN", "")
            fetched, info = fetch_broker_pact(args.broker_url, token, str(consumer), str(provider), args.save_pacts)
            interactions.extend(fetched)
            kept.append(info)
        if not kept and not args.no_pacts:
            notes.append(
                "no pact files matched: every item is reported Not tested (use --no-pacts if that is deliberate)"
            )
        for note in notes:
            print(f"consumer coverage: {note}", file=sys.stderr)
        spec_info, spec_ops = (None, None)
        if args.spec:
            spec_info, spec_ops = load_spec_operations(args.spec)
        verifications = json.loads(Path(args.verifications).read_text()) if args.verifications else None
        artifact = build_artifact(
            manifest,
            interactions,
            spec_info,
            spec_ops,
            args.locations,
            args.exclude_statuses,
            args.pairwise_cap,
            args.large_enum_limit,
            verifications,
            kept,
            notes,
        )
        text = json.dumps(artifact, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text)
        else:
            sys.stdout.write(text)
        if not args.quiet:
            print(format_summary(artifact), file=sys.stderr)
        if args.check:
            print(_schema_check(artifact), file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - the coverage step must never fail the build
        print(f"consumer coverage skipped, NO artifact written: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
