from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DRIFT_SCRIPTS = REPO_ROOT / "plugins" / "swagger-contract-testing" / "skills" / "drift-testing" / "scripts"


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, DRIFT_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_coverage = load_script("check_coverage")
extract_endpoints = load_script("extract_endpoints")


def test_coverage_pipeline_handles_operation_ids_and_synthetic_targets(tmp_path: Path) -> None:
    spec_path = tmp_path / "openapi.yaml"
    test_path = tmp_path / "drift.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "openapi": "3.0.0",
                "paths": {
                    "/products": {
                        "get": {
                            "operationId": "listProducts",
                            "responses": {"200": {}, "404": {}, "500": {}},
                        }
                    },
                    "/health": {"get": {"responses": {"200": {}}}},
                },
            }
        )
    )
    test_path.write_text(
        yaml.safe_dump(
            {
                "operations": {
                    "products": {
                        "target": "source:listProducts",
                        "expected": {"response": {"statusCode": 200}},
                    },
                    "health": {
                        "target": "source:get:/health",
                        "expected": {"response": {"statusCode": 200}},
                    },
                }
            }
        )
    )

    operations = check_coverage.get_spec_operations(str(spec_path), check_coverage.DEFAULT_EXCLUDE)
    coverage = check_coverage.get_test_coverage([str(test_path)])
    report = check_coverage.compare(operations, coverage)

    assert report["covered_operations"] == 2
    assert report["total_codes"] == 3
    assert report["covered_codes"] == 2
    assert report["partial_operations"][0]["missing_codes"] == ["404"]


def test_extract_endpoints_resolves_refs_and_generates_examples() -> None:
    root = {
        "components": {
            "parameters": {
                "ProductId": {
                    "name": "id",
                    "schema": {"type": "string", "format": "uuid"},
                }
            }
        }
    }
    parameter = {"$ref": "#/components/parameters/ProductId"}

    resolved = extract_endpoints.resolve(parameter, root)
    value, confident = extract_endpoints.get_param_example(parameter, root)

    assert resolved["name"] == "id"
    assert value == extract_endpoints.EXAMPLE_UUID
    assert confident is True
    assert extract_endpoints.get_404_path_value(parameter, root) == extract_endpoints.NIL_UUID
