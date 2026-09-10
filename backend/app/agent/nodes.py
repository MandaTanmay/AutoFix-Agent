import difflib
import os
from typing import Any, Callable, Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.execution.manager import ExecutionManager
from app.validation.manager import ValidationManager
from app.validation.base import ValidationResult, TestFailureDetail
from app.analysis.error_parser import ErrorParser
from app.analysis.models import ErrorObservation
from app.llm.client import LLMDiagnosisClient
from app.llm.models import RepairAttempt, RepairDiagnosis
from app.agent.state import AgentState, CodePatch, HistoryItem, LanguageValidationResult
from app.analysis.language_detector import detect_language


class GeneratedPatch(BaseModel):
    """Pydantic model for structured patch generation output."""
    explanation: str = Field(..., description="Concise explanation of what was fixed")
    patched_code: str = Field(..., description="Complete executable patched source code")


PATCH_SYSTEM_PROMPT = """You are an autonomous code repair assistant.
Given the original source code, the diagnosed error/test failure, and the suggested repair strategy, produce the complete repaired code.

CRITICAL INSTRUCTIONS:
1. Output MUST be strictly valid code in the target language.
2. Provide the full executable code in `patched_code`.
3. Provide a concise explanation in `explanation`.
4. Do NOT output markdown or explanations outside the structured fields.
5. No shell commands or external tools.
"""

PATCH_USER_TEMPLATE = """Language: {language}

Current Source Code:
```{language}
{current_code}
```

Diagnosis:
{diagnosis}

Root Cause:
{root_cause}

Repair Strategy:
{repair_strategy}

Affected Lines: {affected_lines}

Return the complete patched code fixing the error.
"""


def _compute_diff(original: str, modified: str) -> str:
    """Generate unified diff between original and modified code."""
    orig_lines = original.splitlines(keepends=True)
    mod_lines = modified.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines, mod_lines, fromfile="before.py", tofile="after.py", lineterm=""
    )
    return "".join(diff)


