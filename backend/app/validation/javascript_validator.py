import json
import os
import shutil
import subprocess
import tempfile
from typing import List, Optional
from app.validation.base import BaseValidator, TestFailureDetail, ValidationResult

# Lightweight test runner harness injected into Node environment
NODE_TEST_HARNESS = """
const assert = require('assert');
const solution = require('./solution.js');

const results = {
    total: 0,
    passed: 0,
    failed: 0,
    failures: []
};

function test(name, fn) {
    results.total++;
    try {
        fn(solution, assert);
        results.passed++;
    } catch (err) {
        results.failed++;
        results.failures.push({
            test_name: name,
            message: err.message || String(err)
        });
    }
}

// User-provided test suite
try {
    %TEST_CODE%
} catch (suiteErr) {
    results.failed++;
    results.total++;
    results.failures.push({
        test_name: "test_suite_syntax",
        message: suiteErr.message || String(suiteErr)
    });
}

console.log("__AUTOFIX_TEST_RESULTS__" + JSON.stringify(results));
"""


class JavaScriptValidator(BaseValidator):
    """Validates JavaScript code by executing Node.js assertions."""

    @property
    def language(self) -> str:
        return "javascript"

    def validate(
        self,
        code: str,
        test_code: str,
        timeout: Optional[float] = None,
    ) -> ValidationResult:
        actual_timeout = timeout if timeout is not None else self.timeout

        node_bin = shutil.which("node")
        if not node_bin:
            return ValidationResult(
                passed=False,
                total_tests=1,
                passed_tests=0,
                failed_tests=1,
                stdout="",
                stderr="Node.js is not available in PATH.",
                failure_details=[
                    TestFailureDetail(test_name="environment", message="Node.js not installed")
                ],
            )

        with tempfile.TemporaryDirectory() as tmp_dir:
            solution_file = os.path.join(tmp_dir, "solution.js")
            with open(solution_file, "w", encoding="utf-8") as f:
                f.write(code)

            runner_code = NODE_TEST_HARNESS.replace("%TEST_CODE%", test_code)
            runner_file = os.path.join(tmp_dir, "runner.js")
            with open(runner_file, "w", encoding="utf-8") as f:
                f.write(runner_code)

            cmd = [node_bin, runner_file]

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

                stdout = proc.stdout
                stderr = proc.stderr

                marker = "__AUTOFIX_TEST_RESULTS__"
                if marker in stdout:
                    raw_json = stdout.split(marker)[-1].strip().splitlines()[0]
                    parsed = json.loads(raw_json)
                    failures = [
                        TestFailureDetail(test_name=f["test_name"], message=f["message"])
                        for f in parsed.get("failures", [])
                    ]
                    passed = parsed.get("passed", 0)
                    failed = parsed.get("failed", 0)
                    total = parsed.get("total", 0)
                    return ValidationResult(
                        passed=(proc.returncode == 0 and failed == 0 and passed > 0),
                        total_tests=total,
                        passed_tests=passed,
                        failed_tests=failed,
                        stdout=stdout,
                        stderr=stderr,
                        failure_details=failures,
                    )

                # If harness didn't finish normally
                return ValidationResult(
                    passed=False,
                    total_tests=1,
                    passed_tests=0,
                    failed_tests=1,
                    stdout=stdout,
                    stderr=stderr,
                    failure_details=[
                        TestFailureDetail(
                            test_name="execution_failure",
                            message=stderr.strip() or "Node.js execution terminated abnormally",
                        )
                    ],
                )

            except subprocess.TimeoutExpired as exc:
                return ValidationResult(
                    passed=False,
                    total_tests=1,
                    passed_tests=0,
                    failed_tests=1,
                    stdout="",
                    stderr=f"Test validation timed out after {actual_timeout}s",
                    failure_details=[
                        TestFailureDetail(
                            test_name="timeout",
                            message=f"Test run exceeded {actual_timeout}s timeout.",
                        )
                    ],
                )
