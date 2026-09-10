import time
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field

# Maximum number of bytes to retain from stdout/stderr.
# Output beyond this limit is truncated to prevent memory abuse.
MAX_OUTPUT_BYTES: int = 65_536  # 64 KB


def _truncate_output(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    """Truncate text to at most max_bytes UTF-8 bytes, appending a notice if trimmed."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return truncated + f"\n[...output truncated at {max_bytes // 1024}KB...]"


class ExecutionResult(BaseModel):
    """Normalized result data model returned after executing code."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int
    execution_time: float = Field(..., description="Duration in seconds")
    language: str
    error_type: Optional[str] = None


class BaseExecutor(ABC):
    """Abstract base class for language code executors."""

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    @property
    @abstractmethod
    def language(self) -> str:
        """Name of the programming language supported by this executor."""
        pass

    @abstractmethod
    def execute(self, code: str, timeout: Optional[float] = None) -> ExecutionResult:
        """
        Execute code string and return structured ExecutionResult.
        Subclasses should NOT invoke a shell (e.g. shell=True in subprocess)
        to prevent arbitrary shell injection.
        """
        pass
