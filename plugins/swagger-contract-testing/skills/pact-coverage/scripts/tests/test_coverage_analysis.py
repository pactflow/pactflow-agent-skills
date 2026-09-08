import json
import pytest
from parse_pact_coverage import (
    extract_pact_interactions,
    extract_oas_operations,
    find_matching_operation,
    oas_path_to_pattern,
    compute_coverage,
    _build_consumer_filtered_oas,
)

DEFAULT_EXCLUDE = {"500", "501", "502", "503"}


class TestOasPathToPattern:
    def test_no_params(self):
        pattern = oas_path_to_pattern("/orders")
        assert pattern.match("/orders")
        assert not pattern.match("/orders/123")

    def test_one_param(self):
        pattern = oas_path_to_pattern("/orders/{id}")
        assert pattern.match("/orders/123")
        assert pattern.match("/orders/abc-def")
        assert not pattern.match("/orders/123/items")

    def test_two_params(self):
        pattern = oas_path_to_pattern("/orgs/{org}/repos/{repo}")
        assert pattern.match("/orgs/acme/repos/widget")
        assert not pattern.match("/orgs/acme")

    def test_dot_in_path_is_not_regex_wildcard(self):
        pattern = oas_path_to_pattern("/v1.0/orders")
        assert pattern.match("/v1.0/orders")
        assert not pattern.match("/v1X0/orders")


