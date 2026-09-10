import difflib
import os
from typing import Any, Callable, Dict, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.execution.manager import ExecutionManager
from app.analysis.error_parser import ErrorParser
from app.llm.client import LLMDiagnosisClient
from app.llm.models import RepairAttempt, RepairDiagnosis
from app.agent.state import AgentState, CodePatch, HistoryItem


class GeneratedPatch(BaseModel):
    """Pydantic model for structured patch generation output."""
    explanation: str = Field(..., description="Concise explanation of what was fixed")
    patched_code: str = Field(..., description="Complete executable patched source code")


PATCH_SYSTEM_PROMPT = """You are an autonomous code repair assistant.
Given the original source code, the diagnosed error, and the suggested repair strategy, produce the complete repaired code.

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
    """Handles node execution logic with pluggable execution, analysis, and LLM services."""

    def __init__(
        self,
        execution_manager: Optional[ExecutionManager] = None,
        diagnosis_client: Optional[LLMDiagnosisClient] = None,
        patch_generator_fn: Optional[Callable[[str, str, RepairDiagnosis], GeneratedPatch]] = None,
    ):
        self.execution_manager = execution_manager or ExecutionManager()
        self.diagnosis_client = diagnosis_client or LLMDiagnosisClient()
        self.patch_generator_fn = patch_generator_fn

    def execute_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Execute the current code in a controlled environment."""
        language = state.get("language", "python")
        code = state.get("current_code", "")
        result = self.execution_manager.execute(language=language, code=code)
        return {
            "execution_result": result,
            "status": "success" if result.success else "running",
        }

    def observe_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Normalize and parse error traces into ErrorObservation."""
        exec_result = state.get("execution_result")
        if not exec_result:
            return {"error_observation": None}

        if exec_result.success:
            return {
                "error_observation": None,
                "status": "success",
            }

        observation = ErrorParser.parse(exec_result)
        return {
            "error_observation": observation,
            "status": "running",
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

        return {
            "patch": patch,
            "current_code": generated.patched_code,
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
            model_name=self.diagnosis_client.model_name,
            temperature=0.1,
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

    def validate_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 5: Execute the patched code to validate if the bug is resolved."""
        language = state.get("language", "python")
        current_code = state.get("current_code", "")
        val_result = self.execution_manager.execute(language=language, code=current_code)
        is_success = val_result.success

        return {
            "validation_result": val_result,
            "status": "success" if is_success else "running",
        }

    def retry_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 6: Record history snapshot, increment attempt counter, prepare next cycle."""
        attempt = state.get("attempt", 0) + 1
        max_attempts = state.get("max_attempts", 5)

        val_result = state.get("validation_result")
        obs = state.get("error_observation")
        diag = state.get("diagnosis")
        patch = state.get("patch")

        err_summary = None
        if val_result and not val_result.success:
            err_summary = val_result.stderr.strip() or f"Exit code {val_result.exit_code}"
        elif obs:
            err_summary = f"{obs.error_type}: {obs.error_message}"

        history_item = HistoryItem(
            attempt=attempt,
            error=err_summary,
            diagnosis=diag.diagnosis if diag else None,
            patch=patch.patched_code if patch else None,
            validation_result="Passed" if (val_result and val_result.success) else "Failed",
            status="success" if (val_result and val_result.success) else "failed",
        )

        updated_history = list(state.get("history", []))
        updated_history.append(history_item)

        new_status = "running"
        if val_result and val_result.success:
            new_status = "success"
        elif attempt >= max_attempts:
            new_status = "max_attempts_reached"

        return {
            "attempt": attempt,
            "history": updated_history,
            "status": new_status,
        }
