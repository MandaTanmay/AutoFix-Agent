import pytest
from langchain_core.runnables import RunnableLambda

from app.agent.graph import create_autofix_graph
from app.agent.nodes import AgentNodeHandler, GeneratedPatch
from app.agent.state import AgentState
from app.execution.manager import ExecutionManager
from app.validation.manager import ValidationManager
from app.llm.client import LLMDiagnosisClient
from app.llm.models import RepairDiagnosis
from app.validation.examples import (
    RUNTIME_BUG_CODE,
    RUNTIME_BUG_TEST,
    RUNTIME_BUG_FIXED,
    LOGIC_BUG_CODE,
    LOGIC_BUG_TEST,
    LOGIC_BUG_FIXED,
    CORRECT_CODE,
    CORRECT_CODE_TEST,
    UNFIXABLE_CODE,
    UNFIXABLE_CODE_TEST,
)


def make_agent_handler(patch_fn):
    default_diagnosis = RepairDiagnosis(
        diagnosis="Error identified",
        root_cause="Bug identified by test/execution observation",
        error_category="LogicOrRuntime",
        confidence=0.95,
        repair_strategy="Apply valid patch",
        affected_lines=[2],
    )
    mock_llm = RunnableLambda(lambda inp: default_diagnosis)
    diag_client = LLMDiagnosisClient(chat_model=mock_llm)
    exec_manager = ExecutionManager(default_timeout=2.0)
    val_manager = ValidationManager(default_timeout=4.0)

    return AgentNodeHandler(
        execution_manager=exec_manager,
        validation_manager=val_manager,
        diagnosis_client=diag_client,
        patch_generator_fn=patch_fn,
    )


# ---------------------------------------------------------------------------
# Test Case 1: Runtime Bug (crashes initially, repaired, and verified by tests)
# ---------------------------------------------------------------------------

def test_workflow_runtime_bug_repaired_and_validated():
    """Runtime bug crashes initial execution, agent diagnoses, patches, and pytest confirms fix."""
    def patch_fix(lang, current_code, diag):
        return GeneratedPatch(
            explanation="Replace rate_percent with discount_rate",
            patched_code=RUNTIME_BUG_FIXED,
        )

    handler = make_agent_handler(patch_fn=patch_fix)
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": RUNTIME_BUG_CODE,
        "current_code": RUNTIME_BUG_CODE,
        "test_code": RUNTIME_BUG_TEST,
        "language": "python",
        "attempt": 0,
        "max_attempts": 3,
        "execution_result": None,
        "error_observation": None,
        "diagnosis": None,
        "patch": None,
        "validation_result": None,
        "history": [],
        "status": "running",
    }

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "success"
    assert final_state["validation_result"].passed is True
    assert final_state["attempt"] == 1
    assert len(final_state["history"]) == 1
    assert "Passed" in final_state["history"][0].validation_result
    assert "discount_rate" in final_state["current_code"]


# ---------------------------------------------------------------------------
# Test Case 2: Logic Bug (runs without crashing, but fails tests, agent repairs)
# ---------------------------------------------------------------------------

def test_workflow_logic_bug_detected_by_tests_and_repaired():
    """
    Code runs with exit code 0 (no exception), but test suite fails!
    The agent must NOT consider it successful, but diagnose, patch, and validate.
    """
    def patch_fix(lang, current_code, diag):
        return GeneratedPatch(
            explanation="Change != to ==",
            patched_code=LOGIC_BUG_FIXED,
        )

    handler = make_agent_handler(patch_fn=patch_fix)
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": LOGIC_BUG_CODE,
        "current_code": LOGIC_BUG_CODE,
        "test_code": LOGIC_BUG_TEST,
        "language": "python",
        "attempt": 0,
        "max_attempts": 3,
        "execution_result": None,
        "error_observation": None,
        "diagnosis": None,
        "patch": None,
        "validation_result": None,
        "history": [],
        "status": "running",
    }

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "success"
    assert final_state["validation_result"].passed is True
    assert final_state["attempt"] == 1
    assert len(final_state["history"]) == 1
    assert final_state["history"][0].status == "success"
    assert "n % 2 == 0" in final_state["current_code"]


# ---------------------------------------------------------------------------
# Test Case 3: Correct Code (runs clean, passes tests immediately at START)
# ---------------------------------------------------------------------------

def test_workflow_correct_code_immediate_validation():
    """Valid code runs clean and passes tests immediately without entering repair."""
    handler = make_agent_handler(
        patch_fn=lambda l, c, d: GeneratedPatch(explanation="", patched_code="")
    )
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": CORRECT_CODE,
        "current_code": CORRECT_CODE,
        "test_code": CORRECT_CODE_TEST,
        "language": "python",
        "attempt": 0,
        "max_attempts": 3,
        "execution_result": None,
        "error_observation": None,
        "diagnosis": None,
        "patch": None,
        "validation_result": None,
        "history": [],
        "status": "running",
    }

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "success"
    assert final_state["validation_result"].passed is True
    assert final_state["attempt"] == 0  # No repair attempts needed
    assert len(final_state["history"]) == 0
    assert final_state["current_code"] == CORRECT_CODE


# ---------------------------------------------------------------------------
# Test Case 4: Unfixable Code (hits max attempts and stops safely)
# ---------------------------------------------------------------------------

def test_workflow_unfixable_code_stops_at_max_attempts():
    """Code that never satisfies tests terminates safely when max_attempts is reached."""
    def failing_patch(lang, current_code, diag):
        return GeneratedPatch(
            explanation="Unsuccessful patch",
            patched_code=UNFIXABLE_CODE,
        )

    handler = make_agent_handler(patch_fn=failing_patch)
    # Use short timeouts for test speed
    handler.execution_manager.default_timeout = 0.5
    handler.execution_manager.get_executor("python").timeout = 0.5
    handler.validation_manager.default_timeout = 0.8
    handler.validation_manager.get_validator("python").timeout = 0.8

    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": UNFIXABLE_CODE,
        "current_code": UNFIXABLE_CODE,
        "test_code": UNFIXABLE_CODE_TEST,
        "language": "python",
        "attempt": 0,
        "max_attempts": 2,
        "execution_result": None,
        "error_observation": None,
        "diagnosis": None,
        "patch": None,
        "validation_result": None,
        "history": [],
        "status": "running",
    }

    final_state = graph.invoke(initial_state)

    assert final_state["status"] == "max_attempts_reached"
    assert final_state["attempt"] == 2
    assert len(final_state["history"]) == 2
    for h in final_state["history"]:
        assert h.status == "failed"
