import json
import pytest
from parse_pact_coverage import load_pact, extract_pact_interactions


class TestLoadPact:
    def test_loads_valid_pact(self, sample_pact):
        assert sample_pact["consumer"]["name"] == "OrderClient"
        assert sample_pact["provider"]["name"] == "OrderAPI"

    def test_raises_on_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ not json }")
        with pytest.raises((ValueError, Exception)):
            load_pact(str(bad))

    def test_raises_on_missing_file(self):
        with pytest.raises((FileNotFoundError, OSError)):
            load_pact("/nonexistent/pact.json")


class TestExtractPactInteractions:
    def test_returns_only_synchronous_http(self, sample_pact):
        interactions = extract_pact_interactions(sample_pact)
        assert len(interactions) == 2  # Asynchronous/Messages filtered out

    def test_all_returned_are_http_type(self, sample_pact):
        for ix in extract_pact_interactions(sample_pact):
            assert ix["method"] in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE")
            assert ix["path"].startswith("/")
            assert isinstance(ix["status"], int)

    def test_get_interaction_fields(self, sample_pact):
        interactions = extract_pact_interactions(sample_pact)
        get_ix = next(ix for ix in interactions if ix["method"] == "GET")
        assert get_ix["path"] == "/orders/123"
        assert get_ix["status"] == 200
        assert get_ix["req_body_fields"] == set()  # no request body on GET
        assert "id" in get_ix["resp_body_fields"]
        assert "status" in get_ix["resp_body_fields"]
        assert "total" not in get_ix["resp_body_fields"]  # intentionally missing

    def test_post_interaction_fields(self, sample_pact):
        interactions = extract_pact_interactions(sample_pact)
        post_ix = next(ix for ix in interactions if ix["method"] == "POST")
        assert post_ix["path"] == "/orders"
        assert post_ix["status"] == 201
        assert "customerId" in post_ix["req_body_fields"]
        assert "orderId" not in post_ix["req_body_fields"]  # intentionally missing
        assert "items" not in post_ix["req_body_fields"]  # intentionally missing

    def test_missing_body_content_returns_empty_set(self):
        pact = {
            "interactions": [{
                "type": "Synchronous/HTTP",
                "description": "no body",
                "request": {"method": "GET", "path": "/ping"},
                "response": {"status": 204}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert interactions[0]["resp_body_fields"] == set()
        assert interactions[0]["req_body_fields"] == set()

    def test_non_dict_body_content_returns_empty_set(self):
        pact = {
            "interactions": [{
                "type": "Synchronous/HTTP",
                "description": "array body",
                "request": {"method": "POST", "path": "/items",
                            "body": {"content": ["a", "b"], "contentType": "application/json"}},
                "response": {"status": 200,
                             "body": {"content": "string-not-dict", "contentType": "text/plain"}}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert interactions[0]["req_body_fields"] == set()
        assert interactions[0]["resp_body_fields"] == set()

    def test_empty_interactions_list(self):
        pact = {"interactions": []}
        assert extract_pact_interactions(pact) == []

    def test_interactions_key_absent(self):
        pact = {}
        assert extract_pact_interactions(pact) == []

    def test_method_is_uppercased(self):
        pact = {
            "interactions": [{
                "type": "Synchronous/HTTP",
                "description": "lowercase method",
                "request": {"method": "get", "path": "/test"},
                "response": {"status": 200}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert interactions[0]["method"] == "GET"


class TestExtractPactInteractionsV3:
    """Pact spec v3/v2 — all interactions are HTTP; body is inline JSON."""

    def test_returns_all_interactions(self, sample_pact_v3):
        # v3 has no type field — all interactions should be returned
        interactions = extract_pact_interactions(sample_pact_v3)
        assert len(interactions) == 2

    def test_get_interaction_inline_body(self, sample_pact_v3):
        interactions = extract_pact_interactions(sample_pact_v3)
        get_ix = next(ix for ix in interactions if ix["method"] == "GET")
        assert get_ix["path"] == "/orders/123"
        assert get_ix["status"] == 200
        assert get_ix["req_body_fields"] == set()
        assert "id" in get_ix["resp_body_fields"]
        assert "status" in get_ix["resp_body_fields"]

    def test_post_interaction_inline_body(self, sample_pact_v3):
        interactions = extract_pact_interactions(sample_pact_v3)
        post_ix = next(ix for ix in interactions if ix["method"] == "POST")
        assert post_ix["path"] == "/orders"
        assert post_ix["status"] == 201
        assert "customerId" in post_ix["req_body_fields"]
        assert "id" in post_ix["resp_body_fields"]

    def test_missing_body_returns_empty_set(self):
        pact = {
            "metadata": {"pactSpecification": {"version": "3.0.0"}},
            "interactions": [{
                "description": "no body",
                "request": {"method": "GET", "path": "/ping"},
                "response": {"status": 204}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert interactions[0]["req_body_fields"] == set()
        assert interactions[0]["resp_body_fields"] == set()

    def test_non_dict_body_returns_empty_set(self):
        pact = {
            "metadata": {"pactSpecification": {"version": "3.0.0"}},
            "interactions": [{
                "description": "array body",
                "request": {"method": "POST", "path": "/items", "body": ["a", "b"]},
                "response": {"status": 200, "body": "string-body"}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert interactions[0]["req_body_fields"] == set()
        assert interactions[0]["resp_body_fields"] == set()

    def test_v2_format_treated_same_as_v3(self):
        pact = {
            "metadata": {"pactSpecification": {"version": "2.0.0"}},
            "interactions": [{
                "description": "v2 interaction",
                "request": {"method": "GET", "path": "/things"},
                "response": {"status": 200, "body": {"name": "foo", "age": 1}}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert len(interactions) == 1
        assert interactions[0]["resp_body_fields"] == {"name", "age"}

    def test_no_metadata_defaults_to_v3_behavior(self):
        # Pacts without metadata should not filter by type (safe fallback)
        pact = {
            "interactions": [{
                "description": "typeless interaction",
                "request": {"method": "DELETE", "path": "/items/1"},
                "response": {"status": 204}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert len(interactions) == 1
        assert interactions[0]["method"] == "DELETE"

    def test_method_is_uppercased(self):
        pact = {
            "metadata": {"pactSpecification": {"version": "3.0.0"}},
            "interactions": [{
                "description": "lowercase",
                "request": {"method": "post", "path": "/orders"},
                "response": {"status": 201}
            }]
        }
        interactions = extract_pact_interactions(pact)
        assert interactions[0]["method"] == "POST"
