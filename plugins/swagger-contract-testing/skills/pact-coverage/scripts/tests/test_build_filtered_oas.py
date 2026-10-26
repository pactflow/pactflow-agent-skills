"""Tests for build_filtered_oas.py — covers run_ripwire, parse_routes_xml, and main()."""

import io
import json
import pathlib
import subprocess
import sys
import unittest.mock as mock

import pytest

# build_filtered_oas is on sys.path via conftest.py (scripts/ parent inserted)
from build_filtered_oas import (
    parse_routes_xml,
    run_ripwire,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


# ─── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def kg_xml() -> str:
    return (FIXTURES_DIR / "consumer_kg.xml").read_text()


# ─── 1. run_ripwire ───────────────────────────────────────────────────────────


class TestRunRipwire:
    def test_successful_call_returns_stdout(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(returncode=0, stdout="some output", stderr="")
            result = run_ripwire("ripwire", "/src", ["--for=routes"])
        assert result == "some output"

    def test_binary_not_found_raises_runtime_error(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            with pytest.raises(RuntimeError, match="not found"):
                run_ripwire("nonexistent", "/src", [])

    def test_timeout_raises_runtime_error(self):
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ripwire", timeout=30),
        ):
            with pytest.raises(RuntimeError, match="timed out"):
                run_ripwire("ripwire", "/src", [], timeout=30)

    def test_nonzero_exit_raises_runtime_error(self):
        with mock.patch("subprocess.run") as m:
            m.return_value = mock.Mock(returncode=1, stdout="", stderr="error message")
            with pytest.raises(RuntimeError, match="exited 1"):
                run_ripwire("ripwire", "/src", [])


# ─── 2. parse_routes_xml ──────────────────────────────────────────────────────


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

    def test_empty_routes_element(self):
        xml = '<r confidence="high"><routes></routes></r>'
        routes, confidence, over_ceiling = parse_routes_xml(xml)
        assert routes == []
        assert confidence == "high"
        assert over_ceiling is False

    def test_route_without_optional_attrs_uses_defaults(self):
        xml = '<r confidence="medium"><route method="DELETE" path="/items"/></r>'
        routes, confidence, _ = parse_routes_xml(xml)
        assert len(routes) == 1
        assert routes[0]["method"] == "DELETE"
        assert routes[0]["path"] == "/items"
        assert routes[0]["from"] == ""
        assert routes[0]["to"] == ""


# ─── 3. main() integration ────────────────────────────────────────────────────

_VALID_RIPWIRE_XML = (
    '<r confidence="high">'
    "<routes>"
    '<route method="GET" path="/orders/{id}" from="getOrder" to="get_order"/>'
    '<route method="POST" path="/orders" from="createOrder" to="create_order"/>'
    "</routes>"
    "</r>"
)


def _run_main(argv, *, ripwire_return=None, ripwire_side_effect=None):
    """Run main() with patched argv and run_ripwire. Returns (exit_code, captured_stdout)."""
    from build_filtered_oas import main

    rw_patch = (
        mock.patch("build_filtered_oas.run_ripwire", side_effect=ripwire_side_effect)
        if ripwire_side_effect is not None
        else mock.patch("build_filtered_oas.run_ripwire", return_value=ripwire_return)
    )

    captured = io.StringIO()
    with mock.patch.object(sys, "argv", argv), rw_patch, mock.patch("sys.stdout", captured):
        with pytest.raises(SystemExit) as exc_info:
            main()

    return exc_info.value.code, captured.getvalue()


class TestMain:
    def test_routes_found_exits_0(self):
        exit_code, _ = _run_main(
            ["build_filtered_oas.py", "--consumer-root", "/src"],
            ripwire_return=_VALID_RIPWIRE_XML,
        )
        assert exit_code == 0

    def test_routes_found_stdout_is_valid_json_array(self):
        _, output = _run_main(
            ["build_filtered_oas.py", "--consumer-root", "/src"],
            ripwire_return=_VALID_RIPWIRE_XML,
        )
        routes = json.loads(output.strip())
        assert isinstance(routes, list)
        assert len(routes) == 2

    def test_routes_contain_method_and_path(self):
        _, output = _run_main(
            ["build_filtered_oas.py", "--consumer-root", "/src"],
            ripwire_return=_VALID_RIPWIRE_XML,
        )
        routes = json.loads(output.strip())
        for r in routes:
            assert "method" in r
            assert "path" in r

    def test_no_routes_exits_1(self):
        empty_xml = '<r confidence="high"><routes></routes></r>'
        exit_code, _ = _run_main(
            ["build_filtered_oas.py", "--consumer-root", "/src"],
            ripwire_return=empty_xml,
        )
        assert exit_code == 1

    def test_ripwire_error_exits_2(self):
        exit_code, _ = _run_main(
            ["build_filtered_oas.py", "--consumer-root", "/src"],
            ripwire_side_effect=RuntimeError("binary not found"),
        )
        assert exit_code == 2


class TestGenericTools:
    def test_extract_verb_and_path(self):
        from build_filtered_oas import extract_routes_from_text

        routes = extract_routes_from_text('fetch("GET", "/orders/123?x=1")\nclient.post("/orders")')
        assert {(r["method"], r["path"]) for r in routes} == {("GET", "/orders/123"), ("POST", "/orders")}

    def test_template_vars_normalised_and_deduped(self):
        from build_filtered_oas import extract_routes_from_text

        text = 'api.get(`/orders/${id}`)\napi.get(f"/orders/{oid}")'
        routes = extract_routes_from_text(text)
        assert [(r["method"], r["path"]) for r in routes] == [("GET", "/orders/{id}")]

    def test_grep_tool_scans_sources(self, tmp_path):
        (tmp_path / "client.py").write_text('requests.get("/products")\n')
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "x.js").write_text('a.get("/ignored")')
        with (
            mock.patch.object(sys, "argv", ["b.py", "--consumer-root", str(tmp_path), "--tool", "grep"]),
            mock.patch("sys.stdout", io.StringIO()) as out,
        ):
            from build_filtered_oas import main

            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 0
        assert json.loads(out.getvalue()) == [{"method": "GET", "path": "/products"}]

    def test_graphify_tool_uses_query_output(self):
        with (
            mock.patch.object(sys, "argv", ["b.py", "--consumer-root", "/src", "--tool", "graphify"]),
            mock.patch("build_filtered_oas.run_command", return_value='GET "/users"') as rc,
            mock.patch("sys.stdout", io.StringIO()) as out,
        ):
            from build_filtered_oas import main

            with pytest.raises(SystemExit):
                main()
        assert rc.call_args.args[0][:2] == ["graphify", "query"]
        assert json.loads(out.getvalue()) == [{"method": "GET", "path": "/users"}]

    def test_repowise_uses_ask(self):
        with (
            mock.patch.object(sys, "argv", ["b.py", "--consumer-root", "/src", "--tool", "repowise"]),
            mock.patch("build_filtered_oas.run_command", return_value='PUT "/a/b"') as rc,
            mock.patch("sys.stdout", io.StringIO()) as out,
        ):
            from build_filtered_oas import main

            with pytest.raises(SystemExit) as exc:
                main()
        assert rc.call_args.args[0][:2] == ["repowise", "ask"]
        assert exc.value.code == 0
        assert json.loads(out.getvalue()) == [{"method": "PUT", "path": "/a/b"}]

    def test_codebase_memory_indexes_then_searches(self):
        outputs = ["indexed", '  return requests.get("/orders/1")']
        with (
            mock.patch.object(sys, "argv", ["b.py", "--consumer-root", "/src", "--tool", "codebase-memory"]),
            mock.patch("build_filtered_oas.run_command", side_effect=outputs) as rc,
            mock.patch("sys.stdout", io.StringIO()) as out,
        ):
            from build_filtered_oas import main

            with pytest.raises(SystemExit) as exc:
                main()
        assert "index_repository" in rc.call_args_list[0].args[0]
        assert "search_code" in rc.call_args_list[1].args[0]
        assert exc.value.code == 0
        assert json.loads(out.getvalue()) == [{"method": "GET", "path": "/orders/1"}]

    def test_unknown_builtin_without_tool_cmd_exits_2(self):
        with (
            mock.patch.object(sys, "argv", ["b.py", "--consumer-root", "/src", "--tool", "auto"]),
            mock.patch("build_filtered_oas.resolve_tool", return_value="nope"),
        ):
            from build_filtered_oas import main

            with pytest.raises(SystemExit) as exc:
                main()
        assert exc.value.code == 2

    def test_tool_cmd_substitutes_root(self):
        with (
            mock.patch.object(
                sys, "argv", ["b.py", "--consumer-root", "/src", "--tool", "repowise", "--tool-cmd", "rw search {root}"]
            ),
            mock.patch("build_filtered_oas.run_command", return_value="DELETE '/a'") as rc,
            mock.patch("sys.stdout", io.StringIO()),
        ):
            from build_filtered_oas import main

            with pytest.raises(SystemExit) as exc:
                main()
        assert rc.call_args.args[0] == ["rw", "search", "/src"]
        assert exc.value.code == 0
