from typing import Dict, Optional, Type
from app.execution.base import BaseExecutor, ExecutionResult, _truncate_output
from app.execution.python_executor import PythonExecutor
from app.execution.javascript_executor import JavaScriptExecutor
from app.execution.java_executor import JavaExecutor

# Strict allowlist of supported language identifiers.
# Reject anything not in this set before attempting execution.
ALLOWED_LANGUAGES: frozenset = frozenset({
    "python", "py",
    "javascript", "js",
    "java",
})


class ExecutionManager:
    """Manages language executors and coordinates code execution."""

    def __init__(self, default_timeout: float = 5.0):
        self.default_timeout = default_timeout
        self._executors: Dict[str, BaseExecutor] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in language executors."""
        self.register_executor("python", PythonExecutor(timeout=self.default_timeout))
        self.register_executor("javascript", JavaScriptExecutor(timeout=self.default_timeout))
        self.register_executor("java", JavaExecutor(timeout=self.default_timeout))
        # Common aliases
        self._executors["js"] = self._executors["javascript"]
        self._executors["py"] = self._executors["python"]

    def register_executor(self, language: str, executor: BaseExecutor) -> None:
        """Register a custom or additional language executor."""
        self._executors[language.strip().lower()] = executor

    def get_executor(self, language: str) -> BaseExecutor:
        """Retrieve executor for a given language."""
        self._validate_language(language)
        key = language.strip().lower()
        return self._executors[key]

    def _validate_language(self, language: str) -> None:
        """Raise ValueError for unknown/disallowed language identifiers."""
        key = language.strip().lower()
        if key not in ALLOWED_LANGUAGES:
            raise ValueError(
                f"Unsupported language '{language}'. "
                f"Allowed values: python, javascript, java."
            )

    def execute(self, language: str, code: str, timeout: Optional[float] = None) -> ExecutionResult:
        """Execute code using the appropriate language executor."""
        self._validate_language(language)
        executor = self.get_executor(language)
        result = executor.execute(code, timeout=timeout)
        # Truncate oversized output at the manager level to cap memory usage.
        return result.model_copy(update={
            "stdout": _truncate_output(result.stdout),
            "stderr": _truncate_output(result.stderr),
        })
