import sys
import os
import re
import tempfile
import subprocess
import time
from typing import Optional
from app.execution.base import BaseExecutor, ExecutionResult


class PythonExecutor(BaseExecutor):
    """Executes Python code via controlled subprocess invocation without a shell."""

    @property
    def language(self) -> str:
        return "python"

    def _extract_error_type(self, stderr: str) -> Optional[str]:
        """Extract Python exception class name from stderr if present."""
        # Typically formatted as `ExceptionName: message` or `SyntaxError: ...`
        matches = re.findall(r"([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Warning|Interrupt)):", stderr)
        if matches:
            return matches[-1]
        return None

    def execute(self, code: str, timeout: Optional[float] = None) -> ExecutionResult:
        actual_timeout = timeout if timeout is not None else self.timeout
        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory() as tmp_dir:
            script_path = os.path.join(tmp_dir, "solution.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Direct controlled execution using current Python interpreter, shell=False
            cmd = [sys.executable, script_path]

            try:
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=actual_timeout,
                    shell=False,
                )
                duration = time.perf_counter() - start_time
                error_type = self._extract_error_type(process.stderr) if process.returncode != 0 else None

                return ExecutionResult(
                    success=(process.returncode == 0),
                    stdout=process.stdout,
                    stderr=process.stderr,
                    exit_code=process.returncode,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type=error_type,
                )
            except subprocess.TimeoutExpired as exc:
                duration = time.perf_counter() - start_time
                stdout_str = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8") if exc.stdout else "")
                stderr_str = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8") if exc.stderr else "")
                return ExecutionResult(
                    success=False,
                    stdout=stdout_str,
                    stderr=f"Execution timed out after {actual_timeout}s\n" + (stderr_str or ""),
                    exit_code=-1,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type="TimeoutError",
                )
            except FileNotFoundError as exc:
                duration = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Python interpreter not found: {str(exc)}",
                    exit_code=-1,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type="EnvironmentError",
                )
