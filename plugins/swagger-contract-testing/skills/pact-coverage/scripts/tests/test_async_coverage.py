import json
import pathlib

import pytest
from async_coverage import (
    build_pact_message,
    compute_async_coverage,
    extract_async_operations,
    extract_pact_messages,
    is_asyncapi,
    load_asyncapi,
    match_message,
    run,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
ASYNC_SPEC = str(FIXTURES / "asyncapi.yaml")


@pytest.fixture
def spec():
    return load_asyncapi(ASYNC_SPEC)


class TestLoad:
    def test_is_asyncapi_true(self):
        assert is_asyncapi(ASYNC_SPEC)

    def test_is_asyncapi_false_for_openapi(self):
        assert not is_asyncapi(str(FIXTURES / "openapi.yaml"))

    def test_is_asyncapi_false_for_missing_file(self):
        assert not is_asyncapi("/nonexistent/spec.yaml")

    def test_load_raises_on_missing_file(self):
        with pytest.raises((OSError, ValueError)):
            load_asyncapi("/nonexistent/spec.yaml")


class TestExtractAsyncOperations:
    def test_default_scope_is_send_only(self, spec):
        assert set(extract_async_operations(spec)) == {"publishOrderCreated", "publishOrderEvents"}

    def test_include_receive(self, spec):
        ops = extract_async_operations(spec, frozenset({"send", "receive"}))
        assert set(ops) == {"publishOrderCreated", "publishOrderEvents", "consumePlaceOrder"}

    def test_address_and_action(self, spec):
        op = extract_async_operations(spec)["publishOrderCreated"]
        assert op["address"] == "orders.created"
        assert op["action"] == "send"

    def test_payload_required_resolves_ref(self, spec):
        msg = extract_async_operations(spec)["publishOrderCreated"]["messages"]["orderCreated"]
        assert msg["payload_required"] == {"orderId", "status"}

    def test_header_required(self, spec):
        msg = extract_async_operations(spec)["publishOrderCreated"]["messages"]["orderCreated"]
        assert msg["header_required"] == {"correlationId"}

    def test_operation_messages_subset(self, spec):
        ops = extract_async_operations(spec)
        assert set(ops["publishOrderEvents"]["messages"]) == {"orderShipped", "orderCancelled"}

    def test_no_messages_list_uses_all_channel_messages(self, spec):
        ops = extract_async_operations(spec)
        assert set(ops["publishOrderCreated"]["messages"]) == {"orderCreated"}

    def test_const_discriminator(self, spec):
        msg = extract_async_operations(spec)["publishOrderEvents"]["messages"]["orderShipped"]
        assert msg["discriminators"] == {"status": ["SHIPPED"]}

    def test_enum_discriminator_through_ref(self, spec):
        msg = extract_async_operations(spec)["publishOrderCreated"]["messages"]["orderCreated"]
        assert msg["discriminators"] == {"status": ["CREATED"]}

    def test_names_include_key_and_name(self, spec):
        msg = extract_async_operations(spec)["publishOrderEvents"]["messages"]["orderShipped"]
        assert "orderShipped" in msg["names"]
        assert "OrderShipped" in msg["names"]

    def test_consumer_channels_filter(self, spec):
        ops = extract_async_operations(spec, channels={"orders.created"})
        assert set(ops) == {"publishOrderCreated"}

    def test_ref_cycle_does_not_hang(self):
        spec = {
            "asyncapi": "3.0.0",
            "channels": {"c": {"address": "t", "messages": {"m": {"payload": {"$ref": "#/components/schemas/A"}}}}},
            "operations": {"o": {"action": "send", "channel": {"$ref": "#/channels/c"}}},
            "components": {
                "schemas": {
                    "A": {"allOf": [{"$ref": "#/components/schemas/A"}], "required": ["id"]},
                }
            },
        }
        msg = extract_async_operations(spec)["o"]["messages"]["m"]
        assert msg["payload_required"] == {"id"}

    def test_multi_format_schema_payload(self):
        spec = {
            "asyncapi": "3.0.0",
            "channels": {
                "c": {
                    "address": "t",
                    "messages": {
                        "m": {
                            "payload": {
                                "schemaFormat": "application/vnd.aai.asyncapi+json;version=3.0.0",
                                "schema": {"type": "object", "required": ["id"]},
                            }
                        }
                    },
                }
            },
            "operations": {"o": {"action": "send", "channel": {"$ref": "#/channels/c"}}},
        }
        assert extract_async_operations(spec)["o"]["messages"]["m"]["payload_required"] == {"id"}


def _load_pact(name):
    return json.loads((FIXTURES / name).read_text())


class TestExtractPactMessages:
    def test_v3_messages(self):
        msgs = extract_pact_messages(_load_pact("async.pact.v3.json"))
        assert [m["description"] for m in msgs] == ["an order created event", "OrderShipped", "mystery"]
        assert msgs[0]["fields"] == {"orderId", "status"}
        assert msgs[0]["metadata"]["topic"] == "orders.created"

    def test_v3_missing_metadata_is_empty(self):
        assert extract_pact_messages(_load_pact("async.pact.v3.json"))[2]["metadata"] == {}

    def test_v4_skips_http_and_unwraps_content(self):
        msgs = extract_pact_messages(_load_pact("async.pact.v4.json"))
        assert len(msgs) == 1
        assert msgs[0]["fields"] == {"orderId", "status", "reason"}
        assert msgs[0]["contents"]["status"] == "CANCELLED"

    def test_http_only_pact_yields_no_messages(self):
        pact = {"interactions": [{"type": "Synchronous/HTTP", "request": {}, "response": {}}]}
        assert extract_pact_messages(pact) == []

    def test_pact_without_messages(self):
        assert extract_pact_messages({}) == []

    def test_string_contents_is_json_parsed(self):
        msg = build_pact_message("d", '{"orderId": "1"}', {})
        assert msg["fields"] == {"orderId"}

    def test_unparseable_or_non_object_contents_has_no_fields(self):
        assert build_pact_message("d", "not json", {})["fields"] == set()
        assert build_pact_message("d", [1, 2], {})["fields"] == set()
        assert build_pact_message("d", None, None)["metadata"] == {}


def _msg(description="", contents=None, metadata=None):
    return build_pact_message(description, contents, metadata)


def _inline(messages, action="send"):
    return {
        "asyncapi": "3.0.0",
        "channels": {"c": {"address": "t", "messages": messages}},
        "operations": {"o": {"action": action, "channel": {"$ref": "#/channels/c"}}},
    }


class TestMatchMessage:
    @pytest.fixture
    def ops(self, spec):
        return extract_async_operations(spec)

    def test_channel_hint_single_message(self, ops):
        msg = _msg("x", {"orderId": "1", "status": "CREATED"}, {"topic": "orders.created"})
        assert match_message(msg, ops) == ("matched", [("publishOrderCreated", "orderCreated")])

    def test_channel_hint_key_is_case_insensitive(self, ops):
        msg = _msg("x", {}, {"Topic": "orders.created"})
        assert match_message(msg, ops)[0] == "matched"

    def test_channel_hint_matches_even_with_missing_fields(self, ops):
        msg = _msg("x", {}, {"topic": "orders.created"})
        assert match_message(msg, ops) == ("matched", [("publishOrderCreated", "orderCreated")])

    def test_name_narrows_within_channel(self, ops):
        msg = _msg("OrderShipped", {"orderId": "1", "status": "SHIPPED"}, {"kafka_topic": "orders.events"})
        assert match_message(msg, ops) == ("matched", [("publishOrderEvents", "orderShipped")])

    def test_structure_with_discriminator_within_channel(self, ops):
        msg = _msg("x", {"orderId": "1", "status": "CANCELLED", "reason": "r"}, {"topic": "orders.events"})
        assert match_message(msg, ops) == ("matched", [("publishOrderEvents", "orderCancelled")])

    def test_structure_only_without_metadata(self, ops):
        msg = _msg("x", {"orderId": "1", "status": "CREATED"})
        assert match_message(msg, ops) == ("matched", [("publishOrderCreated", "orderCreated")])

    def test_discriminator_mismatch_is_unmatched(self, ops):
        msg = _msg("x", {"orderId": "1", "status": "REFUNDED"})
        assert match_message(msg, ops) == ("unmatched", [])

    def test_unmatched(self, ops):
        assert match_message(_msg("mystery", {"foo": 1}), ops) == ("unmatched", [])

    def test_ambiguous(self):
        payload = {"type": "object", "required": ["id"]}
        ops = extract_async_operations(_inline({"a": {"payload": payload}, "b": {"payload": payload}}))
        status, pairs = match_message(_msg("x", {"id": 1}), ops)
        assert status == "ambiguous"
        assert sorted(pairs) == [("o", "a"), ("o", "b")]

    def test_same_message_under_two_operations_matches_both(self):
        spec = _inline({"a": {"payload": {"type": "object", "required": ["id"]}}})
        spec["operations"]["o2"] = {"action": "receive", "channel": {"$ref": "#/channels/c"}}
        ops = extract_async_operations(spec, frozenset({"send", "receive"}))
        status, pairs = match_message(_msg("x", {"id": 1}), ops)
        assert status == "matched"
        assert sorted(pairs) == [("o", "a"), ("o2", "a")]


def _fixture_messages():
    return extract_pact_messages(_load_pact("async.pact.v3.json")) + extract_pact_messages(
        _load_pact("async.pact.v4.json")
    )


class TestComputeAsyncCoverage:
    @pytest.fixture
    def report(self, spec):
        return compute_async_coverage(extract_async_operations(spec), _fixture_messages())

    def test_operations_covered(self, report):
        assert report["operations"]["publishOrderCreated"]["covered"] is True
        assert report["operations"]["publishOrderEvents"]["covered"] is True

    def test_all_messages_covered(self, report):
        assert {k: v["covered"] for k, v in report["messages"].items()} == {
            "publishOrderCreated/orderCreated": True,
            "publishOrderEvents/orderShipped": True,
            "publishOrderEvents/orderCancelled": True,
        }

    def test_missing_payload_field(self, report):
        assert report["payload_fields"]["publishOrderEvents/orderShipped"]["missing"] == ["carrier"]
        assert report["payload_fields"]["publishOrderEvents/orderCancelled"]["missing"] == []

    def test_header_fields_present(self, report):
        assert report["header_fields"]["publishOrderCreated/orderCreated"]["missing"] == []

    def test_unmatched_listed(self, report):
        assert report["unmatched"] == [{"description": "mystery"}]

    def test_has_gaps(self, report):
        assert report["has_gaps"] is True

    def test_uncovered_operation(self, spec):
        report = compute_async_coverage(
            extract_async_operations(spec), extract_pact_messages(_load_pact("async.pact.v4.json"))
        )
        assert report["operations"]["publishOrderCreated"]["covered"] is False
        assert report["messages"]["publishOrderCreated/orderCreated"]["covered"] is False
        assert "publishOrderCreated/orderCreated" not in report["payload_fields"]

    def test_http_only_pact_leaves_everything_uncovered(self, spec):
        report = compute_async_coverage(extract_async_operations(spec), [])
        assert not any(o["covered"] for o in report["operations"].values())
        assert report["has_gaps"] is True

    def test_header_names_compare_case_insensitively(self):
        spec = _inline({"a": {"headers": {"required": ["X-Trace"]}, "payload": {"required": ["id"]}}})
        report = compute_async_coverage(extract_async_operations(spec), [_msg("a", {"id": 1}, {"x-trace": "t"})])
        assert report["header_fields"]["o/a"]["missing"] == []
        assert report["has_gaps"] is False

    def test_unmatched_does_not_cause_gaps(self):
        spec = _inline({"a": {"payload": {"required": ["id"]}}})
        report = compute_async_coverage(
            extract_async_operations(spec), [_msg("a", {"id": 1}), _msg("zzz", {"other": 1})]
        )
        assert report["unmatched"] == [{"description": "zzz"}]
        assert report["has_gaps"] is False

    def test_ambiguous_reported_with_candidates(self):
        payload = {"required": ["id"]}
        spec = _inline({"a": {"payload": payload}, "b": {"payload": payload}})
        report = compute_async_coverage(extract_async_operations(spec), [_msg("x", {"id": 1})])
        assert report["ambiguous"] == [{"description": "x", "candidates": ["t/a", "t/b"]}]


class TestRun:
    def _run(self, spec_path, capsys, **kwargs):
        defaults = {"include_actions": frozenset({"send"}), "consumer_channels": None, "as_json": False}
        code = run(spec_path, _fixture_messages(), ["a.json"], **{**defaults, **kwargs})
        return code, capsys.readouterr()

    def test_gaps_exit_1_and_text_report(self, capsys):
        code, out = self._run(ASYNC_SPEC, capsys)
        assert code == 1
        assert "missing: carrier" in out.out
        assert "mystery" in out.out

    def test_json_output(self, capsys):
        code, out = self._run(ASYNC_SPEC, capsys, as_json=True)
        data = json.loads(out.out)
        assert code == 1
        assert data["has_gaps"] is True
        assert data["consumer_filtered"] is False

    def test_full_coverage_exit_0(self, capsys):
        code, out = self._run(ASYNC_SPEC, capsys, consumer_channels={"orders.created"})
        assert code == 0
        assert "orders.created" in out.out

    def test_consumer_channels_matching_nothing_exit_2(self, capsys):
        code, out = self._run(ASYNC_SPEC, capsys, consumer_channels={"nope"})
        assert code == 2
        assert "No operations" in out.err

    def test_asyncapi_2x_exit_2(self, tmp_path, capsys):
        path = tmp_path / "old.yaml"
        path.write_text("asyncapi: 2.6.0\ninfo: {title: x, version: '1'}\nchannels: {}\n")
        code, out = self._run(str(path), capsys)
        assert code == 2
        assert "3.x" in out.err

    def test_missing_spec_exit_2(self, capsys):
        code, _ = self._run("/nonexistent.yaml", capsys)
        assert code == 2


class TestReviewFixes:
    def test_topic_outside_scope_is_unmatched(self, spec):
        ops = extract_async_operations(spec)
        msg = _msg("x", {"orderId": "1", "status": "CREATED"}, {"topic": "payments.created"})
        assert match_message(msg, ops) == ("unmatched", [])

    def test_unconstrained_message_does_not_match_structurally(self):
        ops = extract_async_operations(_inline({"a": {"payload": {"$ref": "other.yaml#/X"}}}))
        assert match_message(_msg("x", {"foo": 1}, {"topic": "zzz"}), ops) == ("unmatched", [])
        assert match_message(_msg("x", {"foo": 1}), ops) == ("unmatched", [])

    def test_branching_ref_cycle_is_fast(self):
        import time

        spec = _inline({"m": {"payload": {"$ref": "#/components/schemas/S"}}})
        spec["components"] = {
            "schemas": {
                "S": {
                    "allOf": [{"$ref": "#/components/schemas/S"}, {"$ref": "#/components/schemas/S"}],
                    "required": ["x"],
                    "properties": {"k": {"const": 1}},
                }
            }
        }
        start = time.monotonic()
        msg = extract_async_operations(spec)["o"]["messages"]["m"]
        assert time.monotonic() - start < 1
        assert msg["payload_required"] == {"x"}

    @pytest.mark.parametrize("payload", [{"allOf": 3}, {"required": True}, {"required": "orderId"}, {"oneOf": "x"}])
    def test_malformed_schema_keywords_are_ignored(self, payload):
        msg = extract_async_operations(_inline({"m": {"payload": payload}}))["o"]["messages"]["m"]
        assert msg["payload_required"] == set()

    @pytest.mark.parametrize("pact", [{"messages": 5}, {"interactions": 5}, {"messages": ["x", None]}])
    def test_malformed_pact_collections_yield_no_messages(self, pact):
        assert extract_pact_messages(pact) == []

    def test_oneof_variant_matches_structurally(self):
        payload = {"oneOf": [{"required": ["a"]}, {"required": ["b"]}], "required": ["id"]}
        ops = extract_async_operations(_inline({"m": {"payload": payload}}))
        assert match_message(_msg("x", {"id": 1}), ops) == ("matched", [("o", "m")])
