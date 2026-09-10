import os
import re
import shutil
import tempfile
import subprocess
import time
from typing import Optional
from app.execution.base import BaseExecutor, ExecutionResult
from app.execution.python_executor import _check_path_traversal, _scratch_dir


class JavaScriptExecutor(BaseExecutor):
    """Executes JavaScript code via Node.js without a shell."""

    @property
    def language(self) -> str:
        return "javascript"

    def _extract_error_type(self, stderr: str) -> Optional[str]:
        """Extract JavaScript error types like TypeError, ReferenceError, SyntaxError."""
        matches = re.findall(r"([A-Z][a-zA-Z0-9_]*Error):", stderr)
        if matches:
            return matches[0]
        return None

    def execute(self, code: str, timeout: Optional[float] = None) -> ExecutionResult:
        actual_timeout = timeout if timeout is not None else self.timeout
        start_time = time.perf_counter()

        # Security: reject code with obvious path traversal patterns
        try:
            _check_path_traversal(code)
        except ValueError as exc:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
                execution_time=0.0,
                language=self.language,
                error_type="SecurityError",
            )

        node_bin = shutil.which("node")
        if not node_bin:
            duration = time.perf_counter() - start_time
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Node.js runtime ('node') is not installed or not in PATH.",
                exit_code=-1,
                execution_time=round(duration, 4),
                language=self.language,
                error_type="EnvironmentError",
            )

        with tempfile.TemporaryDirectory(dir=_scratch_dir()) as tmp_dir:
            script_path = os.path.join(tmp_dir, "solution.js")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            # Direct controlled execution without shell
            cmd = [node_bin, script_path]

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
