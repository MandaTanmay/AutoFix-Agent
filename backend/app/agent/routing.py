from typing import Literal
from app.agent.state import AgentState


def check_language_match(state: AgentState) -> Literal["match", "mismatch"]:
    """Route only language-compatible source code into execution."""
    validation = state.get("language_validation")
    return "match" if validation and validation.is_match else "mismatch"


def check_runtime_error(state: AgentState) -> Literal["runtime_error", "validate"]:
    """
    Evaluates initial execution:
    - If there was a runtime exception / crash: proceed immediately to DIAGNOSE.
    - If execution ran without crashing: proceed to VALIDATE to test logic correctness.
    """
    exec_result = state.get("execution_result")
    if not exec_result or not exec_result.success:
        return "runtime_error"
    return "validate"


def check_validation_passed(state: AgentState) -> Literal["success", "needs_repair"]:
    """
    Evaluates test suite validation result:
    - If tests pass: terminate with success.
    - If tests fail (or logic bugs detected): proceed to DIAGNOSE.
    """
    val_result = state.get("validation_result")
    if val_result and val_result.passed:
        return "success"
    return "needs_repair"


def check_retry_decision(state: AgentState) -> Literal["success", "retry", "max_attempts_reached"]:
    """
    Evaluates whether the agent should terminate or loop after an attempted repair.
    """
    val_result = state.get("validation_result")
    if val_result and val_result.passed:
        return "success"

    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 5)

    if attempt >= max_attempts:
        return "max_attempts_reached"

    return "retry"