class AgentNodeHandler:
    """Handles node execution logic with pluggable execution, validation, analysis, and LLM services."""

    def __init__(
        self,
        execution_manager: Optional[ExecutionManager] = None,
        validation_manager: Optional[ValidationManager] = None,
        diagnosis_client: Optional[LLMDiagnosisClient] = None,
        patch_generator_fn: Optional[Callable[[str, str, RepairDiagnosis], GeneratedPatch]] = None,
    ):
        self.execution_manager = execution_manager or ExecutionManager()
        self.validation_manager = validation_manager or ValidationManager()
        self.diagnosis_client = diagnosis_client or LLMDiagnosisClient()
        self.patch_generator_fn = patch_generator_fn

    def detect_language_node(self, state: AgentState) -> Dict[str, Any]:
        """Detect source language and block the repair workflow on a mismatch."""
        selected = state.get("language", "python")
        selected = {"py": "python", "js": "javascript"}.get(selected, selected)
        detected, confidence = detect_language(state.get("current_code", ""))
        is_match = detected == selected
        if is_match:
            message = f"Detected language matches selected language: {detected}."
        else:
            message = (
                f"The uploaded code appears to be {detected.capitalize()}, "
                f"but {selected.capitalize()} is selected. "
                f"Please select {detected.capitalize()} to analyze and repair this code."
            )
        return {
            "detected_language": detected,
            "language_validation": LanguageValidationResult(
                selected_language=selected,
                detected_language=detected,
                is_match=is_match,
                confidence=confidence,
                message=message,
            ),
            "status": "running" if is_match else "language_mismatch",
        }

    def execute_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Execute the current code in a controlled environment."""
        language = state.get("language", "python")
        code = state.get("current_code", "")
        result = self.execution_manager.execute(language=language, code=code)
        return {
            "execution_result": result,
            "status": "running",
        }

    def observe_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Normalize and parse error traces into ErrorObservation if execution failed."""
        exec_result = state.get("execution_result")
        if not exec_result:
            return {"error_observation": None}

        if exec_result.success:
            return {
                "error_observation": None,
                "status": "running",
            }

        observation = ErrorParser.parse(exec_result)
        return {
            "error_observation": observation,
            "status": "running",
        }

    def validate_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node: Run test suite validation against the current code.
        Proves code correctness beyond mere zero-exit-code execution.
        """
        language = state.get("language", "python")
        code = state.get("current_code", "")
        test_code = state.get("test_code")

        # If no separate test code is provided, fallback to execution validation
        if not test_code:
            exec_res = self.execution_manager.execute(language=language, code=code)
            is_passed = exec_res.success
            val_result = ValidationResult(
                passed=is_passed,
                total_tests=1,
                passed_tests=1 if is_passed else 0,
                failed_tests=0 if is_passed else 1,
                stdout=exec_res.stdout,
                stderr=exec_res.stderr,
                failure_details=[] if is_passed else [
                    TestFailureDetail(test_name="execution", message=exec_res.stderr.strip() or "Failed with non-zero exit")
                ],
            )
        else:
            val_result = self.validation_manager.validate(
                language=language, code=code, test_code=test_code
            )

        # If validation failed due to assertion or test errors, synthesize ErrorObservation
        observation = state.get("error_observation")
        if not val_result.passed and not observation:
            first_fail = val_result.failure_details[0].message if val_result.failure_details else (val_result.stderr or "Tests failed")
            observation = ErrorObservation(
                language=language,
                error_type="AssertionError" if "AssertionError" in (val_result.stdout + val_result.stderr) else "TestFailure",
                error_message=first_fail,
                file_name=None,
                line_number=None,
                column_number=None,
                stack_trace=val_result.stdout or val_result.stderr,
                stdout=val_result.stdout,
                stderr=val_result.stderr,
            )

        return {
            "validation_result": val_result,
            "error_observation": observation,
            "status": "success" if val_result.passed else "running",
        }

    def diagnose_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Use structured LLM diagnosis to identify root cause & repair strategy."""
        language = state.get("language", "python")
        current_code = state.get("current_code", "")
        observation = state.get("error_observation")
        history = state.get("history", [])

        # Build list of prior repair attempts from history
        previous_attempts = [
            RepairAttempt(
                iteration=h.attempt,
                modified_code=h.patch or "",
                failure_reason=h.error or "Unknown failure",
            )
            for h in history
            if h.patch
        ]

        if not observation:
            return {"diagnosis": None}

        diagnosis = self.diagnosis_client.diagnose(
            language=language,
            source_code=current_code,
            observation=observation,
            previous_attempts=previous_attempts,
        )
        return {"diagnosis": diagnosis}

    def patch_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Synthesize the repaired source code based on the diagnosis."""
        language = state.get("language", "python")
        current_code = state.get("current_code", "")
        diagnosis = state.get("diagnosis")

        if not diagnosis:
            return {"patch": None}

        if self.patch_generator_fn:
            generated = self.patch_generator_fn(language, current_code, diagnosis)
        else:
            generated = self._default_llm_patch(language, current_code, diagnosis)

        diff_text = _compute_diff(current_code, generated.patched_code)
        patch = CodePatch(
            explanation=generated.explanation,
            patched_code=generated.patched_code,
            diff=diff_text,
        )

        # Clear previous error observation for the new attempt
        return {
            "patch": patch,
            "current_code": generated.patched_code,
            "error_observation": None,
        }

    def _default_llm_patch(
        self, language: str, current_code: str, diagnosis: RepairDiagnosis
    ) -> GeneratedPatch:
        """Default patch generator using Groq with structured output."""
        from langchain_groq import ChatGroq

        api_key = self.diagnosis_client.api_key
        if not api_key or api_key == "your_groq_api_key_here":
            raise ValueError("GROQ_API_KEY must be set to generate patches via LLM.")

        llm = ChatGroq(
            groq_api_key=api_key,
            model=self.diagnosis_client.model_name,
            temperature=0,
        ).with_structured_output(GeneratedPatch)

        prompt = ChatPromptTemplate.from_messages(
            [("system", PATCH_SYSTEM_PROMPT), ("user", PATCH_USER_TEMPLATE)]
        )
        chain = prompt | llm
        res = chain.invoke(
            {
                "language": language,
                "current_code": current_code,
                "diagnosis": diagnosis.diagnosis,
                "root_cause": diagnosis.root_cause,
                "repair_strategy": diagnosis.repair_strategy,
                "affected_lines": diagnosis.affected_lines,
            }
        )
        if isinstance(res, dict):
            return GeneratedPatch(**res)
        return res

    def retry_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 6: Record history snapshot, increment attempt counter, check loop limits."""
        attempt = state.get("attempt", 0) + 1
        max_attempts = state.get("max_attempts", 5)

        val_result = state.get("validation_result")
        obs = state.get("error_observation")
        diag = state.get("diagnosis")
        patch = state.get("patch")

        err_summary = None
        if val_result and not val_result.passed:
            first_fail = val_result.failure_details[0].message if val_result.failure_details else ""
            err_summary = first_fail or val_result.stderr.strip() or f"Tests failed ({val_result.failed_tests}/{val_result.total_tests})"
        elif obs:
            err_summary = f"{obs.error_type}: {obs.error_message}"

        history_item = HistoryItem(
            attempt=attempt,
            error=err_summary,
            diagnosis=diag.diagnosis if diag else None,
            patch=patch.patched_code if patch else None,
            validation_result=f"Passed ({val_result.passed_tests}/{val_result.total_tests})" if (val_result and val_result.passed) else f"Failed ({val_result.failed_tests if val_result else 1}/{val_result.total_tests if val_result else 1})",
            status="success" if (val_result and val_result.passed) else "failed",
        )

        updated_history = list(state.get("history", []))
        updated_history.append(history_item)

        new_status = "running"
        if val_result and val_result.passed:
            new_status = "success"
        elif attempt >= max_attempts:
            new_status = "max_attempts_reached"

        return {
            "attempt": attempt,
            "history": updated_history,
            "status": new_status,
        }
