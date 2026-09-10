"""
SSE Emitter — translates LangGraph node output deltas into SSEEvent lists.

LangGraph .stream(stream_mode="updates") yields dicts keyed by node name,
each containing only the state fields mutated by that node. This module
maps those deltas to the appropriate typed SSEEvents for the frontend.

Node names match those registered in graph.py:
  execute, observe, validate_initial, diagnose, patch, validate_repaired, retry
"""

from typing import Any, Dict, List
from app.streaming.events import SSEEvent, SSEEventType


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _current_attempt(delta: Dict[str, Any], default: int = 0) -> int:
    """Extract attempt count from state delta."""
    return int(delta.get("attempt", default))


# ---------------------------------------------------------------------------
# Public translator
# ---------------------------------------------------------------------------

def node_to_sse_events(node_name: str, state_delta: Dict[str, Any], attempt: int = 0) -> List[SSEEvent]:
    """
    Translate a single LangGraph node completion into one or more SSEEvents.

    Args:
        node_name:    Name of the completed LangGraph node.
        state_delta:  Dict of state fields updated by this node (stream_mode="updates").
        attempt:      Current repair attempt index from accumulated state.

    Returns:
        List of SSEEvent instances (usually 1, occasionally 2 for execute/observe pair).
    """
    events: List[SSEEvent] = []
    make = SSEEvent.make

    if node_name == "execute":
        exec_result = state_delta.get("execution_result")
        events.append(make(
            type=SSEEventType.EXECUTE_STARTED,
            message="Executing code in isolated sandbox...",
            attempt=attempt,
        ))
        if exec_result is not None:
            success = getattr(exec_result, "success", False)
            duration = getattr(exec_result, "execution_time", 0.0)
            events.append(make(
                type=SSEEventType.EXECUTE_COMPLETED,
                message=f"Execution completed in {duration:.3f}s — {'passed' if success else 'error detected'}.",
                attempt=attempt,
                status="running",
                details={"success": success, "execution_time": duration},
            ))

    elif node_name == "observe":
        obs = state_delta.get("error_observation")
        if obs is not None:
            err_type = getattr(obs, "error_type", "UnknownError")
            err_msg  = getattr(obs, "error_message", "")
            line_num = getattr(obs, "line_number", None)
            loc = f" at line {line_num}" if line_num else ""
            events.append(make(
                type=SSEEventType.ERROR_DETECTED,
                message=f"{err_type}{loc}: {err_msg}",
                attempt=attempt,
                details={"error_type": err_type, "line_number": line_num},
            ))
        # If no observation: execution was clean, validation follows — no event needed

    elif node_name in ("validate_initial", "validate_repaired"):
        events.append(make(
            type=SSEEventType.VALIDATION_STARTED,
            message="Running test suite validation...",
            attempt=attempt,
        ))
        val = state_delta.get("validation_result")
        if val is not None:
            passed      = getattr(val, "passed", False)
            total       = getattr(val, "total_tests", 0)
            passed_cnt  = getattr(val, "passed_tests", 0)
            failed_cnt  = getattr(val, "failed_tests", 0)
            summary = f"{passed_cnt}/{total} tests passed" if total > 0 else ("passed" if passed else "failed")
            events.append(make(
                type=SSEEventType.VALIDATION_COMPLETED,
                message=f"Validation {'passed' if passed else 'failed'} — {summary}.",
                attempt=attempt,
                status="running",
                details={"passed": passed, "total_tests": total, "passed_tests": passed_cnt, "failed_tests": failed_cnt},
            ))

    elif node_name == "diagnose":
        events.append(make(
            type=SSEEventType.DIAGNOSIS_STARTED,
            message="Analyzing error with AI diagnostics...",
            attempt=attempt,
        ))
        diag = state_delta.get("diagnosis")
        if diag is not None:
            category   = getattr(diag, "error_category", "")
            confidence = getattr(diag, "confidence", 0.0)
            strategy   = getattr(diag, "repair_strategy", "")
            confidence_pct = int(round(confidence * 100)) if isinstance(confidence, float) and confidence <= 1 else int(confidence)
            msg = f"{category} identified — {confidence_pct}% confidence. Strategy: {strategy}"
            events.append(make(
                type=SSEEventType.DIAGNOSIS_COMPLETED,
                message=msg,
                attempt=attempt,
                details={"error_category": category, "confidence": confidence_pct},
            ))

    elif node_name == "patch":
        events.append(make(
            type=SSEEventType.PATCH_STARTED,
            message="Generating code patch...",
            attempt=attempt,
        ))
        patch = state_delta.get("patch")
        if patch is not None:
            explanation = getattr(patch, "explanation", "Patch applied.")
            events.append(make(
                type=SSEEventType.PATCH_GENERATED,
                message=explanation,
                attempt=attempt,
            ))

    elif node_name == "retry":
        new_attempt = _current_attempt(state_delta, default=attempt)
        status_val  = state_delta.get("status", "running")

        if status_val == "success":
            events.append(make(
                type=SSEEventType.REPAIR_SUCCESS,
                message=f"Code repaired and validated successfully in {new_attempt} attempt(s).",
                attempt=new_attempt,
                status="success",
            ))
        elif status_val == "max_attempts_reached":
            events.append(make(
                type=SSEEventType.REPAIR_FAILED,
                message=f"Maximum repair attempts ({new_attempt}) reached without a passing solution.",
                attempt=new_attempt,
                status="failed",
            ))
        else:
            events.append(make(
                type=SSEEventType.RETRY_STARTED,
                message=f"Attempt {new_attempt} — retrying repair cycle.",
                attempt=new_attempt,
            ))

    return events
