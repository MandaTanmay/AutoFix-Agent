import pytest
from unittest.mock import MagicMock
from langchain_core.runnables import RunnableLambda
from app.analysis.models import ErrorObservation
from app.llm.models import RepairDiagnosis, RepairAttempt
from app.llm.client import LLMDiagnosisClient
from app.llm.prompts import create_diagnosis_prompt, format_previous_attempts


def test_repair_diagnosis_schema_validation():
    """Verify RepairDiagnosis validation rules."""
    valid_data = {
        "diagnosis": "Variable 'formatted_name' is referenced before assignment.",
        "root_cause": "The variable 'formatted_name' does not exist in local or global scope.",
        "error_category": "NameResolution",
        "confidence": 0.95,
        "repair_strategy": "Define 'formatted_name = name.title()' before returning or replace with 'name'.",
        "affected_lines": [4],
    }
    diag = RepairDiagnosis(**valid_data)
    assert diag.confidence == 0.95
    assert diag.error_category == "NameResolution"
    assert diag.affected_lines == [4]


def test_format_previous_attempts():
    """Ensure previous repair attempts format appropriately into prompt context."""
    empty_result = format_previous_attempts(None)
    assert "None" in empty_result

    attempts = [
        RepairAttempt(
            iteration=1,
            modified_code="return f'Hello, {formatted_name}'",
            failure_reason="NameError: name 'formatted_name' is not defined",
        )
    ]
    formatted = format_previous_attempts(attempts)
    assert "Attempt #1" in formatted
    assert "failure_reason" not in formatted  # formatted as Failure Reason:
    assert "Failure Reason:" in formatted


def test_prompt_generation():
    """Ensure ChatPromptTemplate generates expected messages."""
    prompt = create_diagnosis_prompt()
    messages = prompt.format_messages(
        language="python",
        source_code="print(x)",
        error_type="NameError",
        error_message="name 'x' is not defined",
        file_name="solution.py",
        line_number=1,
        column_number=7,
        stack_trace="NameError: name 'x' is not defined",
        stdout="",
        stderr="NameError: name 'x' is not defined",
        previous_attempts_text="None",
    )
    assert len(messages) == 2
    assert "You are an expert autonomous code debugging and repair agent." in messages[0].content
    assert "Language: python" in messages[1].content
    assert "print(x)" in messages[1].content


def test_llm_client_missing_api_key_raises_error():
    """Verify that client fails gracefully when no API key is provided."""
    client = LLMDiagnosisClient(api_key="")
    obs = ErrorObservation(
        language="python",
        error_type="NameError",
        error_message="name 'x' is not defined",
        file_name="test.py",
        line_number=1,
        column_number=1,
        stack_trace="",
        stdout="",
        stderr="",
    )
    with pytest.raises(ValueError, match="GROQ_API_KEY is not set"):
        client.diagnose("python", "print(x)", obs)


def test_llm_client_with_mock_model():
    """Verify diagnosis flow using a mock runnable model without real Groq API calls."""
    expected_diagnosis = RepairDiagnosis(
        diagnosis="Undefined variable referenced",
        root_cause="The variable was never initialized in the scope.",
        error_category="NameResolution",
        confidence=0.98,
        repair_strategy="Initialize variable before access.",
        affected_lines=[1],
    )

    # Create a mock runnable model that mimics structured output invocation
    mock_runnable = RunnableLambda(lambda inputs: expected_diagnosis)

    client = LLMDiagnosisClient(chat_model=mock_runnable)

    obs = ErrorObservation(
        language="python",
        error_type="NameError",
        error_message="name 'x' is not defined",
        file_name="solution.py",
        line_number=1,
        column_number=7,
        stack_trace="NameError: name 'x' is not defined",
        stdout="",
        stderr="NameError: name 'x' is not defined",
    )

    diag = client.diagnose(
        language="python",
        source_code="print(x)",
        observation=obs,
        previous_attempts=[
            RepairAttempt(
                iteration=1,
                modified_code="print(x)",
                failure_reason="NameError: name 'x' is not defined",
            )
        ],
    )

    assert isinstance(diag, RepairDiagnosis)
    assert diag.confidence == 0.98
    assert diag.error_category == "NameResolution"
    assert diag.affected_lines == [1]
    assert diag.diagnosis == "Undefined variable referenced"
