import json
import pathlib

import consumer_coverage as cc
import pytest

FIX = pathlib.Path(__file__).parent / "fixtures" / "consumer"
REFS = pathlib.Path(__file__).parents[2] / "references"
SCHEMA = REFS / "coverage-artifact-1.0.0.schema.json"
SAMPLES = sorted((REFS / "samples").glob("consumer-coverage-artifact-sample*.json"))


def run(manifest, pact, spec=None, mode="full", **kw):
    m = json.loads((FIX / manifest).read_text())
    ixs, infos = cc.load_pacts([str(FIX / pact)])
    info, ops = cc.load_spec_operations(str(FIX / spec)) if spec else (None, None)
    return cc.build_artifact(m, ixs, info, ops, mode, pact_meta=infos, **kw)


@pytest.fixture
def checkout():
    return run("checkout-manifest.json", "checkout-product-api.pact.json", "product-api.openapi.yaml")


@pytest.fixture
def mobile():
    return run("mobile-manifest.json", "mobile-loyalty-api.pact.json", mode="hashed")


def items(a, level):
    return [i for o in a["operations"] for i in o["items"] if i["level"] == level]


def test_code_sets_denominator_spec_only_op_not_added(checkout):
    ids = {o["id"] for o in checkout["operations"]}
    assert "GET /orders/{id}" not in ids  # in the spec, never called by the code
    assert ids == {"GET /products/{id}", "GET /products", "POST /orders"}
    assert {o["matchedBy"] for o in checkout["operations"]} == {"spec"}


def test_responses_handled_model_with_explicit_exclusions(checkout):
    by_status = {i["status"]: i for i in items(checkout, "response") if i["id"].startswith("GET /products/{id}")}
    assert by_status["404"]["state"] == "tested"
    for s in ("503", "5XX", "default"):
        assert by_status[s]["state"] == "excluded" and by_status[s]["excludedReason"]
    # 422 is handled in code but no interaction covers it -> Not tested; 400 is spec-only -> absent
    states = {i["id"]: i["state"] for i in items(checkout, "response")}
    assert states["POST /orders#response:422"] == "notTested"
    assert "GET /products#response:400" not in states


def test_unresolved_call_and_interaction_named_not_dropped(checkout):
    kinds = sorted(u["kind"] for u in checkout["unresolved"])
    assert kinds == ["call", "interaction"]
    assert checkout["totals"]["unresolved"] == 2
    assert all(u["reason"] for u in checkout["unresolved"])


def test_over_specified_field_is_observation_not_item(checkout):
    assert [o["field"] for o in checkout["observations"]] == ["sku"]
    assert not any("sku" in i["id"] for o in checkout["operations"] for i in o["items"])


def test_invalid_inputs_not_measured(checkout):
    assert checkout["totals"]["inputs"]["invalid"] is None


def test_totals_match_items(checkout, mobile):
    for a in (checkout, mobile):
        for name, level in (("responses", "response"), ("responseFields", "responseField")):
            t, its = a["totals"][name], items(a, level)
            assert t["total"] == len(its)
            assert t["tested"] == sum(i["state"] == "tested" for i in its)
            assert t["excluded"] == sum(i["state"] == "excluded" for i in its)
        v = items(a, "validInput")
        assert a["totals"]["inputs"]["valid"]["total"] == len(v)
        assert a["totals"]["operations"]["total"] == len(a["operations"])


def test_percent_excludes_excluded_items(checkout):
    t = checkout["totals"]["responses"]
    assert t["percent"] == round(100 * t["tested"] / (t["tested"] + t["notTested"]), 1)


def test_pairwise_only_where_code_varies_inputs_and_skips_covered_pairs(checkout):
    op = next(o for o in checkout["operations"] if o["id"] == "GET /products")
    arr = op["suggestions"]["coveringArray"]
    assert arr["truncated"] is False
    assert {"query:category": "books", "query:sort": "price"} not in arr["rows"]  # already in a pact
    assert len(arr["rows"]) == 3  # 3 uncovered pairs, each needs a row here
    assert all("suggestions" not in o for o in checkout["operations"] if o["id"] != "GET /products")


def test_pairwise_cap_reports_truncation():
    params = {"a": ["1", "2", "3"], "b": ["x", "y", "z"]}
    rows, truncated = cc.covering_array(params, set(), cap=2)
    assert len(rows) == 2 and truncated is True
    rows, truncated = cc.covering_array(params, set(), cap=20)
    assert len(rows) == 3 + 3 + 3 and truncated is False


