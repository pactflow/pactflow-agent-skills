import json
import pathlib
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).parent.parent
FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "parse_pact_coverage.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


ASYNC = ["--spec", str(FIXTURES / "asyncapi.yaml")]
V3 = str(FIXTURES / "async.pact.v3.json")
V4 = str(FIXTURES / "async.pact.v4.json")


def test_async_spec_dispatches_and_reports_gaps():
    result = _cli(*ASYNC, "--pacts", V3, V4)
    assert result.returncode == 1
    assert "AsyncAPI" in result.stdout
    assert "missing: carrier" in result.stdout


def test_async_json_output():
    result = _cli(*ASYNC, "--pacts", V3, V4, "--json")
    assert result.returncode == 1
    assert json.loads(result.stdout)["has_gaps"] is True


def test_consumer_channels_filters_to_full_coverage():
    result = _cli(*ASYNC, "--pacts", V3, "--consumer-channels", '["orders.created"]')
    assert result.returncode == 0, result.stdout + result.stderr


def test_include_actions_widens_scope():
    result = _cli(*ASYNC, "--pacts", V3, V4, "--include-actions", "send,receive", "--json")
    data = json.loads(result.stdout)
    assert "consumePlaceOrder" in data["operations"]


def test_invalid_consumer_channels_exit_2():
    result = _cli(*ASYNC, "--pacts", V3, "--consumer-channels", "not-json")
    assert result.returncode == 2
    assert "consumer-channels" in result.stderr


def test_unreadable_pact_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    result = _cli(*ASYNC, "--pacts", str(bad))
    assert result.returncode == 2


def test_openapi_spec_still_uses_http_path():
    result = _cli("--spec", str(FIXTURES / "openapi.yaml"), "--pacts", str(FIXTURES / "sample.pact.json"))
    assert result.returncode in (0, 1)
    assert "AsyncAPI" not in result.stdout


def _main(monkeypatch, capsys, *args):
    import parse_pact_coverage

    monkeypatch.setattr(sys, "argv", ["parse_pact_coverage.py", *args])
    with pytest.raises(SystemExit) as exc:
        parse_pact_coverage.main()
    return exc.value.code, capsys.readouterr()


class TestMainInProcess:
    def test_dispatches_to_async(self, monkeypatch, capsys):
        code, out = _main(monkeypatch, capsys, *ASYNC, "--pacts", V3, V4)
        assert code == 1
        assert "missing: carrier" in out.out

    def test_consumer_channels_full_coverage(self, monkeypatch, capsys):
        code, _ = _main(monkeypatch, capsys, *ASYNC, "--pacts", V3, "--consumer-channels", '["orders.created"]')
        assert code == 0

    @pytest.mark.parametrize("value", ["not-json", "[]", '{"a": 1}'])
    def test_invalid_consumer_channels(self, monkeypatch, capsys, value):
        code, out = _main(monkeypatch, capsys, *ASYNC, "--pacts", V3, "--consumer-channels", value)
        assert code == 2
        assert "consumer-channels" in out.err

    def test_unreadable_pact(self, monkeypatch, capsys, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{nope")
        code, out = _main(monkeypatch, capsys, *ASYNC, "--pacts", str(bad))
        assert code == 2
        assert "Could not parse pact" in out.err
