import os
import re
import shutil
import tempfile
import subprocess
import time
from typing import Optional
from app.execution.base import BaseExecutor, ExecutionResult


class JavaExecutor(BaseExecutor):
    """Compiles and executes Java source code via javac and java without a shell."""

    @property
    def language(self) -> str:
        return "java"

    def _extract_error_type(self, stderr: str, is_compilation: bool) -> Optional[str]:
        if is_compilation:
            return "CompilationError"
        # Check runtime exception like NullPointerException, ArrayIndexOutOfBoundsException
        matches = re.findall(r"([A-Z][a-zA-Z0-9_]*(?:Exception|Error)):", stderr)
        if matches:
            return matches[-1]
        return "RuntimeError"

    def _extract_main_class_name(self, code: str) -> str:
        """Find the public class name or fallback to standard class name."""
        match = re.search(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        if match:
            return match.group(1)
        fallback = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        if fallback:
            return fallback.group(1)
        return "Main"

    def execute(self, code: str, timeout: Optional[float] = None) -> ExecutionResult:
        actual_timeout = timeout if timeout is not None else self.timeout
        start_time = time.perf_counter()

        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")
        if not javac_bin or not java_bin:
            duration = time.perf_counter() - start_time
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Java SDK ('javac'/'java') is not installed or not in PATH.",
                exit_code=-1,
                execution_time=round(duration, 4),
                language=self.language,
                error_type="EnvironmentError",
            )

        class_name = self._extract_main_class_name(code)

        with tempfile.TemporaryDirectory() as tmp_dir:
            source_file = os.path.join(tmp_dir, f"{class_name}.java")
            with open(source_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Phase 1: Compile with javac
            compile_cmd = [javac_bin, source_file]
            try:
                compile_process = subprocess.run(
                    compile_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=actual_timeout,
                    shell=False,
                )
            except subprocess.TimeoutExpired as exc:
                duration = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Compilation timed out after {actual_timeout}s",
                    exit_code=-1,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type="TimeoutError",
                )

            if compile_process.returncode != 0:
                duration = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    stdout=compile_process.stdout,
                    stderr=compile_process.stderr,
                    exit_code=compile_process.returncode,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type=self._extract_error_type(compile_process.stderr, is_compilation=True),
                )

            # Calculate remaining timeout for execution phase
            time_spent = time.perf_counter() - start_time
            run_timeout = max(0.1, actual_timeout - time_spent)

            # Phase 2: Run with java -cp
            run_cmd = [java_bin, "-cp", tmp_dir, class_name]
            try:
                run_process = subprocess.run(
                    run_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=run_timeout,
                    shell=False,
                )
                duration = time.perf_counter() - start_time
                error_type = self._extract_error_type(run_process.stderr, is_compilation=False) if run_process.returncode != 0 else None

                return ExecutionResult(
                    success=(run_process.returncode == 0),
                    stdout=run_process.stdout,
                    stderr=run_process.stderr,
                    exit_code=run_process.returncode,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type=error_type,
                )
            except subprocess.TimeoutExpired as exc:
                duration = time.perf_counter() - start_time
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"Execution timed out after {actual_timeout}s",
                    exit_code=-1,
                    execution_time=round(duration, 4),
                    language=self.language,
                    error_type="TimeoutError",
                )