class TestFindMatchingOperation:
    def test_exact_path_match(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        key = find_matching_operation("POST", "/orders", ops)
        assert key == "post:/orders"

    def test_template_path_match(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        key = find_matching_operation("GET", "/orders/123", ops)
        assert key == "get:/orders/{id}"

    def test_method_case_insensitive(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert find_matching_operation("get", "/orders/99", ops) == "get:/orders/{id}"

    def test_no_match_returns_none(self, sample_oas):
        ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        assert find_matching_operation("DELETE", "/orders/99", ops) is None

    def test_specificity_wins_over_wildcard(self):
        ops = {
            "get:/items/{id}": {"path": "/items/{id}", "method": "get",
                                "status_codes": {"200"}, "req_required_fields": set(),
                                "resp_required_fields": {}},
            "get:/items/new": {"path": "/items/new", "method": "get",
                               "status_codes": {"200"}, "req_required_fields": set(),
                               "resp_required_fields": {}},
        }
        assert find_matching_operation("GET", "/items/new", ops) == "get:/items/new"


class TestComputeCoverage:
    def test_covered_path_method(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        assert "get:/orders/{id}" in report["path_method"]["covered"]
        assert "post:/orders" in report["path_method"]["covered"]

    def test_no_missing_operations_in_fixture(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        # Both OAS operations are covered (GET and POST have pact interactions)
        assert report["path_method"]["missing"] == []

    def test_missing_status_codes_for_get(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        sc = report["status_codes"]["get:/orders/{id}"]
        assert "200" in sc["covered"]
        assert "401" in sc["missing"]
        assert "404" in sc["missing"]

    def test_missing_req_body_fields_for_post(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        rb = report["req_body_fields"]["post:/orders"]
        assert "customerId" in rb["covered"]
        assert "orderId" in rb["missing"]
        assert "items" in rb["missing"]

    def test_missing_resp_body_fields_for_get_200(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        key = "get:/orders/{id}:200"
        rb = report["resp_body_fields"][key]
        assert "id" in rb["covered"]
        assert "status" in rb["covered"]
        assert "total" in rb["missing"]

    def test_total_interactions_count(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        # 2 HTTP interactions (Async/Messages is excluded)
        assert report["total_interactions"] == 2

    def test_has_gaps_true_when_gaps(self, sample_pact, sample_oas):
        interactions = extract_pact_interactions(sample_pact)
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        assert report["has_gaps"] is True

    def test_has_gaps_false_when_fully_covered(self, sample_oas):
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        interactions = [
            {"method": "GET", "path": "/orders/123", "status": 200,
             "req_body_fields": set(), "resp_body_fields": {"id", "status", "total"},
             "description": "get 200"},
            {"method": "GET", "path": "/orders/999", "status": 401,
             "req_body_fields": set(), "resp_body_fields": set(),
             "description": "get 401"},
            {"method": "GET", "path": "/orders/000", "status": 404,
             "req_body_fields": set(), "resp_body_fields": set(),
             "description": "get 404"},
            {"method": "POST", "path": "/orders", "status": 201,
             "req_body_fields": {"customerId", "orderId", "items"},
             "resp_body_fields": {"id", "status", "total"},
             "description": "post 201"},
            {"method": "POST", "path": "/orders", "status": 400,
             "req_body_fields": set(), "resp_body_fields": set(),
             "description": "post 400"},
        ]
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        assert report["has_gaps"] is False

    def test_unmatched_pact_interactions_are_ignored(self, sample_oas):
        oas_ops = extract_oas_operations(sample_oas, DEFAULT_EXCLUDE)
        interactions = [
            {"method": "GET", "path": "/unknown/endpoint", "status": 200,
             "req_body_fields": set(), "resp_body_fields": set(),
             "description": "unmatched"},
        ]
        report = compute_coverage(oas_ops, interactions, DEFAULT_EXCLUDE)
        # All OAS operations remain missing since nothing matched
        assert "get:/orders/{id}" in report["path_method"]["missing"]
        assert "post:/orders" in report["path_method"]["missing"]


class TestBuildConsumerFilteredOas:
    """Tests for _build_consumer_filtered_oas — consumer-routes path (no ripwire needed)."""

    def test_filters_to_specified_routes_only(self, sample_oas):
        # Only GET /orders/{id} specified — POST /orders must be absent
        routes_json = json.dumps([{"method": "GET", "path": "/orders/{id}"}])
        filtered = _build_consumer_filtered_oas(
            sample_oas,
            consumer_root=None,
            kg=None,
            consumer_routes=routes_json,
            ripwire="ripwire",
        )
        assert filtered is not None
        assert "/orders/{id}" in filtered["paths"]
        # POST /orders must not appear
        assert "post" not in filtered["paths"].get("/orders", {})

    def test_returns_none_when_no_routes_found(self, sample_oas):
        # No source of routes given → must return None
        result = _build_consumer_filtered_oas(
            sample_oas,
            consumer_root=None,
            kg=None,
            consumer_routes=None,
            ripwire="ripwire",
        )
        assert result is None

    def test_returns_none_on_invalid_consumer_routes_json(self, sample_oas):
        result = _build_consumer_filtered_oas(
            sample_oas,
            consumer_root=None,
            kg=None,
            consumer_routes="not valid json",
            ripwire="ripwire",
        )
        assert result is None

    def test_multiple_routes_include_all_matched_operations(self, sample_oas):
        routes_json = json.dumps([
            {"method": "GET", "path": "/orders/{id}"},
            {"method": "POST", "path": "/orders"},
        ])
        filtered = _build_consumer_filtered_oas(
            sample_oas,
            consumer_root=None,
            kg=None,
            consumer_routes=routes_json,
            ripwire="ripwire",
        )
        assert filtered is not None
        assert "get" in filtered["paths"].get("/orders/{id}", {})
        assert "post" in filtered["paths"].get("/orders", {})

    def test_unrecognised_route_does_not_crash(self, sample_oas):
        # /nonexistent is not in the OAS — should be silently skipped
        routes_json = json.dumps([
            {"method": "GET", "path": "/nonexistent"},
            {"method": "GET", "path": "/orders/{id}"},
        ])
        filtered = _build_consumer_filtered_oas(
            sample_oas,
            consumer_root=None,
            kg=None,
            consumer_routes=routes_json,
            ripwire="ripwire",
        )
        assert filtered is not None
        assert "/orders/{id}" in filtered["paths"]

    def test_filtered_oas_has_correct_structure(self, sample_oas):
        routes_json = json.dumps([{"method": "GET", "path": "/orders/{id}"}])
        filtered = _build_consumer_filtered_oas(
            sample_oas,
            consumer_root=None,
            kg=None,
            consumer_routes=routes_json,
            ripwire="ripwire",
        )
        assert "openapi" in filtered
        assert "info" in filtered
        assert "paths" in filtered
        assert "components" in filtered
