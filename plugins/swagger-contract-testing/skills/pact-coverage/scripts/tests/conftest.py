import json
import pathlib
import sys

import pytest
import yaml

# Make parse_pact_coverage importable
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_pact() -> dict:
    return json.loads((FIXTURES_DIR / "sample.pact.json").read_text())


@pytest.fixture
def sample_oas() -> dict:
    return yaml.safe_load((FIXTURES_DIR / "openapi.yaml").read_text())


@pytest.fixture
def pact_path(tmp_path) -> pathlib.Path:
    src = FIXTURES_DIR / "sample.pact.json"
    dest = tmp_path / "consumer-provider.json"
    dest.write_text(src.read_text())
    return dest


@pytest.fixture
def oas_path(tmp_path) -> pathlib.Path:
    src = FIXTURES_DIR / "openapi.yaml"
    dest = tmp_path / "openapi.yaml"
    dest.write_text(src.read_text())
    return dest