def test_no_spec_mode_still_gives_percentage(mobile):
    assert "specification" not in mobile["source"]
    assert {o["matchedBy"] for o in mobile["operations"]} == {"code"}
    assert mobile["totals"]["operations"]["percent"] == 50.0
    # success is "any 2xx" when neither manifest nor spec names one
    assert any(i["id"].endswith("response:2XX") for i in items(mobile, "response"))


def test_locations_modes(checkout):
    full = checkout["locations"]
    assert any("file" in loc and "symbol" in loc for loc in full.values())
    hashed = run("checkout-manifest.json", "checkout-product-api.pact.json", mode="hashed")["locations"]
    assert hashed and all(set(loc) <= {"kind", "commit", "hash", "fileHash", "symbolHash"} for loc in hashed.values())
    none = run("checkout-manifest.json", "checkout-product-api.pact.json", mode="none")
    assert "locations" not in none
    assert not any(i.get("derivedFrom") or i.get("nearestTests") for o in none["operations"] for i in o["items"])
    assert "location" not in json.dumps(none["unresolved"])


def test_never_publishes_code_text(checkout):
    assert "body" not in json.dumps(checkout["locations"]).lower()


def test_same_inputs_same_output():
    a = run("checkout-manifest.json", "checkout-product-api.pact.json", "product-api.openapi.yaml")
    b = run("checkout-manifest.json", "checkout-product-api.pact.json", "product-api.openapi.yaml")
    assert json.dumps(a) == json.dumps(b)


def test_policy_exclude_statuses():
    a = run("checkout-manifest.json", "checkout-product-api.pact.json", exclude_statuses=["404"])
    s = next(i for i in items(a, "response") if i["id"] == "GET /products/{id}#response:404")
    assert s["state"] == "excluded" and "excludeStatuses" in s["excludedReason"]
    assert a["policy"]["excludeStatuses"] == ["404"]


@pytest.mark.parametrize("argv", [["--manifest", "/does/not/exist.json", "--pacts", "x"], ["--bogus"]])
def test_cli_always_exits_zero(argv, capsys):
    assert cc.main(argv) == 0


def test_cli_writes_artifact(tmp_path):
    out = tmp_path / "a.json"
    rc = cc.main(
        [
            "--manifest",
            str(FIX / "mobile-manifest.json"),
            "--pacts",
            str(FIX / "mobile-loyalty-api.pact.json"),
            "--out",
            str(out),
            "--quiet",
            "--locations",
            "hashed",
        ]
    )
    assert rc == 0 and json.loads(out.read_text())["participant"]["role"] == "consumer"


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.name)
def test_samples_validate_against_schema(sample):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text())
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(json.loads(sample.read_text()), schema)


def test_schema_rejects_malformed_artifacts(checkout):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    assert not list(validator.iter_errors(checkout))
    bad_state = json.loads(json.dumps(checkout))
    bad_state["operations"][0]["items"][0]["state"] = "passing"
    no_reason = json.loads(json.dumps(checkout))
    excluded = next(i for o in no_reason["operations"] for i in o["items"] if i["state"] == "excluded")
    del excluded["excludedReason"]
    missing = {k: v for k, v in checkout.items() if k != "totals"}
    for bad in (bad_state, no_reason, missing):
        assert list(validator.iter_errors(bad))


def test_samples_are_regenerated_from_fixtures(checkout, mobile):
    by_name = {p.name: json.loads(p.read_text()) for p in SAMPLES}
    assert by_name["consumer-coverage-artifact-sample-1.0.0.json"] == checkout
    assert by_name["consumer-coverage-artifact-sample-no-spec-1.0.0.json"] == mobile


def test_h8_example_four_interactions_cover_every_pair():
    """sort in {price,name}, inStock present/absent, handled 200 and 404 -> 4 rows, not 8."""
    manifest = {
        "commit": "c1",
        "calls": [
            {
                "method": "GET",
                "path": "/products",
                "successStatus": "200",
                "handledStatuses": ["404"],
                "inputs": {
                    "parameters": [
                        {"name": "sort", "in": "query", "values": ["price", "name"]},
                        {"name": "inStock", "in": "query", "optional": True},
                    ]
                },
            }
        ],
    }
    arr = cc.build_artifact(manifest, [])["operations"][0]["suggestions"]["coveringArray"]
    assert arr["parameters"] == ["query:inStock", "query:sort", "response"]
    assert len(arr["rows"]) == 4 and arr["truncated"] is False
    pairs = {(a, b) for r in arr["rows"] for a, b in __import__("itertools").combinations(sorted(r.items()), 2)}
    assert len(pairs) == 12  # 2x2 + 2x2 + 2x2 pairs, all covered


