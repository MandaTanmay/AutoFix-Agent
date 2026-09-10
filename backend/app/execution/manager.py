from typing import Dict, Optional, Type
from app.execution.base import BaseExecutor, ExecutionResult
from app.execution.python_executor import PythonExecutor
from app.execution.javascript_executor import JavaScriptExecutor
from app.execution.java_executor import JavaExecutor


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
        key = language.strip().lower()
        if key not in self._executors:
            supported = list(set(self._executors.keys()))
            raise ValueError(f"Unsupported language '{language}'. Supported languages: {supported}")
        return self._executors[key]

    def execute(self, language: str, code: str, timeout: Optional[float] = None) -> ExecutionResult:
        """Execute code using the appropriate language executor."""
        executor = self.get_executor(language)
        return executor.execute(code, timeout=timeout)
