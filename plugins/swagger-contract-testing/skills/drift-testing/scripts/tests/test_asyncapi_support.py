from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name: str) -> ModuleType:
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recursive_refs_terminate_and_preserve_back_edge() -> None:
    extract_channels = load_script("extract_channels")
    root = {
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                        "child": {"$ref": "#/components/schemas/Node"},
                    },
                }
            }
        }
    }

    resolved = extract_channels.resolve({"$ref": "#/components/schemas/Node"}, root)

    assert resolved["properties"]["child"] == {"$ref": "#/components/schemas/Node"}


def test_external_refs_fail_explicitly() -> None:
    extract_channels = load_script("extract_channels")

    with pytest.raises(ValueError, match=r"External \$ref is not supported"):
        extract_channels.resolve({"$ref": "./messages.yaml#/Node"}, {})


def test_invalid_operation_action_is_rejected(tmp_path: Path) -> None:
    extract_channels = load_script("extract_channels")
    spec_file = tmp_path / "invalid.yaml"
    spec_file.write_text(
        yaml.safe_dump(
            {
                "asyncapi": "3.0.0",
                "operations": {"invalidOperation": {"action": "publish"}},
            }
        )
    )

    with pytest.raises(ValueError, match="invalid action"):
        extract_channels.load_operations(str(spec_file))


def test_asyncapi_coverage_tracks_each_message(tmp_path: Path) -> None:
    check_coverage = load_script("check_coverage")
    test_file = tmp_path / "tests.yaml"
    test_file.write_text(
        yaml.safe_dump(
            {
                "operations": {
                    "Adjustment": {
                        "target": "async-svc:receiveInventoryCommand:adjustmentMsg",
                    }
                }
            }
        )
    )

    covered = check_coverage.get_asyncapi_covered_targets([str(test_file)])

    assert covered == {("receiveInventoryCommand", "adjustmentMsg")}


def test_unqualified_asyncapi_target_covers_whole_operation(tmp_path: Path) -> None:
    check_coverage = load_script("check_coverage")
    test_file = tmp_path / "tests.yaml"
    test_file.write_text(yaml.safe_dump({"operations": {"Legacy": {"target": "async-svc:receiveInventoryCommand"}}}))

    covered = check_coverage.get_asyncapi_covered_targets([str(test_file)])

    assert covered == {("receiveInventoryCommand", None)}


def test_scaffold_fragments_are_appendable_and_message_aware() -> None:
    extract_channels = load_script("extract_channels")
    operations = [
        {
            "operationId": "receiveInventoryCommand",
            "action": "receive",
            "channel_address": "inventory",
            "has_reply": False,
            "messages": [
                {"local_id": "adjustmentMsg", "payload_required": [], "name": "Adjustment"},
                {"local_id": "reservationMsg", "payload_required": [], "name": "Reservation"},
            ],
        }
    ]

    output = extract_channels.scaffold_all(
        operations,
        "async-svc",
        {("receiveInventoryCommand", "adjustmentMsg")},
        include_root=False,
    )

    assert not output.startswith("operations:")
    assert "adjustmentMsg" not in output
    assert "reservationMsg" in output
