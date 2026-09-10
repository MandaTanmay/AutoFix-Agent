import time
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel, Field


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

    def _measure_time(self) -> float:
        return time.perf_counter()
