from typing import List, Optional
from pydantic import BaseModel, Field


class RepairAttempt(BaseModel):
    """Represents a previous repair attempt that was tried and failed."""
    iteration: int
    modified_code: str
    failure_reason: str


class RepairDiagnosis(BaseModel):
    """Structured output returned by the LLM diagnosis model."""
    diagnosis: str = Field(
        ...,
        description="Detailed explanation of what went wrong during code execution",
    )
    root_cause: str = Field(
        ...,
        description="The specific underlying bug or programming mistake causing the failure",
    )
    error_category: str = Field(
        ...,
        description="Standard classification, e.g., Syntax, NameResolution, TypeMismatch, IndexOutOfBounds, Logic, Environment",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0 in the diagnosis",
    )
    repair_strategy: str = Field(
        ...,
        description="Actionable step-by-step guidance on how the code should be repaired",
    )
    affected_lines: List[int] = Field(
        default_factory=list,
        description="1-based line numbers in the source code that need modification or are involved in the error",
    )
