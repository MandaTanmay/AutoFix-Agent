import os
import re
import shutil
import subprocess
import tempfile
from typing import List, Optional
from app.validation.base import BaseValidator, TestFailureDetail, ValidationResult


class JavaValidator(BaseValidator):
    """Validates Java code by compiling and executing a companion TestRunner class."""

    @property
    def language(self) -> str:
        return "java"

    def _extract_main_class(self, code: str) -> str:
        match = re.search(r"public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        if match:
            return match.group(1)
        fallback = re.search(r"class\s+([A-Za-z_][A-Za-z0-9_]*)", code)
        if fallback:
            return fallback.group(1)
        return "Solution"

    def validate(
        self,
        code: str,
        test_code: str,
        timeout: Optional[float] = None,
    ) -> ValidationResult:
        actual_timeout = timeout if timeout is not None else self.timeout

        javac_bin = shutil.which("javac")
        java_bin = shutil.which("java")
        if not javac_bin or not java_bin:
            return ValidationResult(
                passed=False,
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                stdout="",
                stderr="Java SDK ('javac'/'java') is not installed or not in PATH.",
                failure_details=[
                    TestFailureDetail(test_name="environment", message="Java SDK missing")
                ],
            )

        solution_class = self._extract_main_class(code)
        test_class = self._extract_main_class(test_code)

        with tempfile.TemporaryDirectory() as tmp_dir:
            sol_path = os.path.join(tmp_dir, f"{solution_class}.java")
            with open(sol_path, "w", encoding="utf-8") as f:
                f.write(code)

            test_path = os.path.join(tmp_dir, f"{test_class}.java")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)

            # Compile both
            compile_proc = subprocess.run(
                [javac_bin, sol_path, test_path],
                cwd=tmp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=actual_timeout,
                shell=False,
            )

            if compile_proc.returncode != 0:
                return ValidationResult(
                    passed=False,
                    total_tests=1,
                    passed_tests=0,
                    failed_tests=1,
                    stdout=compile_proc.stdout,
                    stderr=compile_proc.stderr,
                    failure_details=[
                        TestFailureDetail(
                            test_name="compilation",
                            message=compile_proc.stderr.strip() or "Java compilation failed",
                        )
                    ],
                )

            # Run test runner with assertion enabled (-ea)
            run_proc = subprocess.run(
                [java_bin, "-ea", "-cp", tmp_dir, test_class],
                cwd=tmp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=actual_timeout,
                shell=False,
            )

            is_passed = (run_proc.returncode == 0)
            failed_count = 0 if is_passed else 1
            passed_count = 1 if is_passed else 0

            failure_details = []
            if not is_passed:
                failure_details.append(
                    TestFailureDetail(
                        test_name=test_class,
                        message=run_proc.stderr.strip() or run_proc.stdout.strip() or "AssertionError",
                    )
                )

            return ValidationResult(
                passed=is_passed,
                total_tests=1,
                passed_tests=passed_count,
                failed_tests=failed_count,
                stdout=run_proc.stdout,
                stderr=run_proc.stderr,
                failure_details=failure_details,
            )
