from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class TestFailureDetail(BaseModel):
    """Detailed information about an individual test failure."""
    __test__ = False
    test_name: str = Field(..., description="Name or identifier of the failing test")
    message: str = Field(..., description="Failure message or assertion error")
    expected: Optional[str] = None
    actual: Optional[str] = None


class ValidationResult(BaseModel):
    """Structured result from running automated tests on repaired code."""
    passed: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    stdout: str = ""
    stderr: str = ""
    failure_details: List[TestFailureDetail] = Field(default_factory=list)


class BaseValidator(ABC):
    """Abstract base class for language-specific test validators."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout

    @property
    @abstractmethod
    def language(self) -> str:
        """Supported programming language."""
        pass

    @abstractmethod
    def validate(
        self,
        code: str,
        test_code: str,
        timeout: Optional[float] = None,
    ) -> ValidationResult:
        """
        Execute the test suite against the provided source code.
        Returns a structured ValidationResult.
        """
        pass
