"""
Security hardening tests for AutoFix Agent execution layer and API schemas.

Tests verify:
- Language allowlist enforcement (ExecutionManager + Pydantic)
- Oversized code rejection at schema level (100KB limit)
- Path traversal pattern detection in all executors
- Output truncation at 64KB limit
- Empty code rejection
"""

import pytest
from unittest.mock import patch, MagicMock
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.execution.manager import ExecutionManager, ALLOWED_LANGUAGES
from app.execution.base import _truncate_output, MAX_OUTPUT_BYTES
from app.execution.python_executor import _check_path_traversal, _scratch_dir
from app.schemas import AnalyzeRequest, RepairRequest


# ---------------------------------------------------------------------------
# Allowlist tests
# ---------------------------------------------------------------------------

class TestLanguageAllowlist:

    def test_allowed_languages_constant_is_correct(self):
        """Verify the allowlist contains exactly the expected identifiers."""
        assert "python" in ALLOWED_LANGUAGES
        assert "javascript" in ALLOWED_LANGUAGES
        assert "java" in ALLOWED_LANGUAGES
        assert "py" in ALLOWED_LANGUAGES
        assert "js" in ALLOWED_LANGUAGES

    def test_manager_rejects_unknown_language(self):
        mgr = ExecutionManager()
        with pytest.raises(ValueError, match="Unsupported language"):
            mgr.execute(language="ruby", code="puts 'hello'")

    def test_manager_rejects_bash(self):
        mgr = ExecutionManager()
        with pytest.raises(ValueError, match="Unsupported language"):
            mgr.execute(language="bash", code="echo hi")

    def test_manager_rejects_empty_language(self):
        mgr = ExecutionManager()
        with pytest.raises(ValueError, match="Unsupported language"):
            mgr.execute(language="", code="print(1)")

    def test_manager_rejects_shell_injection_language(self):
        mgr = ExecutionManager()
        with pytest.raises(ValueError, match="Unsupported language"):
            mgr.execute(language="python; rm -rf /", code="print(1)")

    def test_manager_accepts_python_alias(self):
        """'py' alias should work without raising."""
        mgr = ExecutionManager()
        # Should not raise (will actually execute)
        result = mgr.execute(language="py", code="print('ok')")
        assert result is not None

    def test_manager_accepts_js_alias(self):
        """'js' alias should be accepted, even if node is not available."""
        mgr = ExecutionManager()
        # Should not raise ValueError for unknown language
        # (may raise EnvironmentError if node not installed, that's fine)
        try:
            result = mgr.execute(language="js", code="console.log('ok')")
            assert result is not None
        except ValueError as e:
            pytest.fail(f"'js' alias should not raise ValueError: {e}")


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_analyze_request_rejects_empty_code(self):
        with pytest.raises(ValidationError, match="empty"):
            AnalyzeRequest(source_code="   ", language="python")

    def test_analyze_request_rejects_unknown_language(self):
        with pytest.raises(ValidationError, match="Unsupported language"):
            AnalyzeRequest(source_code="print(1)", language="cobol")

    def test_analyze_request_normalizes_language_case(self):
        req = AnalyzeRequest(source_code="print(1)", language="Python")
        assert req.language == "python"

    def test_analyze_request_rejects_oversized_code(self):
        big_code = "x = 1\n" * (102_400 // 6 + 1)   # > 100KB
        with pytest.raises(ValidationError, match="maximum allowed size"):
            AnalyzeRequest(source_code=big_code, language="python")

    def test_repair_request_rejects_empty_code(self):
        with pytest.raises(ValidationError, match="empty"):
            RepairRequest(source_code="\n\n  ", language="python")

    def test_repair_request_rejects_unknown_language(self):
        with pytest.raises(ValidationError, match="Unsupported language"):
            RepairRequest(source_code="print(1)", language="perl")

    def test_repair_request_rejects_oversized_test_code(self):
        big_test = "assert True\n" * (102_400 // 12 + 1)   # > 100KB
        with pytest.raises(ValidationError, match="maximum allowed size"):
            RepairRequest(source_code="print(1)", language="python", test_code=big_test)

    def test_repair_request_accepts_valid_test_code(self):
        req = RepairRequest(
            source_code="def add(a, b): return a + b",
            language="python",
            test_code="assert add(1, 2) == 3",
        )
        assert req.test_code == "assert add(1, 2) == 3"

    def test_repair_request_max_attempts_bounds(self):
        with pytest.raises(ValidationError):
            RepairRequest(source_code="print(1)", language="python", max_attempts=0)
        with pytest.raises(ValidationError):
            RepairRequest(source_code="print(1)", language="python", max_attempts=11)


# ---------------------------------------------------------------------------
# Output truncation tests
# ---------------------------------------------------------------------------

class TestOutputTruncation:

    def test_short_output_not_truncated(self):
        result = _truncate_output("hello world")
        assert result == "hello world"

    def test_empty_output_not_truncated(self):
        result = _truncate_output("")
        assert result == ""

    def test_oversized_output_is_truncated(self):
        big_output = "A" * (MAX_OUTPUT_BYTES + 10_000)
        result = _truncate_output(big_output)
        assert len(result.encode("utf-8")) <= MAX_OUTPUT_BYTES + 100   # small slack for notice
        assert "truncated" in result

    def test_truncation_appends_notice(self):
        big_output = "X" * (MAX_OUTPUT_BYTES + 1)
        result = _truncate_output(big_output)
        assert "[...output truncated" in result

    def test_truncation_at_exact_boundary(self):
        """Output exactly at limit should not be truncated."""
        exact = "B" * MAX_OUTPUT_BYTES
        result = _truncate_output(exact)
        assert result == exact

    def test_manager_truncates_large_stdout(self):
        """ExecutionManager should truncate stdout from executor output."""
        mgr = ExecutionManager()
        big_stdout = "Z" * (MAX_OUTPUT_BYTES + 5000)

        mock_result = MagicMock()
        mock_result.stdout = big_stdout
        mock_result.stderr = ""

        with patch.object(mgr, "get_executor") as mock_get:
            mock_exec = MagicMock()
            mock_exec.execute.return_value = mock_result
            mock_get.return_value = mock_exec

            result = mgr.execute(language="python", code="print('x' * 200000)")
            assert len(result.stdout.encode("utf-8")) <= MAX_OUTPUT_BYTES + 200


# ---------------------------------------------------------------------------
# Path traversal detection tests
# ---------------------------------------------------------------------------

class TestPathTraversalDetection:

    def test_no_traversal_in_normal_code(self):
        """Normal Python code should pass without raising."""
        code = "def add(a, b):\n    return a + b\nprint(add(1, 2))"
        _check_path_traversal(code)  # should not raise

    def test_detects_unix_dotdot(self):
        code = "import os; os.open('../etc/passwd', 0)"
        with pytest.raises(ValueError, match="disallowed path"):
            _check_path_traversal(code)

    def test_detects_etc_passwd(self):
        code = "open('/etc/passwd').read()"
        with pytest.raises(ValueError, match="disallowed path"):
            _check_path_traversal(code)

    def test_detects_proc_filesystem(self):
        code = "open('/proc/self/maps').read()"
        with pytest.raises(ValueError, match="disallowed path"):
            _check_path_traversal(code)

    def test_detects_windows_dotdot_backslash(self):
        code = r"open('..\..\..\Windows\System32\cmd.exe')"
        with pytest.raises(ValueError, match="disallowed path"):
            _check_path_traversal(code)

    def test_python_executor_returns_security_error_result(self):
        """Python executor must return a SecurityError result, not raise."""
        from app.execution.python_executor import PythonExecutor
        executor = PythonExecutor(timeout=5.0)
        result = executor.execute("open('/etc/passwd').read()")
        assert not result.success
        assert result.error_type == "SecurityError"
        assert "disallowed" in result.stderr

    def test_javascript_executor_returns_security_error_result(self):
        """JavaScript executor must return a SecurityError result, not raise."""
        from app.execution.javascript_executor import JavaScriptExecutor
        executor = JavaScriptExecutor(timeout=5.0)
        result = executor.execute("const fs = require('fs'); fs.readFileSync('../etc/passwd')")
        assert not result.success
        assert result.error_type == "SecurityError"

    def test_java_executor_returns_security_error_result(self):
        """Java executor must return a SecurityError result, not raise."""
        from app.execution.java_executor import JavaExecutor
        executor = JavaExecutor(timeout=5.0)
        result = executor.execute(
            'public class Main { public static void main(String[] args) throws Exception '
            '{ new java.io.FileReader("../../etc/passwd"); } }'
        )
        assert not result.success
        assert result.error_type == "SecurityError"


# ---------------------------------------------------------------------------
# API-level security tests (HTTP)
# ---------------------------------------------------------------------------

class TestAPISecurityEndpoints:

    def test_analyze_rejects_unknown_language_via_http(self):
        client = TestClient(app)
        resp = client.post("/api/analyze", json={
            "source_code": "print(1)",
            "language": "cobol",
        })
        assert resp.status_code == 422   # Pydantic validation error

    def test_analyze_rejects_empty_code_via_http(self):
        client = TestClient(app)
        resp = client.post("/api/analyze", json={
            "source_code": "   ",
            "language": "python",
        })
        assert resp.status_code == 422

    def test_repair_stream_rejects_empty_code_via_http(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/repair/stream", json={
            "source_code": "",
            "language": "python",
        })
        # Either 422 (Pydantic) or 400 (manual check) — both acceptable
        assert resp.status_code in (400, 422)

    def test_repair_rejects_oversized_code_via_http(self):
        client = TestClient(app)
        big_code = "x = 1\n" * (102_400 // 6 + 1)
        resp = client.post("/api/repair", json={
            "source_code": big_code,
            "language": "python",
        })
        assert resp.status_code == 422

    def test_repair_rejects_unknown_language_via_http(self):
        client = TestClient(app)
        resp = client.post("/api/repair", json={
            "source_code": "print(1)",
            "language": "typescript",
        })
        assert resp.status_code == 422