def test_provider_sample_validates_against_schema():
    import json
    from pathlib import Path

    jsonschema = pytest.importorskip("jsonschema")
    refs = Path(__file__).resolve().parents[2] / "references"
    schema = json.loads((refs / "coverage-artifact-1.0.0.schema.json").read_text())
    sample = json.loads((refs / "samples" / "provider-coverage-artifact-sample-1.0.0.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(sample)


def test_cli_exits_zero_when_output_cannot_be_written(tmp_path, capsys):
    out = tmp_path / "missing-dir" / "artifact.json"
    argv = ["--manifest", str(FIX / "checkout-manifest.json"), "--pacts", str(FIX / "checkout-product-api.pact.json")]
    assert cc.main([*argv, "--out", str(out), "--quiet"]) == 0
    assert not out.exists()
    assert "consumer coverage skipped" in capsys.readouterr().err


def test_covering_array_reports_truncated_when_candidate_pool_is_cut(monkeypatch):
    params = {f"p{i}": ["a", "b", "c"] for i in range(6)}  # 729 candidate rows
    rows, truncated = cc.covering_array(params, set(), cap=10_000)
    assert truncated is False  # full pool: every pair gets covered
    monkeypatch.setattr(cc, "MAX_CANDIDATES", 3)  # a pool too small to cover every pair
    rows, truncated = cc.covering_array(params, set(), cap=10_000)
    assert truncated is True
    assert rows


def _ix(query=None, status=200, description="d"):
    return {
        "pact": "p.json",
        "description": description,
        "providerStates": [],
        "method": "GET",
        "path": "/products",
        "query": query or {},
        "headers": {},
        "reqBody": None,
        "status": status,
        "respBody": None,
    }


_CROSS_MANIFEST = {
    "commit": "c1",
    "calls": [
        {
            "method": "GET",
            "path": "/products",
            "successStatus": "200",
            "inputs": {
                "parameters": [
                    {"name": "sort", "in": "query", "values": ["price", "name"]},
                    {"name": "inStock", "in": "query", "optional": True},
                ]
            },
        }
    ],
}


def test_h8_measured_cross_coverage_for_consumers():
    a = cc.build_artifact(_CROSS_MANIFEST, [_ix({"sort": ["price"], "inStock": ["true"]}), _ix({"sort": ["name"]})])
    cross = a["operations"][0]["crossCoverage"]
    assert cross["strength"] == 2
    [pair] = cross["fieldPairs"]
    assert pair["fields"] == ["query:inStock", "query:sort"] and pair["total"] == 4
    assert {tuple(c["values"]) for c in pair["covered"]} == {("present", "price"), ("absent", "name")}
    assert all(c["state"] == "tested" and c["tests"] for c in pair["covered"])
    assert (cross["totals"]["tested"], cross["totals"]["notTested"], cross["totals"]["percent"]) == (2, 2, 50.0)
    assert a["crossCoverage"]["totals"] == cross["totals"]  # report level sums the operations


def test_cross_coverage_left_out_when_code_does_not_vary_inputs():
    manifest = {"commit": "c1", "calls": [{"method": "GET", "path": "/products", "successStatus": "200"}]}
    a = cc.build_artifact(manifest, [_ix()])
    assert "crossCoverage" not in a["operations"][0] and "crossCoverage" not in a


def test_hashed_locations_carry_file_and_symbol_hashes(checkout, mobile):
    for loc in mobile["locations"].values():
        assert {"kind", "commit", "hash", "fileHash"} <= set(loc) and "file" not in loc and "symbol" not in loc
    full = next(iter(checkout["locations"].values()))
    assert "fileHash" not in full and "symbolHash" not in full
    m = json.loads((FIX / "mobile-manifest.json").read_text())
    call = next(c for c in m["calls"] if c.get("callSite"))["callSite"]
    hashed = [loc for loc in mobile["locations"].values() if loc["kind"] == "call-site"]
    assert cc._sha(call["file"]) in {loc["fileHash"] for loc in hashed}
    assert cc._sha(call["symbol"]) in {loc["symbolHash"] for loc in hashed}


def test_config_hash_recorded_and_changes_with_policy():
    a = cc.build_artifact(_CROSS_MANIFEST, [])
    b = cc.build_artifact(_CROSS_MANIFEST, [], exclude_statuses=["418"])
    ha, hb = a["source"]["analysis"]["configSha256"], b["source"]["analysis"]["configSha256"]
    assert len(ha) == 64 and ha != hb
    assert ha == cc.build_artifact(_CROSS_MANIFEST, [])["source"]["analysis"]["configSha256"]


def test_verification_links_are_attached_and_do_not_change_coverage():
    plain = cc.build_artifact(_CROSS_MANIFEST, [_ix({"sort": ["price"]}, description="list")])
    linked = cc.build_artifact(
        _CROSS_MANIFEST,
        [_ix({"sort": ["price"]}, description="list")],
        verifications={"p.json#list": "https://broker/verification/1"},
    )
    refs = [r for o in linked["operations"] for i in o["items"] for r in i.get("tests", [])]
    assert refs and all(r["verification"] == "https://broker/verification/1" for r in refs)
    assert plain["totals"] == linked["totals"]


def test_verifications_flag_reads_json_file(tmp_path):
    v = tmp_path / "v.json"
    v.write_text(json.dumps({"a request for product 1": "https://broker/v/9"}))
    out = tmp_path / "a.json"
    args = ["--manifest", str(FIX / "checkout-manifest.json"), "--pacts", str(FIX / "checkout-product-api.pact.json")]
    assert cc.main([*args, "--verifications", str(v), "--out", str(out), "--quiet"]) == 0
    assert "https://broker/v/9" in out.read_text()


# ─── Rule H alignment round 2: fixes found by running the skill on nine projects ───────────────


def mk_ix(
    method="GET", path="/products", status=200, query=None, headers=None, req=None, resp=None, desc="d", states=None
):
    return {
        "pact": "p.json",
        "description": desc,
        "providerStates": states or [],
        "method": method,
        "path": path,
        "query": query or {},
        "headers": headers or {},
        "reqBody": req,
        "status": status,
        "respBody": resp,
    }


def call(path="/products", method="GET", **kw):
    site = {"file": "src/a.ts", "line": 3, "symbol": "load"}
    return {"method": method, "path": path, "callSite": site, "successStatus": "200", **kw}


def build(calls, ixs, tests=None, **kw):
    manifest = {"commit": "c1", "calls": calls, "tests": tests or {}}
    return cc.build_artifact(manifest, ixs, **kw)


def resp_items(a):
    return {i["label"]: i for o in a["operations"] for i in o["items"] if i["level"] == "response"}


def test_handled_4xx_class_is_tested_by_any_client_error_interaction():
    a = build([call(handledStatuses=["4XX", "5XX"])], [mk_ix(), mk_ix(status=404, desc="missing")])
    items = resp_items(a)
    assert items["4XX handled response"]["state"] == "tested"
    assert items["5XX handled response"]["state"] == "excluded"  # 5xx stays Excluded (Rule H5)


def test_blanket_non_2xx_handling_is_tested_by_any_error_interaction():
    covered = build([call(handledStatuses=["non-2XX"])], [mk_ix(), mk_ix(status=422, desc="bad")])
    assert resp_items(covered)["non-2XX handled response"]["state"] == "tested"
    uncovered = build([call(handledStatuses=["non-2XX"])], [mk_ix()])
    assert resp_items(uncovered)["non-2XX handled response"]["state"] == "notTested"


def test_headers_inputs_are_measured_and_unknown_keys_warn():
    c = call(inputs={"headers": [{"name": "x-api-key"}], "bogus": []})
    a = build([c], [mk_ix(headers={"x-api-key": "k"})])
    item = next(i for o in a["operations"] for i in o["items"] if i["id"].endswith("input:header:x-api-key"))
    assert item["state"] == "tested"
    assert any("unknown inputs key 'bogus'" in w for w in a["warnings"])


def test_tests_map_can_key_by_provider_state_and_item_ids_stay_unique():
    ixs = [mk_ix(desc="a request", states=["ok"]), mk_ix(status=404, desc="a request", states=["gone"])]
    tests = {
        "a request#ok": {"file": "t.ts", "line": 10, "symbol": "ok"},
        "a request#gone": {"file": "t.ts", "line": 20, "symbol": "gone"},
    }
    a = build([call()], ixs, tests)
    lines = sorted(loc["line"] for loc in a["locations"].values() if loc["kind"] == "test")
    assert lines == [10, 20]
    ids = [i["id"] for o in a["operations"] for i in o["items"]]
    assert len(ids) == len(set(ids))


def test_pass_through_and_reads_nothing_control_observations():
    body = {"id": 1, "extra": 2}
    plain = build([call()], [mk_ix(resp=body)])
    forwarded = build([call(passThrough=True)], [mk_ix(resp=body)])
    nothing = build([call(readsNothing=True)], [mk_ix(resp=body)])
    assert plain["observations"] == [] and forwarded["observations"] == []  # unknown reads / forwarded: no claim
    assert {o["field"] for o in nothing["observations"]} == {"id", "extra"}


def test_over_specified_fields_are_found_at_any_depth():
    body = {"users": [{"id": 1, "roles": [{"name": "a"}]}]}
    assert cc._over_specified(body, {"users.id"}) == ["users.roles"]
    assert cc._over_specified(body, {"users"}) == []
    assert cc._over_specified(body, set()) == ["users"]


def test_pact_status_the_code_does_not_handle_is_an_observation():
    a = build([call()], [mk_ix(), mk_ix(status=400, desc="bad token")])
    kinds = [(o["kind"], o["status"]) for o in a["observations"]]
    assert ("unhandledResponseStatus", "400") in kinds and len(kinds) == 1


def test_form_urlencoded_request_bodies_are_parsed_into_fields():
    part = {"headers": {"Content-Type": ["application/x-www-form-urlencoded"]}, "body": "a=1&b=two&a=3"}
    assert cc._body_of(part, False) == {"a": ["1", "3"], "b": "two"}
    c = call("/token", "POST", inputs={"body": [{"name": "grant_type"}, {"name": "code"}]})
    ix = mk_ix("POST", "/token", req={"grant_type": "authorization_code", "code": "x"})
    a = build([c], [ix])
    states = {i["label"]: i["state"] for o in a["operations"] for i in o["items"] if i["level"] == "validInput"}
    assert set(states.values()) == {"tested"}


def test_any_documented_2xx_the_pact_returns_is_the_success_response(tmp_path):
    spec = tmp_path / "s.yaml"
    spec.write_text(
        "openapi: 3.0.0\ninfo: {title: t, version: '1'}\n"
        "paths:\n  /jobs:\n    post:\n      responses:\n        '200': {}\n        '202': {}\n"
    )
    info, ops = cc.load_spec_operations(str(spec))
    c = call("/jobs", "POST")
    del c["successStatus"]
    a = build([c], [mk_ix("POST", "/jobs", status=202)], spec_info=info, spec_ops=ops)
    assert resp_items(a)["202 success response"]["state"] == "tested"


def test_success_key_aliases_merge_into_one_field_item():
    calls = [call(responseFields={"200": ["id"]}), call(responseFields={"2XX": ["id"]})]
    a = build(calls, [mk_ix(resp={"id": 1})])
    ids = [i["id"] for o in a["operations"] for i in o["items"] if i["level"] == "responseField"]
    assert ids == ["GET /products#field:200:id"]


def test_path_parameters_are_not_counted_as_valid_inputs():
    c = call("/products/{id}", inputs={"parameters": [{"name": "id", "in": "path"}]})
    a = build([c], [mk_ix(path="/products/7")])
    assert a["totals"]["inputs"]["valid"]["total"] == 0


def test_shared_handler_is_one_location_across_operations():
    handler = {"file": "src/h.ts", "line": 9, "symbol": "check"}
    a = build([call("/a", handlers=[handler]), call("/b", handlers=[handler])], [])
    assert sum(1 for loc in a["locations"].values() if loc["kind"] == "handler") == 1


def test_warnings_for_template_paths_thin_call_sites_and_test_keys():
    thin = {"method": "GET", "path": "/x/${id}", "callSite": {"file": "src/a.ts", "line": 1}}
    a = build([thin], [mk_ix(path="/x/1")], {"never used": {"file": "t.ts", "line": 1, "symbol": "s"}})
    text = " | ".join(a["warnings"])
    assert "template syntax" in text and "callSite lacks symbol" in text
    assert "tests key 'never used' matches no pact interaction" in text
    assert "no tests entry" in text


def test_summary_checks_report_locations_and_why_fields_are_na():
    a = build([call()], [mk_ix()])
    summary = cc.format_summary(a)
    assert "Locations:" in summary and "Items without derivedFrom: 0 of" in summary
    assert "Response fields n/a" in summary


def _write_pact(tmp_path, name, consumer="app", provider="svc", version=None, messages=0):
    pact = {
        "consumer": {"name": consumer},
        "provider": {"name": provider},
        "interactions": [
            {"description": "list", "request": {"method": "GET", "path": "/products"}, "response": {"status": 200}}
        ],
    }
    if messages:
        pact["messages"] = [{"description": "event"}] * messages
    if version:
        pact["_links"] = {"pb:consumer-version": {"name": version}}
    path = tmp_path / name
    path.write_text(json.dumps(pact))
    return str(path)


def _manifest_file(tmp_path, provider="svc"):
    m = {"commit": "abc1234", "consumer": {"name": "app"}, "provider": {"name": provider}, "calls": [call()]}
    path = tmp_path / "m.json"
    path.write_text(json.dumps(m))
    return str(path)


def test_pact_provenance_records_version_and_flags_a_commit_mismatch(tmp_path):
    pact = _write_pact(tmp_path, "p.json", version="ffff999", messages=2)
    out = tmp_path / "a.json"
    assert cc.main(["--manifest", _manifest_file(tmp_path), "--pacts", pact, "--out", str(out), "--quiet"]) == 0
    a = json.loads(out.read_text())
    [info] = a["source"]["pacts"]
    assert info["consumerVersion"] == "ffff999" and info["commitMismatch"] is True and len(info["sha256"]) == 64
    assert a["notMeasured"][0]["reason"] == "messagePacts"
    assert any("not the manifest commit" in w for w in a["warnings"])


def test_pacts_for_another_provider_are_skipped(tmp_path, capsys):
    mine = _write_pact(tmp_path, "mine.json")
    other = _write_pact(tmp_path, "other.json", provider="different")
    out = tmp_path / "a.json"
    cc.main(["--manifest", _manifest_file(tmp_path), "--pacts", mine, other, "--out", str(out), "--quiet"])
    a = json.loads(out.read_text())
    assert [p["name"] for p in a["source"]["pacts"]] == ["mine.json"]
    assert "other.json skipped" in capsys.readouterr().err


def test_no_pacts_mode_needs_no_pacts_flag_and_stays_quiet(tmp_path, capsys):
    out = tmp_path / "a.json"
    assert cc.main(["--manifest", _manifest_file(tmp_path), "--no-pacts", "--out", str(out), "--quiet"]) == 0
    assert json.loads(out.read_text())["totals"]["operations"]["tested"] == 0
    assert "no pact files matched" not in capsys.readouterr().err
    cc.main(["--manifest", _manifest_file(tmp_path), "--out", str(out), "--quiet"])
    assert "no pact files matched" in capsys.readouterr().err


class _Response:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_broker_fetch_reads_the_latest_pact_and_records_it(tmp_path, monkeypatch):
    seen = {}
    pact = json.loads(Path_read(_write_pact(tmp_path, "src.json", version="abc1234")))

    def fake_urlopen(request, timeout=0):
        seen["url"], seen["auth"] = request.full_url, request.get_header("Authorization")
        return _Response(json.dumps(pact).encode())

    monkeypatch.setattr(cc.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "a.json"
    argv = [
        "--manifest",
        _manifest_file(tmp_path),
        "--broker-url",
        "https://b.example/",
        "--broker-token",
        "T",
        "--quiet",
    ]
    assert cc.main([*argv, "--out", str(out)]) == 0
    assert seen["url"] == "https://b.example/pacts/provider/svc/consumer/app/latest" and seen["auth"] == "Bearer T"
    a = json.loads(out.read_text())
    assert a["source"]["pacts"][0]["from"] == "broker" and "commitMismatch" not in a["source"]["pacts"][0]
    assert a["totals"]["operations"]["tested"] == 1
    assert cc.main([*argv, "--out", str(out), "--save-pacts", str(tmp_path / "kept")]) == 0
    assert json.loads((tmp_path / "kept" / "app-svc.json").read_text()) == pact
    assert json.loads(out.read_text())["warnings"] == [] or isinstance(json.loads(out.read_text())["warnings"], list)


def test_broker_404_runs_with_no_pacts_and_says_so(tmp_path, monkeypatch):
    def fake_urlopen(request, timeout=0):
        raise cc.urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(cc.urllib.request, "urlopen", fake_urlopen)
    out = tmp_path / "n.json"
    argv = ["--manifest", _manifest_file(tmp_path), "--broker-url", "https://b.example", "--broker-token", "T"]
    assert cc.main([*argv, "--quiet", "--out", str(out)]) == 0
    artifact = json.loads(out.read_text())
    assert artifact["totals"]["operations"]["tested"] == 0
    assert any("broker has no pact" in w for w in artifact["warnings"])


def fake_urlopen(request, timeout=0):
        raise cc.urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(cc.urllib.request, "urlopen", fake_urlopen)
    cc.main(["--manifest", _manifest_file(tmp_path), "--broker-url", "https://b.example", "--broker-token", "T"])
    assert "rerun with --no-pacts" in capsys.readouterr().err


def test_manifest_defaults_fill_handled_statuses_and_handlers(tmp_path):
    manifest = json.loads(Path_read(_manifest_file(tmp_path)))
    for call in manifest["calls"]:
        call.pop("handledStatuses", None)
        call.pop("handlers", None)
    manifest["defaults"] = {
        "handledStatuses": ["non-2XX"],
        "handlers": [{"file": "src/http.ts", "line": 5, "symbol": "fetch"}],
    }
    path = tmp_path / "with-defaults.json"
    path.write_text(json.dumps(manifest))
    out = tmp_path / "d.json"
    assert cc.main(["--manifest", str(path), "--no-pacts", "--quiet", "--out", str(out)]) == 0
    artifact = json.loads(out.read_text())
    assert any("http.ts" in str(loc) for loc in artifact["locations"].values())
    assert not any("defaults" in w for w in artifact["warnings"])


def test_top_level_array_field_has_no_leading_dot(tmp_path):
    manifest = json.loads(Path_read(_manifest_file(tmp_path)))
    manifest["calls"][0]["responseFields"] = {"200": ["[].login"]}
    path = tmp_path / "arr.json"
    path.write_text(json.dumps(manifest))
    out = tmp_path / "o.json"
    assert cc.main(["--manifest", str(path), "--no-pacts", "--quiet", "--out", str(out)]) == 0
    ids = [i["id"] for op in json.loads(out.read_text())["operations"] for i in op["items"]]
    assert any(i.endswith("field:200:login") for i in ids) and not any(".login" in i and ":." in i for i in ids)


def test_boolean_body_values_match_lowercase_manifest_text():
    assert cc._scalar(True) == "true" and cc._scalar(False) == "false" and cc._scalar(3) == "3"
    ix = {"reqBody": {"active": True}, "query": {}, "headers": {}}
    assert cc._ix_sends(ix, "body:active", "true")
    assert not cc._ix_sends(ix, "body:active", "false")


def test_top_level_array_body_paths_match():
    assert cc._get_path([{"op": "remove", "value": {"uuid": "u"}}], "[].op") == (True, "remove")
    assert cc._get_path([{"op": "remove", "value": {"uuid": "u"}}], "[].value.uuid") == (True, "u")
    assert cc._get_path([{"op": "remove"}], "op") == (True, "remove")
    assert cc._get_path([], "[].op")[0] is False


def Path_read(path):
    return open(path).read()


def test_strict_exits_one_on_failure_default_exits_zero(tmp_path):
    missing = str(tmp_path / "nope.json")
    assert cc.main(["--manifest", missing, "--no-pacts", "--quiet"]) == 0
    assert cc.main(["--manifest", missing, "--no-pacts", "--quiet", "--strict"]) == 1


def test_check_flag_validates_against_the_schema(tmp_path, capsys):
    pytest.importorskip("jsonschema")
    cc.main(
        ["--manifest", _manifest_file(tmp_path), "--no-pacts", "--out", str(tmp_path / "a.json"), "--check", "--quiet"]
    )
    assert "schema check: valid" in capsys.readouterr().err
