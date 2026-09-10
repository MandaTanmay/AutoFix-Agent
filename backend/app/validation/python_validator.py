import os
import re
import subprocess
import sys
import tempfile
from typing import List, Optional
from app.validation.base import BaseValidator, TestFailureDetail, ValidationResult


class PythonValidator(BaseValidator):
    """Validates Python code by executing a pytest test suite via subprocess."""

    @property
    def language(self) -> str:
        return "python"

    def _parse_pytest_output(self, stdout: str, stderr: str, returncode: int) -> ValidationResult:
        """Extract test counts and failed test details from pytest terminal output."""
        # e.g.: "==== 2 passed in 0.12s ====" or "==== 1 failed, 2 passed in 0.20s ===="
        passed = 0
        failed = 0

        passed_match = re.search(r"(\d+)\s+passed", stdout)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+)\s+failed", stdout)
        if failed_match:
            failed = int(failed_match.group(1))

        # Check for errors in collection or execution
        error_match = re.search(r"(\d+)\s+error", stdout)
        if error_match:
            failed += int(error_match.group(1))

        total = passed + failed

        failure_details: List[TestFailureDetail] = []
        # Look for FAILED test markers: FAILED test_solution.py::test_func - AssertionError: ...
        fail_lines = re.findall(r"FAILED\s+([^\s]+)\s*-\s*(.*)", stdout)
        for t_name, msg in fail_lines:
            failure_details.append(
                TestFailureDetail(test_name=t_name.strip(), message=msg.strip())
            )

        # If pytest failed before running tests (syntax error, collection error)
        if returncode != 0 and total == 0:
            failed = 1
            total = 1
            err_msg = stderr.strip() or stdout.strip() or "Pytest collection or runtime error"
            failure_details.append(
                TestFailureDetail(test_name="collection_or_syntax_error", message=err_msg)
            )

        is_passed = (returncode == 0 and failed == 0 and passed > 0)

        return ValidationResult(
            passed=is_passed,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            stdout=stdout,
            stderr=stderr,
            failure_details=failure_details,
        )

    def validate(
        self,
        code: str,
        test_code: str,
        timeout: Optional[float] = None,
    ) -> ValidationResult:
        actual_timeout = timeout if timeout is not None else self.timeout

        tmp_dir = tempfile.mkdtemp(prefix="autofix_test_")
        try:
            # Write solution code
            solution_file = os.path.join(tmp_dir, "solution.py")
            with open(solution_file, "w", encoding="utf-8") as f:
                f.write(code)

            # Write test suite code
            test_file = os.path.join(tmp_dir, "test_solution.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write(test_code)

            # Controlled invocation of pytest via current python interpreter, shell=False
            # Disable pytest cache creation and third-party global hooks (like deepeval, langsmith) for speed & isolation
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                test_file,
                "-q",
                "--tb=short",
                "-p",
                "no:cacheprovider",
                "-p",
                "no:deepeval",
                "-p",
                "no:langsmith",
                "-p",
                "no:asyncio",
                "-p",
                "no:xdist",
                "-o",
                "pythonpath=" + tmp_dir,
            ]


            try:
                proc = subprocess.run(
                    cmd,
                    cwd=tmp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=actual_timeout,
                    shell=False,
                )
                return self._parse_pytest_output(proc.stdout, proc.stderr, proc.returncode)

            except subprocess.TimeoutExpired as exc:
                stdout_str = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout.decode("utf-8") if exc.stdout else "")
                stderr_str = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr.decode("utf-8") if exc.stderr else "")
                return ValidationResult(
                    passed=False,
                    total_tests=1,
                    passed_tests=0,
                    failed_tests=1,
                    stdout=stdout_str,
                    stderr=f"Test validation timed out after {actual_timeout}s\n" + stderr_str,
                    failure_details=[
                        TestFailureDetail(
                            test_name="timeout",
                            message=f"Test suite execution exceeded {actual_timeout}s timeout limit.",
                        )
                    ],
                )
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)


