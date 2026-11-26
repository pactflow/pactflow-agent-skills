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
    ixs = cc.load_interactions([str(FIX / pact)])
    info, ops = cc.load_spec_operations(str(FIX / spec)) if spec else (None, None)
    return cc.build_artifact(m, ixs, info, ops, mode, **kw)


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
    assert hashed and all(set(loc) <= {"kind", "commit", "hash"} for loc in hashed.values())
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

    import jsonschema

    refs = Path(__file__).resolve().parents[2] / "references"
    schema = json.loads((refs / "coverage-artifact-1.0.0.schema.json").read_text())
    sample = json.loads((refs / "samples" / "provider-coverage-artifact-sample-1.0.0.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(sample)
