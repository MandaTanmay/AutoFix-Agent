"""
SSEEvent — typed Server-Sent Event model for AutoFix Agent streaming.

Events are serialized as JSON and sent over the text/event-stream protocol.
Only user-facing summaries are emitted — no internal chain-of-thought.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SSEEventType(str, Enum):
    """All valid SSE event types emitted by the repair stream."""
    SESSION_STARTED    = "session_started"
    EXECUTE_STARTED    = "execute_started"
    EXECUTE_COMPLETED  = "execute_completed"
    ERROR_DETECTED     = "error_detected"
    DIAGNOSIS_STARTED  = "diagnosis_started"
    DIAGNOSIS_COMPLETED= "diagnosis_completed"
    PATCH_STARTED      = "patch_started"
    PATCH_GENERATED    = "patch_generated"
    VALIDATION_STARTED = "validation_started"
    VALIDATION_COMPLETED = "validation_completed"
    RETRY_STARTED      = "retry_started"
    REPAIR_SUCCESS     = "repair_success"
    REPAIR_FAILED      = "repair_failed"
    STREAM_ERROR       = "stream_error"


class SSEEvent(BaseModel):
    """
    A single SSE event emitted during the agent repair workflow.
    
    Only safe, user-facing summaries are included.
    No raw chain-of-thought or internal debug data is exposed.
    """
    type: SSEEventType
    attempt: int = Field(0, description="Repair iteration index (0 = initial execution)")
    status: str = Field("running", description="Agent lifecycle status: running | success | failed")
    message: str = Field(..., description="Concise human-readable summary")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp",
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional lightweight metadata (e.g. error_type, confidence, test_counts)",
    )

    def to_sse_line(self) -> str:
        """
        Serialize to SSE wire format.

        Returns a string of the form:
            data: {...json...}\\n\\n
        """
        return f"data: {self.model_dump_json()}\n\n"

    @classmethod
    def make(
        cls,
        type: SSEEventType,
        message: str,
        attempt: int = 0,
        status: str = "running",
        details: Optional[Dict[str, Any]] = None,
    ) -> "SSEEvent":
        """Convenience factory for concise event creation."""
        return cls(
            type=type,
            attempt=attempt,
            status=status,
            message=message,
            details=details,
        )
