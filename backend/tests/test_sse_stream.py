"""
Tests for the SSE streaming endpoint: POST /api/repair/stream

Tests verify:
- Stream opens and emits session_started as first event
- Events are valid JSON with the expected SSE schema
- Stream closes with repair_success or repair_failed terminal events
- Stream handles empty source_code with HTTP 400 (before streaming)
- Event ordering follows the agent workflow sequence
- Emitter correctly maps node deltas to event types
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.streaming.events import SSEEvent, SSEEventType
from app.streaming.emitter import node_to_sse_events
from app.execution.base import ExecutionResult
from app.analysis.models import ErrorObservation
from app.llm.models import RepairDiagnosis
from app.validation.base import ValidationResult, TestFailureDetail
from app.agent.state import CodePatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_sse_lines(raw: str) -> list[dict]:
    """Parse raw SSE body text into list of event dicts."""
    events = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            payload = line[len("data:"):].strip()
            events.append(json.loads(payload))
    return events


# ---------------------------------------------------------------------------
# Unit tests: SSEEvent model
# ---------------------------------------------------------------------------

class TestSSEEventModel:
    def test_to_sse_line_format(self):
        event = SSEEvent.make(
            type=SSEEventType.SESSION_STARTED,
            message="Test session",
        )
        line = event.to_sse_line()
        assert line.startswith("data: ")
        assert line.endswith("\n\n")
        payload = json.loads(line[len("data: "):].strip())
        assert payload["type"] == "session_started"
        assert payload["message"] == "Test session"
        assert "timestamp" in payload

    def test_event_has_required_fields(self):
        event = SSEEvent.make(
            type=SSEEventType.ERROR_DETECTED,
            message="NameError at line 5",
            attempt=1,
            status="running",
            details={"error_type": "NameError"},
        )
        assert event.attempt == 1
        assert event.status == "running"
        assert event.details["error_type"] == "NameError"

    def test_default_status_is_running(self):
        event = SSEEvent.make(type=SSEEventType.EXECUTE_STARTED, message="x")
        assert event.status == "running"


# ---------------------------------------------------------------------------
# Unit tests: node_to_sse_events emitter
# ---------------------------------------------------------------------------

class TestNodeToSSEEvents:

    def _make_exec_result(self, success: bool) -> ExecutionResult:
        return ExecutionResult(
            success=success,
            stdout="500\n" if success else "",
            stderr="" if success else "NameError: name 'x' is not defined",
            exit_code=0 if success else 1,
            execution_time=0.05,
            language="python",
            error_type=None if success else "NameError",
        )

    def _make_observation(self) -> ErrorObservation:
        return ErrorObservation(
            language="python",
            error_type="NameError",
            error_message="name 'x' is not defined",
            file_name="solution.py",
            line_number=3,
            column_number=None,
            stack_trace="Traceback...",
            stdout="",
            stderr="NameError: name 'x' is not defined",
        )

    def _make_diagnosis(self) -> RepairDiagnosis:
        return RepairDiagnosis(
            diagnosis="Variable x is not defined.",
            root_cause="Undefined variable",
            error_category="NameError",
            confidence=0.92,
            repair_strategy="Define x before use",
            affected_lines=[3],
        )

    def _make_validation(self, passed: bool) -> ValidationResult:
        return ValidationResult(
            passed=passed,
            total_tests=3,
            passed_tests=3 if passed else 1,
            failed_tests=0 if passed else 2,
            stdout="",
            stderr="" if passed else "AssertionError",
            failure_details=[] if passed else [
                TestFailureDetail(test_name="test_one", message="AssertionError: expected 5 got 3"),
            ],
        )

    def test_execute_node_emits_two_events(self):
        delta = {"execution_result": self._make_exec_result(False)}
        events = node_to_sse_events("execute", delta, attempt=0)
        assert len(events) == 2
        assert events[0].type == SSEEventType.EXECUTE_STARTED
        assert events[1].type == SSEEventType.EXECUTE_COMPLETED

    def test_execute_node_success_flag(self):
        delta = {"execution_result": self._make_exec_result(True)}
        events = node_to_sse_events("execute", delta, attempt=0)
        completed = events[1]
        assert "passed" in completed.message
        assert completed.details["success"] is True

    def test_observe_node_emits_error_event(self):
        delta = {"error_observation": self._make_observation()}
        events = node_to_sse_events("observe", delta, attempt=0)
        assert len(events) == 1
        assert events[0].type == SSEEventType.ERROR_DETECTED
        assert "NameError" in events[0].message
        assert "line 3" in events[0].message

    def test_observe_node_no_event_when_no_error(self):
        delta = {"error_observation": None}
        events = node_to_sse_events("observe", delta, attempt=0)
        assert events == []

    def test_diagnose_node_emits_two_events(self):
        delta = {"diagnosis": self._make_diagnosis()}
        events = node_to_sse_events("diagnose", delta, attempt=1)
        assert len(events) == 2
        assert events[0].type == SSEEventType.DIAGNOSIS_STARTED
        assert events[1].type == SSEEventType.DIAGNOSIS_COMPLETED
        assert "92%" in events[1].message

    def test_patch_node_emits_two_events(self):
        patch = CodePatch(
            explanation="Fixed undefined variable x by adding x = 0",
            patched_code="x = 0\nprint(x)",
            diff="",
        )
        delta = {"patch": patch}
        events = node_to_sse_events("patch", delta, attempt=1)
        assert len(events) == 2
        assert events[0].type == SSEEventType.PATCH_STARTED
        assert events[1].type == SSEEventType.PATCH_GENERATED
        assert "Fixed undefined variable" in events[1].message

    def test_validate_node_emits_two_events(self):
        delta = {"validation_result": self._make_validation(True)}
        events = node_to_sse_events("validate_initial", delta, attempt=0)
        assert len(events) == 2
        assert events[0].type == SSEEventType.VALIDATION_STARTED
        assert events[1].type == SSEEventType.VALIDATION_COMPLETED
        assert "passed" in events[1].message

    def test_validate_repaired_failure(self):
        delta = {"validation_result": self._make_validation(False)}
        events = node_to_sse_events("validate_repaired", delta, attempt=1)
        completed = events[1]
        assert "failed" in completed.message
        assert completed.details["failed_tests"] == 2

    def test_retry_node_success(self):
        delta = {"attempt": 1, "status": "success"}
        events = node_to_sse_events("retry", delta, attempt=1)
        assert len(events) == 1
        assert events[0].type == SSEEventType.REPAIR_SUCCESS
        assert events[0].status == "success"

    def test_retry_node_max_attempts(self):
        delta = {"attempt": 5, "status": "max_attempts_reached"}
        events = node_to_sse_events("retry", delta, attempt=5)
        assert events[0].type == SSEEventType.REPAIR_FAILED
        assert events[0].status == "failed"

    def test_retry_node_continue(self):
        delta = {"attempt": 2, "status": "running"}
        events = node_to_sse_events("retry", delta, attempt=2)
        assert events[0].type == SSEEventType.RETRY_STARTED

    def test_unknown_node_returns_empty(self):
        events = node_to_sse_events("unknown_future_node", {}, attempt=0)
        assert events == []


# ---------------------------------------------------------------------------
# Integration tests: /api/repair/stream HTTP endpoint
# ---------------------------------------------------------------------------

class TestSSEStreamEndpoint:
    """
    Integration tests using a mocked LangGraph graph to avoid real LLM calls.
    We inject a fake graph whose .stream() yields controlled chunks.
    """

    def _make_clean_exec_result(self) -> ExecutionResult:
        return ExecutionResult(
            success=True, stdout="Hello", stderr="",
            exit_code=0, execution_time=0.01, language="python",
        )

    def test_empty_code_returns_400_or_422(self):
        """Empty source_code must be rejected before streaming begins.
        FastAPI returns 422 when Pydantic validation fails on the request body.
        """
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/api/repair/stream", json={
            "source_code": "   ",
            "language": "python",
        })
        # 422: Pydantic field_validator rejects whitespace-only source_code
        assert resp.status_code in (400, 422)

    def test_stream_returns_text_event_stream_content_type(self):
        """Verify correct media type is set."""
        # Build a fake graph whose stream() returns immediately with success
        fake_exec_result = self._make_clean_exec_result()
        fake_val_result = ValidationResult(
            passed=True, total_tests=1, passed_tests=1,
            failed_tests=0, stdout="ok", stderr="", failure_details=[],
        )

        fake_chunks = [
            {"execute": {"execution_result": fake_exec_result, "status": "running"}},
            {"observe": {"error_observation": None, "status": "running"}},
            {"validate_initial": {"validation_result": fake_val_result, "status": "success"}},
        ]

        fake_graph = MagicMock()
        fake_graph.stream.return_value = iter(fake_chunks)

        with patch("app.main.create_autofix_graph", return_value=fake_graph):
            client = TestClient(app)
            resp = client.post("/api/repair/stream", json={
                "source_code": "print('hello')",
                "language": "python",
                "max_attempts": 3,
            })

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_first_event_is_session_started(self):
        """First event must always be session_started."""
        fake_exec_result = self._make_clean_exec_result()
        fake_val_result = ValidationResult(
            passed=True, total_tests=1, passed_tests=1,
            failed_tests=0, stdout="ok", stderr="", failure_details=[],
        )

        fake_chunks = [
            {"execute": {"execution_result": fake_exec_result}},
            {"observe": {"error_observation": None}},
            {"validate_initial": {"validation_result": fake_val_result}},
        ]

        fake_graph = MagicMock()
        fake_graph.stream.return_value = iter(fake_chunks)

        with patch("app.main.create_autofix_graph", return_value=fake_graph):
            client = TestClient(app)
            resp = client.post("/api/repair/stream", json={
                "source_code": "print('hi')",
                "language": "python",
            })

        events = parse_sse_lines(resp.text)
        assert len(events) > 0
        assert events[0]["type"] == "session_started"

    def test_stream_clean_code_ends_with_success(self):
        """Code that passes validation immediately should emit repair_success."""
        fake_exec_result = self._make_clean_exec_result()
        fake_val_result = ValidationResult(
            passed=True, total_tests=1, passed_tests=1,
            failed_tests=0, stdout="ok", stderr="", failure_details=[],
        )

        fake_chunks = [
            {"execute": {"execution_result": fake_exec_result}},
            {"observe": {"error_observation": None}},
            {"validate_initial": {"validation_result": fake_val_result}},
        ]

        fake_graph = MagicMock()
        fake_graph.stream.return_value = iter(fake_chunks)

        with patch("app.main.create_autofix_graph", return_value=fake_graph):
            client = TestClient(app)
            resp = client.post("/api/repair/stream", json={
                "source_code": "print('hi')",
                "language": "python",
            })

        events = parse_sse_lines(resp.text)
        types = [e["type"] for e in events]
        # Should have session_started ... validation_completed ... repair_success
        assert "session_started" in types
        assert "validation_completed" in types
        # Last meaningful event should be success (or fallback success)
        terminal_events = [e for e in events if e["type"] in ("repair_success", "repair_failed")]
        assert len(terminal_events) >= 1
        assert terminal_events[-1]["type"] == "repair_success"

    def test_stream_max_attempts_ends_with_failed(self):
        """When max_attempts is hit, stream must end with repair_failed."""
        fake_exec_result = ExecutionResult(
            success=False, stdout="", stderr="NameError: x",
            exit_code=1, execution_time=0.01, language="python",
            error_type="NameError",
        )
        fake_obs = ErrorObservation(
            language="python", error_type="NameError",
            error_message="name 'x' is not defined",
            file_name=None, line_number=None, column_number=None,
            stack_trace="", stdout="", stderr="NameError: x",
        )
        fake_val = ValidationResult(
            passed=False, total_tests=1, passed_tests=0,
            failed_tests=1, stdout="", stderr="NameError",
            failure_details=[TestFailureDetail(test_name="exec", message="NameError")],
        )
        fake_diag = RepairDiagnosis(
            diagnosis="x is undefined", root_cause="Missing variable",
            error_category="NameError", confidence=0.9,
            repair_strategy="Define x", affected_lines=[1],
        )
        fake_patch = CodePatch(
            explanation="Added x = 0",
            patched_code="x = 0\nprint(x)",
            diff="",
        )

        fake_chunks = [
            {"execute": {"execution_result": fake_exec_result}},
            {"observe": {"error_observation": fake_obs}},
            {"diagnose": {"diagnosis": fake_diag}},
            {"patch": {"patch": fake_patch, "current_code": "x = 0\nprint(x)"}},
            {"validate_repaired": {"validation_result": fake_val}},
            {"retry": {"attempt": 1, "status": "max_attempts_reached", "history": []}},
        ]

        fake_graph = MagicMock()
        fake_graph.stream.return_value = iter(fake_chunks)

        with patch("app.main.create_autofix_graph", return_value=fake_graph):
            client = TestClient(app)
            resp = client.post("/api/repair/stream", json={
                "source_code": "print(x)",
                "language": "python",
                "max_attempts": 1,
            })

        events = parse_sse_lines(resp.text)
        types = [e["type"] for e in events]
        assert "session_started" in types
        assert "error_detected" in types
        assert "repair_failed" in types
        # Must end with repair_failed
        terminal = [e for e in events if e["type"] in ("repair_success", "repair_failed")]
        assert terminal[-1]["type"] == "repair_failed"
        assert terminal[-1]["status"] == "failed"

    def test_all_events_are_valid_json(self):
        """Every SSE line must be parseable as JSON."""
        fake_exec_result = self._make_clean_exec_result()
        fake_val_result = ValidationResult(
            passed=True, total_tests=1, passed_tests=1,
            failed_tests=0, stdout="ok", stderr="", failure_details=[],
        )
        fake_chunks = [
            {"execute": {"execution_result": fake_exec_result}},
            {"observe": {"error_observation": None}},
            {"validate_initial": {"validation_result": fake_val_result}},
        ]
        fake_graph = MagicMock()
        fake_graph.stream.return_value = iter(fake_chunks)

        with patch("app.main.create_autofix_graph", return_value=fake_graph):
            client = TestClient(app)
            resp = client.post("/api/repair/stream", json={
                "source_code": "print(1)",
                "language": "python",
            })

        # parse_sse_lines will raise json.JSONDecodeError if any line is invalid
        events = parse_sse_lines(resp.text)
        assert len(events) > 0
        for event in events:
            assert "type" in event
            assert "message" in event
            assert "timestamp" in event
