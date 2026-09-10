import pytest
from app.agent.graph import create_autofix_graph
from app.agent.nodes import AgentNodeHandler, GeneratedPatch
from app.agent.state import AgentState
from app.execution.manager import ExecutionManager
from app.llm.client import LLMDiagnosisClient
from app.llm.models import RepairDiagnosis
from langchain_core.runnables import RunnableLambda


def make_test_handler(patch_fn, diagnosis_fn=None):
    """Helper to build an AgentNodeHandler with deterministic mocks for testing."""
    default_diagnosis = RepairDiagnosis(
        diagnosis="Undefined variable error",
        root_cause="Referencing undefined identifier",
        error_category="NameResolution",
        confidence=0.99,
        repair_strategy="Define variable before use",
        affected_lines=[1],
    )

    mock_llm = RunnableLambda(lambda inp: diagnosis_fn(inp) if diagnosis_fn else default_diagnosis)
    diag_client = LLMDiagnosisClient(chat_model=mock_llm)
    exec_manager = ExecutionManager()

    return AgentNodeHandler(
        execution_manager=exec_manager,
        diagnosis_client=diag_client,
        patch_generator_fn=patch_fn,
    )


def test_immediate_success():
    """If initial code runs without error, agent stops immediately at OBSERVE -> END."""
    clean_code = "print('Hello AutoFix')"

    handler = make_test_handler(
        patch_fn=lambda lang, code, diag: GeneratedPatch(
            explanation="Unused", patched_code="Unused"
        )
    )
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": clean_code,
        "current_code": clean_code,
        "test_code": None,
        "language": "python",
        "attempt": 0,
        "max_attempts": 5,
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
    assert final_state["attempt"] == 0
    assert len(final_state["history"]) == 0
    assert final_state["current_code"] == clean_code


def test_one_repair_success():
    """Agent detects bug on first run, repairs it, validates, and terminates successfully."""
    broken_code = "print(undefined_val)"
    fixed_code = "undefined_val = 'fixed'\nprint(undefined_val)"

    def mock_patch(language, current_code, diagnosis):
        return GeneratedPatch(
            explanation="Define undefined_val",
            patched_code=fixed_code,
        )

    handler = make_test_handler(patch_fn=mock_patch)
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": broken_code,
        "current_code": broken_code,
        "test_code": None,
        "language": "python",
        "attempt": 0,
        "max_attempts": 5,
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
    assert final_state["attempt"] == 1
    assert len(final_state["history"]) == 1
    assert final_state["history"][0].status == "success"
    assert "Passed" in final_state["history"][0].validation_result
    assert final_state["current_code"] == fixed_code



def test_multiple_repairs_success():
    """Agent takes 2 attempts: first patch still has an error, second patch succeeds."""
    step_codes = [
        "print(second_bug)",  # attempt 1: introduces second_bug
        "print('All fixed')",  # attempt 2: fully fixed
    ]
    call_count = {"count": 0}

    def progressive_patch(language, current_code, diagnosis):
        code = step_codes[call_count["count"]]
        call_count["count"] += 1
        return GeneratedPatch(
            explanation=f"Applying patch step {call_count['count']}",
            patched_code=code,
        )

    handler = make_test_handler(patch_fn=progressive_patch)
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": "print(first_bug)",
        "current_code": "print(first_bug)",
        "test_code": None,
        "language": "python",
        "attempt": 0,
        "max_attempts": 5,
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
    assert final_state["attempt"] == 2
    assert len(final_state["history"]) == 2
    assert final_state["history"][0].status == "failed"
    assert final_state["history"][1].status == "success"
    assert "All fixed" in final_state["current_code"]


def test_maximum_attempts_reached():
    """Agent stops immediately when attempt reaches max_attempts and sets appropriate status."""
    broken_code = "raise RuntimeError('cannot fix')"

    def failing_patch(language, current_code, diagnosis):
        # Keeps returning broken code
        return GeneratedPatch(
            explanation="Failed attempt",
            patched_code=broken_code,
        )

    handler = make_test_handler(patch_fn=failing_patch)
    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": broken_code,
        "current_code": broken_code,
        "test_code": None,
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

    assert final_state["status"] == "max_attempts_reached"
    assert final_state["attempt"] == 3
    assert len(final_state["history"]) == 3
    # Check that each attempt is recorded in history
    for item in final_state["history"]:
        assert item.status == "failed"
        assert "Failed" in item.validation_result



def test_unrepairable_code():
    """Unrepairable code stops gracefully at max_attempts without infinite looping."""
    broken_code = "while True: pass"  # Timeout error code

    def unrepairable_patch(language, current_code, diagnosis):
        return GeneratedPatch(
            explanation="Still unrepairable",
            patched_code="while True: pass",
        )

    handler = make_test_handler(patch_fn=unrepairable_patch)
    # Give a short timeout to prevent slow test execution
    handler.execution_manager.default_timeout = 0.5
    handler.execution_manager.get_executor("python").timeout = 0.5

    graph = create_autofix_graph(handler)

    initial_state: AgentState = {
        "original_code": broken_code,
        "current_code": broken_code,
        "test_code": None,
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
    assert "timed out" in final_state["history"][0].error.lower()
