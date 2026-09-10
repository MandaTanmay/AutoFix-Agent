from unittest.mock import MagicMock

from app.agent.graph import create_autofix_graph
from app.agent.nodes import AgentNodeHandler, GeneratedPatch
from app.agent.state import AgentState
from app.analysis.language_detector import detect_language
from app.execution.manager import ExecutionManager


PYTHON_CODE = "def calculate_total(price, quantity):\n    return priice * quantity\n\nprint(calculate_total(100, 5))"


def make_state(language: str) -> AgentState:
    return {
        "original_code": PYTHON_CODE,
        "current_code": PYTHON_CODE,
        "test_code": None,
        "language": language,
        "detected_language": "unknown",
        "language_validation": None,
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


def test_python_source_matches_python_selection():
    detection = detect_language(PYTHON_CODE)
    assert detection.language == "python"

    handler = AgentNodeHandler()
    result = handler.detect_language_node(make_state("python"))
    assert result["language_validation"].is_match is True


def test_python_source_mismatches_java_without_execution():
    execution_manager = MagicMock(spec=ExecutionManager)
    handler = AgentNodeHandler(execution_manager=execution_manager)
    final_state = create_autofix_graph(handler).invoke(make_state("java"))

    assert final_state["status"] == "language_mismatch"
    assert final_state["detected_language"] == "python"
    assert final_state["language_validation"].is_match is False
    assert final_state["attempt"] == 0
    assert final_state["execution_result"] is None
    execution_manager.execute.assert_not_called()


def test_python_source_mismatches_javascript():
    result = AgentNodeHandler().detect_language_node(make_state("javascript"))
    assert result["detected_language"] == "python"
    assert result["language_validation"].is_match is False


def test_matching_python_source_enters_normal_autofix_workflow():
    execution_manager = ExecutionManager()
    handler = AgentNodeHandler(
        execution_manager=execution_manager,
        patch_generator_fn=lambda language, code, diagnosis: GeneratedPatch(
            explanation="Fix typo", patched_code="print(500)"
        ),
    )
    final_state = create_autofix_graph(handler).invoke(make_state("python"))

    assert final_state["status"] == "success"
    assert final_state["attempt"] == 1
    assert final_state["current_code"] == "print(500)"