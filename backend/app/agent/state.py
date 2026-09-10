from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field

from app.execution.base import ExecutionResult
from app.analysis.models import ErrorObservation
from app.llm.models import RepairDiagnosis


class CodePatch(BaseModel):
    """Represents the code modification produced by the patch node."""
    explanation: str = Field(..., description="Concise summary of the change")
    patched_code: str = Field(..., description="Full modified source code")
    diff: Optional[str] = Field(None, description="Optional unified diff representation")


class HistoryItem(BaseModel):
    """Historical snapshot of a repair iteration."""
    attempt: int
    error: Optional[str] = None
    diagnosis: Optional[str] = None
    patch: Optional[str] = None
    validation_result: Optional[str] = None
    status: str


class AgentState(TypedDict):
    """LangGraph State representation for the AutoFix code repair workflow."""
    original_code: str
    current_code: str
    language: str
    attempt: int
    max_attempts: int
    execution_result: Optional[ExecutionResult]
    error_observation: Optional[ErrorObservation]
    diagnosis: Optional[RepairDiagnosis]
    patch: Optional[CodePatch]
    validation_result: Optional[ExecutionResult]
    history: List[HistoryItem]
    status: str  # "running", "success", "failed", "max_attempts_reached"
