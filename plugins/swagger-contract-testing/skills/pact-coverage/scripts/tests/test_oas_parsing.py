import jsonref
import pytest
from parse_pact_coverage import _extract_required_fields, extract_oas_operations, load_oas

DEFAULT_EXCLUDE = {"500", "501", "502", "503"}


class TestLoadOas:
    def test_loads_yaml(self, oas_path):
        oas = load_oas(str(oas_path))
        assert oas["openapi"].startswith("3.")

    def test_raises_on_missing_file(self):
        with pytest.raises((FileNotFoundError, OSError, ValueError)):
            load_oas("/nonexistent/spec.yaml")


class TestExtractOasOperations:
    def test_finds_all_operations(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert "get:/orders/{id}" in ops
        assert "post:/orders" in ops

    def test_status_codes_extracted_for_get(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert ops["get:/orders/{id}"]["status_codes"] == {"200", "401", "404"}

    def test_status_codes_extracted_for_post(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert ops["post:/orders"]["status_codes"] == {"201", "400"}

    def test_excludes_default_codes(self, sample_oas):
        import copy

        oas_with_500 = copy.deepcopy(sample_oas)
        oas_with_500["paths"]["/orders/{id}"]["get"]["responses"]["500"] = {"description": "Internal error"}
        ops = extract_oas_operations(oas_with_500, DEFAULT_EXCLUDE)
        assert "500" not in ops["get:/orders/{id}"]["status_codes"]

    def test_req_required_fields_resolved_from_ref(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert ops["post:/orders"]["req_required_fields"] == {"customerId", "orderId", "items"}

    def test_resp_required_fields_resolved_from_ref(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert ops["get:/orders/{id}"]["resp_required_fields"]["200"] == {"id", "status", "total"}

    def test_no_request_body_gives_empty_req_fields(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert ops["get:/orders/{id}"]["req_required_fields"] == set()

    def test_operation_key_uses_lowercase_method(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert "get:/orders/{id}" in ops
        assert "GET:/orders/{id}" not in ops

    def test_resp_required_fields_for_post_201(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert ops["post:/orders"]["resp_required_fields"]["201"] == {"id", "status", "total"}


class TestExtractRequiredFields:
    def test_direct_required_list(self):
        schema = {"type": "object", "required": ["foo", "bar"], "properties": {}}
        assert _extract_required_fields(schema) == {"foo", "bar"}

    def test_empty_required_returns_empty_set(self):
        schema = {"type": "object", "required": [], "properties": {}}
        assert _extract_required_fields(schema) == set()

    def test_ref_resolution(self):
        doc = {
            "components": {"schemas": {"Foo": {"type": "object", "required": ["x", "y"]}}},
            "schema": {"$ref": "#/components/schemas/Foo"},
        }
        resolved = jsonref.replace_refs(doc)
        assert _extract_required_fields(resolved["schema"]) == {"x", "y"}

    def test_allof_merges_required(self):
        schema = {
            "allOf": [
                {"required": ["a", "b"]},
                {"required": ["c"]},
            ]
        }
        assert _extract_required_fields(schema) == {"a", "b", "c"}

    def test_anyof_takes_union(self):
        schema = {
            "anyOf": [
                {"required": ["a"]},
                {"required": ["b"]},
            ]
        }
        assert _extract_required_fields(schema) == {"a", "b"}

    def test_oneof_takes_union(self):
        schema = {
            "oneOf": [
                {"required": ["x"]},
                {"required": ["y"]},
            ]
        }
        assert _extract_required_fields(schema) == {"x", "y"}

    def test_no_required_returns_empty_set(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        assert _extract_required_fields(schema) == set()
