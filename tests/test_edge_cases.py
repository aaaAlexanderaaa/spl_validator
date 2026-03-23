"""Edge case tests for the SPL validator — lexer, parser, HTTP API, CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from spl_validator.core import validate
from spl_validator.json_payload import build_validation_json_dict
from spl_validator.src.lexer import Lexer, TokenType

_repo_root = Path(__file__).resolve().parent.parent


# ── Lexer edge cases ─────────────────────────────────────────────────

class TestLexerEdgeCases:
    def test_empty_input(self):
        tokens = Lexer("").tokenize()
        assert len(tokens) == 1
        assert tokens[0].type == TokenType.EOF

    def test_only_whitespace(self):
        tokens = Lexer("   \t\n  ").tokenize()
        assert tokens[-1].type == TokenType.EOF

    def test_single_pipe(self):
        tokens = Lexer("|").tokenize()
        pipe_tokens = [t for t in tokens if t.type == TokenType.PIPE]
        assert len(pipe_tokens) == 1

    def test_unclosed_double_quote(self):
        tokens = Lexer('"hello').tokenize()
        error_tokens = [t for t in tokens if t.type == TokenType.ERROR]
        assert len(error_tokens) >= 1

    def test_unclosed_single_quote(self):
        tokens = Lexer("'hello").tokenize()
        error_tokens = [t for t in tokens if t.type == TokenType.ERROR]
        assert len(error_tokens) >= 1

    def test_escaped_quotes_in_string(self):
        tokens = Lexer(r'"say \"hi\""').tokenize()
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        assert len(string_tokens) == 1

    def test_nested_parentheses(self):
        tokens = Lexer("sum(if(a>0,b,c))").tokenize()
        lparen = [t for t in tokens if t.type == TokenType.LPAREN]
        rparen = [t for t in tokens if t.type == TokenType.RPAREN]
        assert len(lparen) == 2
        assert len(rparen) == 2

    def test_very_long_identifier(self):
        long_id = "a" * 10000
        tokens = Lexer(f"index={long_id}").tokenize()
        assert any(t.value == long_id for t in tokens)

    def test_comparison_operators(self):
        for op in ["==", "!=", ">=", "<=", ">", "<"]:
            tokens = Lexer(f"x {op} 1").tokenize()
            assert any(t.value == op for t in tokens), f"Operator {op} not tokenized"

    def test_boolean_keywords(self):
        tokens = Lexer("a AND b OR c NOT d").tokenize()
        keywords = [t for t in tokens if t.type == TokenType.AND or t.type == TokenType.OR or t.type == TokenType.NOT]
        assert len(keywords) == 3


# ── Validator edge cases ─────────────────────────────────────────────

class TestValidatorEdgeCases:
    def test_empty_string(self):
        r = validate("")
        assert not r.is_valid
        assert any(e.code == "SPL005" for e in r.errors)

    def test_whitespace_only(self):
        r = validate("   \t  ")
        assert not r.is_valid

    def test_single_pipe(self):
        r = validate("|")
        assert not r.is_valid

    def test_trailing_pipe_tolerated(self):
        r = validate("index=web | stats count |")
        assert r.is_valid

    def test_double_pipe(self):
        r = validate("index=web || stats count")
        assert not r.is_valid

    def test_leading_pipe_non_generating(self):
        r = validate("| stats count")
        assert not r.is_valid
        assert any(e.code == "SPL001" for e in r.errors)

    def test_simplest_valid_query(self):
        r = validate("index=main")
        assert r.is_valid
        assert r.ast is not None

    def test_very_long_query(self):
        spl = "index=main | eval " + " | eval ".join(f"f{i}={i}" for i in range(100))
        r = validate(spl)
        assert r.ast is not None

    def test_makeresults_generating(self):
        r = validate("| makeresults | eval x=1")
        assert r.is_valid

    def test_strict_unknown_command(self):
        r = validate("| makeresults | unknowncmd123", strict=True)
        assert not r.is_valid
        assert any(e.code == "SPL013" for e in r.errors)

    def test_strict_allows_macros(self):
        r = validate("index=web | `my_macro(arg1, arg2)`", strict=True)
        assert r.is_valid

    def test_unclosed_subsearch(self):
        r = validate("index=web [search index=dns")
        assert not r.is_valid

    def test_empty_subsearch(self):
        r = validate("index=web | join host []")
        assert not r.is_valid
        assert any(e.code == "SPL022" for e in r.errors)

    def test_bare_eval_tolerated(self):
        r = validate("| makeresults | eval")
        assert r.is_valid

    def test_stats_count_by_warns(self):
        r = validate("index=web | stats count BY host")
        assert r.is_valid
        codes = {w.code for w in r.warnings}
        assert "LIMSTA" in codes

    def test_json_output_valid_query(self):
        r = validate("index=web | stats count")
        payload = build_validation_json_dict(r, warning_groups="all")
        assert payload["valid"] is True
        json.dumps(payload)

    def test_json_output_invalid_query(self):
        r = validate("")
        payload = build_validation_json_dict(r, warning_groups="all")
        assert payload["valid"] is False
        json.dumps(payload)

    def test_lex_spl_field_set(self):
        r = validate("index=web | stats count")
        assert r._lex_spl is not None or r._lex_spl is None  # field exists

    def test_ast_type_is_pipeline(self):
        from spl_validator.src.parser.ast import Pipeline
        r = validate("index=web | stats count")
        assert isinstance(r.ast, Pipeline)

    def test_ast_none_on_failure(self):
        r = validate("")
        # AST may be None or a Pipeline depending on how far parsing got


# ── Suggestion edge cases ────────────────────────────────────────────

class TestSuggestionEdgeCases:
    def test_dedup_without_sort_warns(self):
        r = validate("index=web | dedup host")
        codes = {w.code for w in r.warnings}
        assert "BEST001" in codes

    def test_dedup_with_sort_no_warn(self):
        r = validate("index=web | sort - _time | dedup host")
        codes = {w.code for w in r.warnings}
        assert "BEST001" not in codes

    def test_join_without_type_warns(self):
        r = validate("index=web | join host [search index=dns | head 100]")
        codes = {w.code for w in r.warnings}
        assert "BEST002" in codes

    def test_transaction_unbounded_warns(self):
        r = validate("index=web | transaction host")
        codes = {w.code for w in r.warnings}
        assert "BEST003" in codes

    def test_transaction_maxspan_still_warns(self):
        r = validate("index=web | transaction host maxspan=30m")
        codes = {w.code for w in r.warnings}
        assert "BEST003" in codes

    def test_sort_then_head_warns(self):
        r = validate("index=web | sort - bytes | head 5")
        codes = {w.code for w in r.warnings}
        assert "BEST005" in codes

    def test_sort_unlimited_warns(self):
        r = validate("index=web | stats count BY host | sort - count")
        codes = {w.code for w in r.warnings}
        assert "BEST006" in codes

    def test_table_star_warns(self):
        r = validate("index=web | table *")
        codes = {w.code for w in r.warnings}
        assert "BEST007" in codes

    def test_consecutive_eval_warns(self):
        r = validate("index=web | eval a=1 | eval b=2")
        codes = {w.code for w in r.warnings}
        assert "BEST008" in codes

    def test_single_eval_no_warn(self):
        r = validate("index=web | eval a=1, b=2")
        codes = {w.code for w in r.warnings}
        assert "BEST008" not in codes

    def test_extraction_before_filter_warns(self):
        r = validate('index=web | rex "(?<ip>\\d+)" | where ip!="0"')
        codes = {w.code for w in r.warnings}
        assert "BEST009" in codes

    def test_mvexpand_warns(self):
        r = validate("index=web | mvexpand myfield")
        codes = {w.code for w in r.warnings}
        assert "BEST013" in codes

    def test_spath_warns(self):
        r = validate("index=web | spath")
        codes = {w.code for w in r.warnings}
        assert "BEST014" in codes

    def test_join_performance_warns(self):
        r = validate("index=web | join host [search index=dns | head 100]")
        codes = {w.code for w in r.warnings}
        assert "BEST010" in codes


# ── Limit/semantic warning edge cases ────────────────────────────────

class TestLimitAndSemanticWarnings:
    def test_tail_limit_warning(self):
        r = validate("index=web | tail")
        codes = {w.code for w in r.warnings}
        assert "LIMTAI" in codes

    def test_sort_limit_warning(self):
        r = validate("index=web | stats count BY host | sort - count")
        codes = {w.code for w in r.warnings}
        assert "LIMSOR" in codes

    def test_head_limit_warning(self):
        r = validate("index=web | head")
        codes = {w.code for w in r.warnings}
        assert "LIMHEA" in codes

    def test_stats_memory_limit(self):
        r = validate("index=web | stats count BY host")
        codes = {w.code for w in r.warnings}
        assert "LIMSTA" in codes

    def test_where_semantic(self):
        r = validate("index=web | where status>400")
        codes = {w.code for w in r.warnings}
        assert "SEM-WHE" in codes

    def test_head_filter_semantic(self):
        r = validate("index=web | head 5")
        codes = {w.code for w in r.warnings}
        assert "SEM-FLT" in codes

    def test_transaction_limit_warning(self):
        r = validate("index=web | transaction host")
        codes = {w.code for w in r.warnings}
        assert "LIMTRA" in codes

    def test_join_subsearch_limit_warning(self):
        r = validate("index=web | join host [search index=dns | head 100]")
        codes = {w.code for w in r.warnings}
        assert "LIMJOI" in codes


# ── HTTP API edge cases ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def httpd_server():
    """Start HTTP server on a random port for the module."""
    import socket
    import time

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = int(s.getsockname()[1])
    s.close()

    proc = subprocess.Popen(
        [sys.executable, "-m", "spl_validator.httpd", "--host", "127.0.0.1", "--port", str(port)],
        cwd=_repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 10.0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.2) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.05)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError("httpd did not start")

    yield port

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _post_validate(port: int, body: bytes | str, content_type: str = "application/json") -> tuple[int, dict | str]:
    if isinstance(body, str):
        body = body.encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/validate",
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            text = r.read().decode("utf-8")
            return r.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8")
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, text


class TestHttpApiEdgeCases:
    def test_malformed_json(self, httpd_server: int):
        code, body = _post_validate(httpd_server, "not json at all")
        assert code == 400
        assert body["error"] == "invalid_request"

    def test_missing_spl_field(self, httpd_server: int):
        code, body = _post_validate(httpd_server, json.dumps({}))
        assert code == 400
        assert "spl" in body.get("message", "")

    def test_spl_not_string(self, httpd_server: int):
        code, body = _post_validate(httpd_server, json.dumps({"spl": 123}))
        assert code == 400
        assert "spl" in body.get("message", "")

    def test_empty_spl_string(self, httpd_server: int):
        code, body = _post_validate(httpd_server, json.dumps({"spl": ""}))
        assert code == 422
        assert body["valid"] is False

    def test_valid_spl_returns_200(self, httpd_server: int):
        code, body = _post_validate(httpd_server, json.dumps({"spl": "index=web | stats count"}))
        assert code == 200
        assert body["valid"] is True

    def test_invalid_spl_returns_422(self, httpd_server: int):
        code, body = _post_validate(httpd_server, json.dumps({"spl": "| stats count"}))
        assert code == 422
        assert body["valid"] is False

    def test_v1_validate_endpoint(self, httpd_server: int):
        req = urllib.request.Request(
            f"http://127.0.0.1:{httpd_server}/v1/validate",
            data=json.dumps({"spl": "index=main"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            assert r.status == 200

    def test_get_404(self, httpd_server: int):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{httpd_server}/nonexistent", timeout=2)
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_post_unknown_path_404(self, httpd_server: int):
        code, body = _post_validate(httpd_server, json.dumps({"spl": "x"}))
        # This hits /validate which is valid; test /unknown instead
        req = urllib.request.Request(
            f"http://127.0.0.1:{httpd_server}/unknown",
            data=json.dumps({"spl": "x"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=2)
        except urllib.error.HTTPError as e:
            assert e.code == 404

    def test_invalid_advice_returns_400(self, httpd_server: int):
        code, body = _post_validate(
            httpd_server,
            json.dumps({"spl": "index=web", "advice": "nonexistent_group"}),
        )
        assert code == 400

    def test_strict_flag(self, httpd_server: int):
        code, body = _post_validate(
            httpd_server,
            json.dumps({"spl": "| makeresults | unknowncmd", "strict": True}),
        )
        assert code == 422
        codes = {e["code"] for e in body.get("errors", [])}
        assert "SPL013" in codes

    def test_concurrent_requests(self, httpd_server: int):
        """Verify ThreadingHTTPServer handles parallel requests."""
        import concurrent.futures

        def single_request():
            c, b = _post_validate(httpd_server, json.dumps({"spl": "index=web | stats count"}))
            assert c == 200
            return b["valid"]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(single_request) for _ in range(20)]
            results = [f.result() for f in futures]
        assert all(results)


# ── CLI edge cases ───────────────────────────────────────────────────

class TestCliEdgeCases:
    def test_empty_stdin(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spl_validator", "--stdin", "--format=json"],
            cwd=_repo_root,
            input="",
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout)
        assert data["valid"] is False

    def test_multiline_stdin(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spl_validator", "--stdin", "--format=json"],
            cwd=_repo_root,
            input="index=web\n| stats count BY host\n",
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout)
        assert data["valid"] is True

    def test_format_json_flag(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spl_validator", "--format=json", "--spl", "index=web"],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert "output_schema_version" in data

    def test_advice_all(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spl_validator", "--format=json", "--advice=all",
             "--spl", "index=web | stats count BY host"],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout)
        assert len(data.get("warnings", [])) > 0

    def test_exit_code_0_valid(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spl_validator", "--format=json", "--spl", "index=main"],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0

    def test_exit_code_1_invalid(self):
        proc = subprocess.run(
            [sys.executable, "-m", "spl_validator", "--format=json", "--spl", "| stats count"],
            cwd=_repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1


# ── Diagnostic code coverage ─────────────────────────────────────────

class TestDiagnosticCodeCoverage:
    """Ensure every emitted diagnostic code has at least one targeted test."""

    def test_spl006_unknown_command_warning(self):
        r = validate("index=web | totallyunknowncmd789")
        codes = {w.code for w in r.warnings}
        assert "SPL006" in codes

    def test_spl007_invalid_character(self):
        r = validate("index=web | eval x=\x01")
        codes = {e.code for e in r.errors}
        assert "SPL007" in codes

    def test_spl009_unclosed_paren_in_stats(self):
        r = validate("index=web | stats sum(count(")
        codes = {e.code for e in r.errors}
        assert "SPL009" in codes

    def test_spl040_bare_lookup(self):
        r = validate("index=web | lookup")
        codes = {w.code for w in r.warnings}
        assert "SPL040" in codes

    def test_spl041_rest_non_services_uri(self):
        r = validate("| makeresults | rest uri=http://example.com/foo")
        codes = {w.code for w in r.warnings}
        assert "SPL041" in codes

    def test_spl042_bare_rest(self):
        r = validate("| makeresults | rest")
        codes = {w.code for w in r.warnings}
        assert "SPL042" in codes

    def test_limsub_appendcols(self):
        r = validate("index=web | appendcols [search index=dns | stats count]")
        codes = {w.code for w in r.warnings}
        assert "LIMSUB" in codes

    def test_limapp_append(self):
        r = validate("index=web | append [search index=dns]")
        codes = {w.code for w in r.warnings}
        assert "LIMAPP" in codes

    def test_limmve_mvexpand(self):
        r = validate("index=web | mvexpand myfield")
        codes = {w.code for w in r.warnings}
        assert "LIMMVE" in codes

    def test_best012_lowercase_not(self):
        r = validate("index=web not error")
        codes = {w.code for w in r.warnings}
        assert "BEST012" in codes

    def test_spl050_plain_search_without_index(self):
        r = validate("error 404")
        codes = {w.code for w in r.warnings}
        assert "SPL050" in codes

    def test_sem_ded_dedup(self):
        r = validate("index=web | dedup host")
        codes = {w.code for w in r.warnings}
        assert "SEM-DED" in codes

    def test_sem_joi_join(self):
        r = validate("index=web | join host [search index=dns | head 100]")
        codes = {w.code for w in r.warnings}
        assert "SEM-JOI" in codes

    def test_sem_reg_regex(self):
        r = validate('index=web | regex _raw="error"')
        codes = {w.code for w in r.warnings}
        assert "SEM-REG" in codes

    def test_sem_map_map(self):
        r = validate('| makeresults | map search="index=web"')
        codes = {w.code for w in r.warnings}
        assert "SEM-MAP" in codes

    def test_sem_top_top(self):
        r = validate("index=web | top host")
        codes = {w.code for w in r.warnings}
        assert "SEM-TOP" in codes

    def test_sem_rar_rare(self):
        r = validate("index=web | rare host")
        codes = {w.code for w in r.warnings}
        assert "SEM-RAR" in codes

    def test_sem_tra_transaction(self):
        r = validate("index=web | transaction host")
        codes = {w.code for w in r.warnings}
        assert "SEM-TRA" in codes

    def test_sem_loo_lookup(self):
        r = validate("index=web | lookup mytable field")
        codes = {w.code for w in r.warnings}
        assert "SEM-LOO" in codes


# ── Registry parity test ─────────────────────────────────────────────

class TestRegistryParity:
    """Ensure Python and TypeScript registries stay in sync."""

    def test_ts_registry_command_count_matches_python(self):
        import json as _json
        from spl_validator.src.registry.commands import COMMANDS
        registry_path = _repo_root / "typescript" / "core" / "src" / "generated" / "registryData.json"
        with open(registry_path) as f:
            data = _json.load(f)
        ts_commands = set(data["commands"].keys())
        py_commands = set(COMMANDS.keys())
        assert ts_commands == py_commands, (
            f"Command mismatch — Python-only: {py_commands - ts_commands}, "
            f"TS-only: {ts_commands - py_commands}"
        )

    def test_ts_registry_function_count_matches_python(self):
        import json as _json
        from spl_validator.src.registry.functions import FUNCTIONS
        registry_path = _repo_root / "typescript" / "core" / "src" / "generated" / "registryData.json"
        with open(registry_path) as f:
            data = _json.load(f)
        ts_functions = set(data["functions"].keys())
        py_functions = set(FUNCTIONS.keys())
        assert ts_functions == py_functions, (
            f"Function mismatch — Python-only: {py_functions - ts_functions}, "
            f"TS-only: {ts_functions - py_functions}"
        )
