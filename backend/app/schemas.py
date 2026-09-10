from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.execution.base import ExecutionResult
from app.analysis.models import ErrorObservation
from app.llm.models import RepairDiagnosis
from app.validation.base import ValidationResult
from app.agent.state import HistoryItem, LanguageValidationResult

# Maximum allowed source/test code size in bytes (100 KB).
_MAX_CODE_BYTES: int = 102_400

# Allowed language identifiers (must match ExecutionManager.ALLOWED_LANGUAGES).
_ALLOWED_LANGUAGES: frozenset = frozenset({"python", "py", "javascript", "js", "java"})


def _validate_source_code(v: str) -> str:
    """Shared validator: ensures source_code is non-empty and within size limits."""
    stripped = v.strip()
    if not stripped:
        raise ValueError("source_code must not be empty or whitespace-only.")
    if len(v.encode("utf-8")) > _MAX_CODE_BYTES:
        raise ValueError(
            f"source_code exceeds the maximum allowed size of {_MAX_CODE_BYTES // 1024}KB."
        )
    return v


def _validate_language(v: str) -> str:
    """Shared validator: ensures language is in the supported allowlist."""
    normalized = v.strip().lower()
    if normalized not in _ALLOWED_LANGUAGES:
        raise ValueError(
            f"Unsupported language '{v}'. Allowed values: python, javascript, java."
        )
    return normalized


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Request payload for /api/analyze."""
    source_code: str = Field(..., description="Source code to execute and analyze")
    language: str = Field("python", description="Programming language (python, javascript, java)")
    timeout: Optional[float] = Field(5.0, ge=0.5, le=30.0, description="Execution timeout in seconds")

    @field_validator("source_code")
    @classmethod
    def validate_source_code(cls, v: str) -> str:
        return _validate_source_code(v)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        return _validate_language(v)


class RepairRequest(BaseModel):
    """Request payload for /api/repair."""
    source_code: str = Field(..., description="Initial buggy or suspected source code")
    language: str = Field("python", description="Programming language (python, javascript, java)")
    max_attempts: Optional[int] = Field(5, ge=1, le=10, description="Maximum iterative repair attempts")
    timeout: Optional[float] = Field(5.0, ge=0.5, le=30.0, description="Execution/validation timeout per run")
    test_code: Optional[str] = Field(None, description="Optional test suite code for test-driven validation")

    @field_validator("source_code")
    @classmethod
    def validate_source_code(cls, v: str) -> str:
        return _validate_source_code(v)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        return _validate_language(v)

    @field_validator("test_code")
    @classmethod
    def validate_test_code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.encode("utf-8")) > _MAX_CODE_BYTES:
            raise ValueError(
                f"test_code exceeds the maximum allowed size of {_MAX_CODE_BYTES // 1024}KB."
            )
        return v


# ---------------------------------------------------------------------------
# Event & Response Schemas
# ---------------------------------------------------------------------------

class AgentEvent(BaseModel):
    """Concise agent progress event suitable for UI status streaming/display."""
    type: str = Field(..., description="Event type, e.g. execution, observation, diagnosis, patch, validation")
    attempt: int = Field(0, description="Attempt index during which the event occurred")
    message: str = Field(..., description="Human-readable concise summary of the action/result")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional lightweight metadata")


class AnalyzeResponse(BaseModel):
    """Response returned by /api/analyze."""
    language: str
    detected_language: str
    language_validation: LanguageValidationResult
    execution_result: Optional[ExecutionResult] = None
    error_observation: Optional[ErrorObservation] = None


class RepairResponse(BaseModel):
    """Response returned by /api/repair."""
    session_id: str = Field(..., description="Unique session identifier for the repair run")
    status: str = Field(..., description="Outcome status: success, max_attempts_reached, or failed")
    language: str
    detected_language: str
    language_validation: LanguageValidationResult
    attempts: int = Field(..., description="Total repair iterations performed")
    final_code: str = Field(..., description="Final repaired source code")
    diagnosis: Optional[RepairDiagnosis] = Field(None, description="Latest diagnostic analysis")
    validation_result: Optional[ValidationResult] = Field(None, description="Latest test validation result")
    execution_result: Optional[ExecutionResult] = Field(None, description="Latest runtime execution result")
    history: List[HistoryItem] = Field(default_factory=list, description="Snapshots of each attempt")
    events: List[AgentEvent] = Field(default_factory=list, description="Concise timeline events")


class HealthResponse(BaseModel):
    """Response returned by /api/health."""
    status: str
    service: str
