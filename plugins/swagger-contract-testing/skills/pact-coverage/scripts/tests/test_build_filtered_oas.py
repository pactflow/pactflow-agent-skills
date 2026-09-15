"""Tests for build_filtered_oas.py."""
import pathlib
import sys
import unittest.mock as mock

import pytest
import yaml

# build_filtered_oas is on sys.path via conftest.py (scripts/ parent inserted)
from build_filtered_oas import (
    build_filtered_oas,
    extract_http_method,
    extract_return_type,
    extract_url_path,
    find_http_wrapper_symbol,
    get_routes_via_wrapper_callers,
    get_schema_properties,
    normalise_type_name,
    parse_body_xml,
    parse_deserialization_xml,
    parse_routes_xml,
    parse_type_fields_xml,
    resolve_response_fields,
    routes_from_json,
    structural_match,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def kg_xml() -> str:
    return (FIXTURES_DIR / "consumer_kg.xml").read_text()


@pytest.fixture
def sample_oas() -> dict:
    return yaml.safe_load((FIXTURES_DIR / "openapi.yaml").read_text())


# ─── 1. parse_routes_xml ──────────────────────────────────────────────────────

class TestParseRoutesXml:
    def test_parses_routes(self, kg_xml):
        routes, confidence, over_ceiling = parse_routes_xml(kg_xml)
        assert len(routes) == 2
        assert confidence == "high"
        assert over_ceiling is False

    def test_route_fields(self, kg_xml):
        routes, _, _ = parse_routes_xml(kg_xml)
        get_route = next(r for r in routes if r["method"] == "GET")
        assert get_route["path"] == "/orders/{id}"
        assert get_route["from"] == "getOrder"
        assert get_route["to"] == "get_order"

    def test_method_uppercased(self, kg_xml):
        routes, _, _ = parse_routes_xml(kg_xml)
        for route in routes:
            assert route["method"] == route["method"].upper()

    def test_over_ceiling_flag(self):
        xml = '<r confidence="low" over_ceiling="1"><routes><route method="get" path="/x" from="" to=""/></routes></r>'
        routes, confidence, over_ceiling = parse_routes_xml(xml)
        assert confidence == "low"
        assert over_ceiling is True
        assert len(routes) == 1

    def test_default_confidence_low(self):
        xml = '<r><routes><route method="get" path="/x" from="" to=""/></routes></r>'
        routes, confidence, _ = parse_routes_xml(xml)
        assert confidence == "low"

    def test_malformed_xml_returns_empty(self):
        routes, confidence, over_ceiling = parse_routes_xml("not xml at all <<<")
        assert routes == []
        assert confidence == "low"
        assert over_ceiling is False


# ─── 2. parse_body_xml ────────────────────────────────────────────────────────

class TestParseBodyXml:
    def test_extracts_body_text(self):
        xml = "<r><s><body>function foo() { return 1; }</body></s></r>"
        result = parse_body_xml(xml)
        assert "function foo" in result

    def test_multiple_bodies_joined(self):
        xml = "<r><s><body>line1</body></s><s><body>line2</body></s></r>"
        result = parse_body_xml(xml)
        assert "line1" in result
        assert "line2" in result

    def test_empty_on_malformed_xml(self):
        result = parse_body_xml("<<<bad xml")
        assert result == ""

    def test_from_fixture_kg(self, kg_xml):
        # The fixture has multiple body elements; all should be extracted
        result = parse_body_xml(kg_xml)
        assert "getOrder" in result or "axios" in result


# ─── 3. parse_type_fields_xml ─────────────────────────────────────────────────

class TestParseTypeFieldsXml:
    def test_extracts_typescript_interface_fields(self, kg_xml):
        required, optional = parse_type_fields_xml(kg_xml, "Order")
        assert "id" in required
        assert "price" in required
        assert "description" in required

    def test_extracts_order_summary_fields(self, kg_xml):
        required, optional = parse_type_fields_xml(kg_xml, "OrderSummary")
        assert "id" in required
        assert "status" in required

    def test_unknown_type_returns_empty(self, kg_xml):
        required, optional = parse_type_fields_xml(kg_xml, "NonExistentType")
        assert required == set()
        assert optional == set()

    def test_only_matches_iface_type(self, kg_xml):
        # getOrder is t="fn", not iface/cls/struct/type — must not match
        required, optional = parse_type_fields_xml(kg_xml, "getOrder")
        assert required == set()

    def test_malformed_xml_returns_empty(self):
        required, optional = parse_type_fields_xml("<<<bad", "Order")
        assert required == set()
        assert optional == set()

    def test_python_typeddict_fields(self):
        xml = """<r><s t="type" n="User"><body>class User(TypedDict):
    name: str
    age: int
</body></s></r>"""
        required, optional = parse_type_fields_xml(xml, "User")
        assert "name" in required
        assert "age" in required

    def test_typescript_optional_fields(self):
        xml = """<r><s t="iface" n="Order"><body>interface Order {
  id: number;
  price: number;
  items?: OrderItems;
}</body></s></r>"""
        required, optional = parse_type_fields_xml(xml, "Order")
        assert "id" in required
        assert "price" in required
        assert "items" in optional
        assert "items" not in required

    def test_python_optional_fields_with_default(self):
        xml = """<r><s t="cls" n="Order"><body>@dataclass
class Order:
    id: int
    price: float
    description: str = ""
</body></s></r>"""
        required, optional = parse_type_fields_xml(xml, "Order")
        assert "id" in required
        assert "price" in required
        assert "description" in optional
        assert "description" not in required

    def test_optional_fields_not_in_required(self):
        xml = """<r><s t="iface" n="T"><body>interface T {
  a: number;
  b?: string;
  c?: boolean;
}</body></s></r>"""
        required, optional = parse_type_fields_xml(xml, "T")
        assert required == {"a"}
        assert optional == {"b", "c"}

    def test_nested_inline_object_not_captured_as_top_level(self):
        xml = """<r><s t="iface" n="Order"><body>interface Order {
  id: number;
  metadata: {
    createdAt: string;
    updatedAt: string;
  };
}</body></s></r>"""
        required, optional = parse_type_fields_xml(xml, "Order")
        assert "id" in required
        assert "metadata" in required
        assert "createdAt" not in required
        assert "createdAt" not in optional
        assert "updatedAt" not in required
        assert "updatedAt" not in optional


# ─── 4. extract_return_type ───────────────────────────────────────────────────

class TestExtractReturnType:
    def test_typescript_promise(self):
        body = "async function getOrder(id: string): Promise<Order> { return x; }"
        assert extract_return_type(body) == "Order"

    def test_typescript_as_cast(self):
        body = "return resp.data as Order;"
        assert extract_return_type(body) == "Order"

    def test_python_arrow(self):
        body = "def get_order(id: str) -> Order:\n    pass"
        assert extract_return_type(body) == "Order"

    def test_python_optional(self):
        body = "def get_order(id: str) -> Optional[Order]:\n    pass"
        assert extract_return_type(body) == "Order"

    def test_skips_known_type_names(self):
        body = "return resp.data as Response;"
        # "Response" is in SKIP_TYPE_NAMES, so should not match
        result = extract_return_type(body)
        assert result != "Response"

    def test_returns_none_when_no_match(self):
        body = "const x = 1; console.log(x);"
        assert extract_return_type(body) is None

    def test_typescript_const_annotation(self):
        body = "const order: Order = await fetchOrder();"
        assert extract_return_type(body) == "Order"

    def test_list_generic_container(self):
        body = "def get_orders() -> List[Order]:\n    pass"
        assert extract_return_type(body) == "Order"

    def test_dict_generic_container(self):
        body = "def get_map() -> Dict[str, Order]:\n    pass"
        assert extract_return_type(body) == "Order"

    def test_typescript_array_type(self):
        body = "async getOrders(): Array<Order> { return []; }"
        assert extract_return_type(body) == "Order"


# ─── 5. normalise_type_name ───────────────────────────────────────────────────

class TestNormaliseTypeName:
    def test_strips_response_suffix(self):
        assert normalise_type_name("OrderResponse") == "Order"

    def test_strips_dto_suffix(self):
        assert normalise_type_name("OrderDto") == "Order"

    def test_strips_i_prefix(self):
        assert normalise_type_name("IOrder") == "Order"

    def test_snake_case_to_camel(self):
        assert normalise_type_name("order_item") == "OrderItem"

    def test_no_change_on_clean_name(self):
        assert normalise_type_name("Order") == "Order"

    def test_strips_longest_suffix_first(self):
        # "Data" and "Payload" are both suffixes — test that longest match wins
        # "OrderPayloadData" — "Data" is shorter but appears last; should strip "Data"
        result = normalise_type_name("OrderPayloadData")
        assert result == "OrderPayload"

    def test_i_prefix_not_stripped_if_no_uppercase_next(self):
        # "invoice" — starts with "I" but next char is lowercase → should not strip
        assert normalise_type_name("invoice") == "invoice"


# ─── 6. get_schema_properties ─────────────────────────────────────────────────

class TestGetSchemaProperties:
    def test_returns_property_keys(self, sample_oas):
        props = get_schema_properties("Order", sample_oas)
        assert props == {"id", "status", "total"}

    def test_returns_empty_for_unknown_schema(self, sample_oas):
        props = get_schema_properties("NonExistent", sample_oas)
        assert props == set()

    def test_create_order_request_props(self, sample_oas):
        props = get_schema_properties("CreateOrderRequest", sample_oas)
        assert props == {"customerId", "orderId", "items"}


# ─── 7. structural_match ──────────────────────────────────────────────────────

class TestStructuralMatch:
    def test_high_overlap_finds_correct_schema(self, sample_oas):
        # Order has {id, status, total}; consumer asks for {id, status} → 100% overlap
        schema_name, score = structural_match({"id", "status"}, sample_oas, 0.8)
        assert schema_name == "Order"
        assert score >= 0.8

    def test_below_threshold_returns_none(self, sample_oas):
        # Fields with no overlap with any schema
        schema_name, score = structural_match({"foo", "bar", "baz"}, sample_oas, 0.8)
        assert schema_name is None

    def test_empty_consumer_fields_returns_none(self, sample_oas):
        schema_name, score = structural_match(set(), sample_oas, 0.8)
        assert schema_name is None
        assert score == 0.0

    def test_partial_match_below_threshold(self, sample_oas):
        # One field matches out of many — below 80%
        schema_name, score = structural_match({"id", "foo", "bar", "baz", "qux"}, sample_oas, 0.8)
        # 1/5 = 20% < 80% → None
        assert schema_name is None


# ─── 8. resolve_response_fields ───────────────────────────────────────────────

class TestResolveResponseFields:
    def test_tier1_exact_match(self, sample_oas):
        fields, tier, note = resolve_response_fields("Order", {"id", "status"}, sample_oas)
        assert tier == 1
        assert "exact" in note
        assert fields == {"id", "status"}  # consumer_fields used (non-empty)

    def test_tier1_uses_schema_props_when_consumer_fields_empty(self, sample_oas):
        fields, tier, note = resolve_response_fields("Order", set(), sample_oas)
        assert tier == 1
        assert fields == {"id", "status", "total"}  # falls back to schema props

    def test_tier2_normalised_match(self, sample_oas):
        # "OrderResponse" normalises to "Order" which is in schemas
        fields, tier, note = resolve_response_fields("OrderResponse", {"id", "status"}, sample_oas)
        assert tier == 2
        assert "normalised" in note

    def test_tier3_structural_match(self, sample_oas):
        # "OrderSummary" is not in schemas, doesn't normalise to a schema name,
        # but {id, status} has 100% overlap with Order's {id, status, total}
        fields, tier, note = resolve_response_fields("OrderSummary", {"id", "status"}, sample_oas)
        assert tier == 3
        assert "structural" in note
        assert fields == {"id", "status"}

    def test_tier4_no_match(self, sample_oas):
        # type_name=None and no structural overlap
        fields, tier, note = resolve_response_fields(None, set(), sample_oas)
        assert tier == 4
        assert fields is None

    def test_tier4_no_type_name_no_structural(self, sample_oas):
        fields, tier, note = resolve_response_fields(None, {"foo", "bar", "baz"}, sample_oas)
        # {foo, bar, baz} has no overlap with any OAS schema → Tier 4
        assert tier == 4


# ─── 9. build_filtered_oas ────────────────────────────────────────────────────

class TestBuildFilteredOas:
    def _make_routes(self, sample_oas):
        """Construct two enriched routes: GET with Tier 1, POST with Tier 4."""
        return [
            {
                "method": "GET",
                "path": "/orders/{id}",
                "from": "getOrder",
                "to": "get_order",
                "type_name": "Order",
                "consumer_fields": ["id", "price"],
                # resolved_fields = intersection of {id, price} with Order props {id, status, total} = {id}
                "resolved_fields": ["id"],
                "tier": 1,
                "tier_note": "exact → Order",
            },
            {
                "method": "POST",
                "path": "/orders",
                "from": "createOrder",
                "to": "create_order",
                "type_name": None,
                "consumer_fields": [],
                "resolved_fields": None,
                "tier": 4,
                "tier_note": "no consumer-root — OAS required[] used",
            },
        ]

    def test_produces_filtered_paths(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        assert "/orders/{id}" in filtered["paths"]
        assert "/orders" in filtered["paths"]

    def test_only_matched_operations_present(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        # GET should be present on /orders/{id}
        assert "get" in filtered["paths"]["/orders/{id}"]
        # POST should be present on /orders
        assert "post" in filtered["paths"]["/orders"]

    def test_tier1_narrows_required_fields(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        # GET /orders/{id} response 200 schema should have required narrowed
        response_200 = filtered["paths"]["/orders/{id}"]["get"]["responses"]["200"]
        schema = response_200["content"]["application/json"]["schema"]
        # resolved_fields = ["id"], properties = {id, status, total}
        # intersection = {"id"}
        assert schema["required"] == ["id"]

    def test_tier4_keeps_oas_required(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        # POST /orders 201 response uses Tier 4 (resolved_fields=None) — required unchanged
        response_201 = filtered["paths"]["/orders"]["post"]["responses"]["201"]
        schema = response_201["content"]["application/json"]["schema"]
        # The ref is preserved (not resolved inline) when resolved_fields is None
        # so "required" comes from the original OAS schema via $ref
        assert "$ref" in schema or "required" in schema

    def test_x_consumer_type_match_annotation_present(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        get_op = filtered["paths"]["/orders/{id}"]["get"]
        assert "x-consumer-type-match" in get_op
        ann = get_op["x-consumer-type-match"]
        assert ann["tier"] == 1
        assert ann["consumer-type"] == "Order"
        assert "id" in ann["consumer-fields"]

    def test_x_consumer_type_match_tier4(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        post_op = filtered["paths"]["/orders"]["post"]
        assert "x-consumer-type-match" in post_op
        ann = post_op["x-consumer-type-match"]
        assert ann["tier"] == 4

    def test_unmatched_route_skipped(self, sample_oas):
        routes = [
            {
                "method": "DELETE",
                "path": "/nonexistent",
                "from": "deleteX",
                "to": "delete_x",
                "type_name": None,
                "consumer_fields": [],
                "resolved_fields": None,
                "tier": 4,
                "tier_note": "no consumer-root — OAS required[] used",
            }
        ]
        filtered, _ = build_filtered_oas(routes, sample_oas)
        assert "/nonexistent" not in filtered["paths"]
        assert filtered["paths"] == {}

    def test_preserves_other_oas_sections(self, sample_oas):
        routes = self._make_routes(sample_oas)
        filtered, _ = build_filtered_oas(routes, sample_oas)
        # info and components should be carried over
        assert "info" in filtered
        assert "components" in filtered

    def test_empty_intersection_preserves_oas_required(self, sample_oas):
        """When consumer fields don't overlap schema properties, OAS required[] is preserved."""
        routes = [{
            "method": "GET",
            "path": "/orders/{id}",
            "from": "getOrder",
            "to": "get_order",
            "type_name": "Order",
            "consumer_fields": ["foo", "bar"],
            "resolved_fields": ["foo", "bar"],  # no overlap with OAS Order props {id,status,total}
            "tier": 3,
            "tier_note": "structural → Order (75%)",
        }]
        filtered, _ = build_filtered_oas(routes, sample_oas)
        response_200 = filtered["paths"]["/orders/{id}"]["get"]["responses"]["200"]
        schema = response_200["content"]["application/json"]["schema"]
        # Empty intersection — OAS required[] must NOT be overwritten with []
        assert schema.get("required") != []


# ─── 10. routes_from_json ─────────────────────────────────────────────────────

class TestRoutesFromJson:
    def test_parses_valid_json(self):
        raw = '[{"method":"GET","path":"/orders/{id}"},{"method":"POST","path":"/orders"}]'
        routes = routes_from_json(raw)
        assert len(routes) == 2
        assert routes[0]["method"] == "get"
        assert routes[0]["path"] == "/orders/{id}"

    def test_method_lowercased(self):
        routes = routes_from_json('[{"method":"DELETE","path":"/x"}]')
        assert routes[0]["method"] == "delete"

    def test_all_routes_are_tier4(self):
        routes = routes_from_json('[{"method":"GET","path":"/x"}]')
        assert routes[0]["tier"] == 4
        assert routes[0]["resolved_fields"] is None

    def test_deduplicates(self):
        raw = '[{"method":"GET","path":"/x"},{"method":"GET","path":"/x"}]'
        routes = routes_from_json(raw)
        assert len(routes) == 1

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="invalid"):
            routes_from_json("not json")

    def test_non_array_raises(self):
        with pytest.raises(ValueError, match="array"):
            routes_from_json('{"method":"GET","path":"/x"}')

    def test_missing_method_raises(self):
        with pytest.raises(ValueError, match="method"):
            routes_from_json('[{"path":"/x"}]')

    def test_missing_path_raises(self):
        with pytest.raises(ValueError, match="path"):
            routes_from_json('[{"method":"GET"}]')

    def test_empty_array(self):
        routes = routes_from_json("[]")
        assert routes == []


# ─── 11. extract_url_path ─────────────────────────────────────────────────────

class TestExtractUrlPath:
    def test_typescript_template_literal(self):
        body = "const resp = await axios.get(`/orders/${id}`);"
        assert extract_url_path(body) == "/orders/{param}"

    def test_python_fstring(self):
        body = 'async with session.get(f"{base_url}/orders/{order_id}") as resp:'
        assert extract_url_path(body) == "/orders/{param}"

    def test_plain_string_path(self):
        body = 'session.get("/orders/items")'
        assert extract_url_path(body) == "/orders/items"

    def test_numeric_id_normalised(self):
        body = 'requests.get("/orders/1234")'
        assert extract_url_path(body) == "/orders/{param}"

    def test_full_url_extracts_path(self):
        body = 'fetch("https://api.example.com/orders/items")'
        assert extract_url_path(body) == "/orders/items"

    def test_multi_segment_path(self):
        body = "axios.get(`/orders/${orderId}/items/${itemId}`)"
        assert extract_url_path(body) == "/orders/{param}/items/{param}"

    def test_no_path_returns_none(self):
        assert extract_url_path("x = y + z") is None

    def test_returns_deepest_path(self):
        # Two candidates — prefer the one with more segments
        body = 'session.get("/x"); session.post("/orders/items/details")'
        path = extract_url_path(body)
        assert path == "/orders/items/details"

    def test_short_path_like_v1(self):
        body = 'requests.get("/v1")'
        assert extract_url_path(body) == "/v1"

    def test_fstring_beats_error_message_path(self):
        """f-string API path is preferred over longer plain-string error message."""
        body = (
            'resp = await session.get(f"/orders/{id}")\n'
            'if not resp: raise ValueError("no order at /orders/not-found/details/retry")'
        )
        assert extract_url_path(body) == "/orders/{param}"


# ─── 12. extract_http_method ──────────────────────────────────────────────────

class TestExtractHttpMethod:
    def test_aiohttp_get(self):
        body = "async with session.get(url) as resp:"
        assert extract_http_method(body) == "GET"

    def test_aiohttp_post(self):
        body = "async with self.session.post(url, json=data) as resp:"
        assert extract_http_method(body) == "POST"

    def test_aiohttp_delete(self):
        body = "async with client.delete(f'/orders/{id}') as resp:"
        assert extract_http_method(body) == "DELETE"

    def test_requests_patch(self):
        body = "resp = requests.patch('/orders/1', json=data)"
        assert extract_http_method(body) == "PATCH"

    def test_explicit_method_attribute(self):
        body = 'fetch(url, { method: "PUT", body: JSON.stringify(data) })'
        assert extract_http_method(body) == "PUT"

    def test_axios_post(self):
        body = "const resp = await axios.post('/orders', payload);"
        assert extract_http_method(body) == "POST"

    def test_no_method_returns_none(self):
        assert extract_http_method("x = y + z") is None

    def test_delete_before_get(self):
        # Should not confuse .delete() with .get()
        body = "client.delete('/orders/1')"
        assert extract_http_method(body) == "DELETE"


# ─── 13. parse_deserialization_xml ────────────────────────────────────────────

class TestParseDeserializationXml:
    def test_finds_python_unpacking(self):
        xml = """<r><s t="fn" n="get_order">
  <body>async def get_order(id):
    data = await resp.json()
    return Order(**data)</body>
</s></r>"""
        hits = parse_deserialization_xml(xml)
        assert len(hits) == 1
        assert hits[0]["type_name"] == "Order"
        assert hits[0]["function_name"] == "get_order"

    def test_finds_model_validate(self):
        xml = """<r><s t="fn" n="fetch_user">
  <body>return User.model_validate(await resp.json())</body>
</s></r>"""
        hits = parse_deserialization_xml(xml)
        assert any(h["type_name"] == "User" for h in hits)

    def test_finds_resp_data_as_cast(self):
        xml = """<r><s t="fn" n="getOrder">
  <body>return resp.data as Order;</body>
</s></r>"""
        hits = parse_deserialization_xml(xml)
        assert any(h["type_name"] == "Order" for h in hits)

    def test_skips_non_fn_elements(self):
        xml = """<r><s t="iface" n="Order">
  <body>Order(**data)</body>
</s></r>"""
        hits = parse_deserialization_xml(xml)
        assert hits == []

    def test_skips_skip_type_names(self):
        xml = """<r><s t="fn" n="handle">
  <body>return Response(**data)</body>
</s></r>"""
        hits = parse_deserialization_xml(xml)
        assert not any(h["type_name"] == "Response" for h in hits)

    def test_deduplicates(self):
        xml = """<r><s t="fn" n="get_order">
  <body>return Order(**a); return Order(**b);</body>
</s></r>"""
        hits = parse_deserialization_xml(xml)
        order_hits = [h for h in hits if h["type_name"] == "Order"]
        assert len(order_hits) == 1

    def test_malformed_xml_returns_empty(self):
        assert parse_deserialization_xml("<<<bad") == []


# ─── 14. extract_url_path — encodeURIComponent handling ───────────────────────

class TestExtractUrlPathEncodeUri:
    def test_encode_uri_component_preserves_var_name(self):
        body = "this.http.fetch(`${this.http.baseUrl}/pacticipants/${encodeURIComponent(pacticipantName)}`);"
        path = extract_url_path(body)
        assert path == "/pacticipants/{pacticipantName}"

    def test_encode_uri_multi_segment_preserves_names(self):
        body = (
            "return await this.http.fetch<T>(`${this.http.baseUrl}"
            "/pacticipants/${encodeURIComponent(pacticipantName)}"
            "/versions/${encodeURIComponent(versionNumber)}"
            "/deployed-versions/environment/${encodeURIComponent(environmentId)}`);"
        )
        path = extract_url_path(body)
        assert path == (
            "/pacticipants/{pacticipantName}"
            "/versions/{versionNumber}"
            "/deployed-versions/environment/{environmentId}"
        )

    def test_bare_ts_var_still_becomes_param(self):
        # ${id} without encodeURIComponent → still {param} (existing behaviour preserved)
        body = "axios.get(`/orders/${id}`);"
        assert extract_url_path(body) == "/orders/{param}"

    def test_encode_uri_mixed_with_plain_segment(self):
        body = "`${base}/environments/${encodeURIComponent(envId)}/deployed-versions`"
        path = extract_url_path(body)
        assert path == "/environments/{envId}/deployed-versions"


# ─── 15. get_routes_via_wrapper_callers ───────────────────────────────────────

def _callers_xml(caller_names: list[str]) -> str:
    """Build a minimal <route from="..."> XML for mocking --callers output."""
    routes = "".join(
        f'<route from="{n}" to="HttpClient.fetch" method="" path=""/>'
        for n in caller_names
    )
    return f'<r confidence="high"><routes>{routes}</routes></r>'


def _expand_xml(body: str) -> str:
    """Build a minimal --expand XML with a <body>."""
    return f"<r><s><body>{body}</body></s></r>"


class TestGetRoutesViaWrapperCallers:
    def test_basic_single_caller(self):
        callers_xml = _callers_xml(["listEnvironments"])
        body_xml = _expand_xml(
            'return await this.http.fetch(`${b}/environments`, {method: "GET"});'
        )
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.side_effect = [callers_xml, body_xml]
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert len(routes) == 1
        assert routes[0]["method"] == "GET"
        assert routes[0]["path"] == "/environments"
        assert routes[0]["from"] == "listEnvironments"

    def test_encode_uri_param_preserved_in_route(self):
        callers_xml = _callers_xml(["getPacticipant"])
        body_xml = _expand_xml(
            "return await this.http.fetch("
            "`${b}/pacticipants/${encodeURIComponent(name)}`, {method: \"GET\"});"
        )
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.side_effect = [callers_xml, body_xml]
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert routes[0]["path"] == "/pacticipants/{name}"

    def test_deduplicates_same_method_path(self):
        callers_xml = _callers_xml(["methodA", "methodB"])
        same_body = _expand_xml('this.http.fetch(`${b}/items`, {method: "GET"});')
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.side_effect = [callers_xml, same_body, same_body]
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert len(routes) == 1

    def test_empty_when_no_callers_and_grep_empty(self):
        # Both --callers and --grep return nothing → empty list
        empty_xml = '<r confidence="high"><routes></routes></r>'
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.return_value = empty_xml
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert routes == []

    def test_grep_fallback_dynamic_dispatch(self):
        """When --callers finds nothing, grep fallback finds call sites by name."""
        empty_callers_xml = '<r confidence="high"><routes></routes></r>'
        grep_xml = (
            '<grep pattern=".fetch(" root="/src">'
            '<f p="client/environment-api.ts">'
            '<hit l="28" in="listEnvironments">this.http.fetch</hit>'
            '<hit l="55" in="recordDeployment">this.http.fetch</hit>'
            "</f>"
            "</grep>"
        )
        body_list_xml = _expand_xml(
            'return await this.http.fetch(`${b}/environments`, {method: "GET"});'
        )
        body_record_xml = _expand_xml(
            'return await this.http.fetch('
            '`${b}/pacticipants/${encodeURIComponent(name)}/deployed`, {method: "POST"});'
        )
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.side_effect = [empty_callers_xml, grep_xml, body_list_xml, body_record_xml]
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert len(routes) == 2
        assert {r["method"] for r in routes} == {"GET", "POST"}
        assert "/environments" in {r["path"] for r in routes}
        assert "/pacticipants/{name}/deployed" in {r["path"] for r in routes}

    def test_grep_fallback_handles_at_sibling_elements(self):
        """<at> sibling elements within a <hit> are also collected as callers."""
        empty_callers_xml = '<r confidence="high"><routes></routes></r>'
        grep_xml = (
            '<grep pattern=".fetch(" root="/src">'
            '<f p="client/webhook-api.ts">'
            '<hit l="35" in="getWebhook">'
            '<at l="52" in="createWebhook"/>'
            "<at l=\"69\" in=\"updateWebhook\"/>"
            "</hit>"
            "</f>"
            "</grep>"
        )
        body_get_xml = _expand_xml(
            'return await this.http.fetch(`${b}/webhooks/${encodeURIComponent(id)}`, {method: "GET"});'
        )
        body_create_xml = _expand_xml(
            'return await this.http.fetch(`${b}/webhooks`, {method: "POST"});'
        )
        body_update_xml = _expand_xml(
            'return await this.http.fetch(`${b}/webhooks/${encodeURIComponent(id)}`, {method: "PUT"});'
        )
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.side_effect = [
                empty_callers_xml,
                grep_xml,
                body_get_xml,
                body_create_xml,
                body_update_xml,
            ]
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        # GET and PUT share the same path but differ by method → both kept
        # POST has a different path → also kept
        assert len(routes) == 3
        methods = {r["method"] for r in routes}
        assert "GET" in methods
        assert "POST" in methods
        assert "PUT" in methods

    def test_skips_caller_with_no_url(self):
        callers_xml = _callers_xml(["helperMethod"])
        body_xml = _expand_xml("const x = 1 + 2; return x;")
        with mock.patch("build_filtered_oas.run_ripwire") as m:
            m.side_effect = [callers_xml, body_xml]
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert routes == []

    def test_ripwire_error_returns_empty(self):
        with mock.patch("build_filtered_oas.run_ripwire", side_effect=RuntimeError("fail")):
            routes = get_routes_via_wrapper_callers("rw", "/src", "HttpClient.fetch")
        assert routes == []


# ─── 16. find_http_wrapper_symbol ─────────────────────────────────────────────

class TestFindHttpWrapperSymbol:
    def test_finds_from_route_element(self):
        xml = '<r><route from="HttpClient.fetch" to="" method="" path=""/></r>'
        with mock.patch("build_filtered_oas.run_ripwire", return_value=xml):
            sym = find_http_wrapper_symbol("rw", "/src")
        assert sym == "HttpClient.fetch"

    def test_finds_class_method_from_s_element(self):
        xml = '<r><s t="method" n="fetch" class="ApiClient"><body></body></s></r>'
        with mock.patch("build_filtered_oas.run_ripwire", return_value=xml):
            sym = find_http_wrapper_symbol("rw", "/src")
        assert sym == "ApiClient.fetch"

    def test_returns_none_when_ripwire_fails(self):
        with mock.patch("build_filtered_oas.run_ripwire", side_effect=RuntimeError("fail")):
            assert find_http_wrapper_symbol("rw", "/src") is None

    def test_returns_none_when_nothing_matches(self):
        xml = '<r><route from="getOrder" to="" method="GET" path="/orders/{id}"/></r>'
        with mock.patch("build_filtered_oas.run_ripwire", return_value=xml):
            assert find_http_wrapper_symbol("rw", "/src") is None
