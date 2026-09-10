import re
from typing import Optional
from app.execution.base import ExecutionResult
from app.analysis.models import ErrorObservation

# Supported Python errors
PYTHON_KNOWN_ERRORS = {
    "SyntaxError",
    "NameError",
    "TypeError",
    "IndexError",
    "KeyError",
    "ValueError",
    "ZeroDivisionError",
    "AttributeError",
    "ImportError",
    "ModuleNotFoundError",
    "IndentationError",
    "TabError",
    "AssertionError",
    "TimeoutError",
    "RecursionError",
    "RuntimeError",
}

# Supported JavaScript errors
JS_KNOWN_ERRORS = {
    "SyntaxError",
    "TypeError",
    "ReferenceError",
    "RangeError",
    "URIError",
    "EvalError",
    "TimeoutError",
    "Error",
}


class ErrorParser:
    """Parses raw execution results into normalized ErrorObservation models."""

    @classmethod
    def parse(cls, result: ExecutionResult) -> ErrorObservation:
        """Parse ExecutionResult safely without throwing exceptions."""
        try:
            lang = (result.language or "").strip().lower()
            if lang in ("python", "py"):
                return cls._parse_python(result)
            elif lang in ("javascript", "js", "node"):
                return cls._parse_javascript(result)
            elif lang == "java":
                return cls._parse_java(result)
            else:
                return cls._parse_fallback(result)
        except Exception:
            # Guarantee that the parser never crashes
            return cls._parse_fallback(result)

    @classmethod
    def _parse_python(cls, result: ExecutionResult) -> ErrorObservation:
        stderr = result.stderr or ""
        stdout = result.stdout or ""

        # Pattern for Python exception line: e.g., "NameError: name 'x' is not defined"
        # Handles single and multi-line exception messages
        error_match = re.search(
            r"^([A-Z][a-zA-Z0-9_]*(?:Error|Exception|Warning|Interrupt))(?::\s*(.*))?$",
            stderr,
            re.MULTILINE,
        )

        error_type = "UnknownError"
        error_message = ""

        if error_match:
            found_type = error_match.group(1).strip()
            error_message = (error_match.group(2) or "").strip()
            # If known or recognized exception
            if found_type in PYTHON_KNOWN_ERRORS or found_type.endswith("Error"):
                error_type = found_type
            else:
                error_type = found_type

        # Extract file and line from traceback: File "...", line 12
        # Usually the last File "...", line X in the traceback is the error origin
        file_matches = list(re.finditer(r'File "([^"]+)", line (\d+)(?:,\s*in (.+))?', stderr))
        file_name = None
        line_number = None
        if file_matches:
            last_file_match = file_matches[-1]
            file_name = last_file_match.group(1)
            line_number = int(last_file_match.group(2))

        # Check for column indicator (^ or ~~~^) in Python 3.11+
        column_number = None
        col_match = re.search(r"(\s+)\^", stderr)
        if col_match:
            column_number = len(col_match.group(1))

        # If error_type still unknown, check if result.error_type is provided
        if error_type == "UnknownError" and result.error_type:
            error_type = result.error_type
        if not error_message and stderr.strip():
            # Fallback to the last non-empty line of stderr
            lines = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
            if lines:
                error_message = lines[-1]

        return ErrorObservation(
            language="python",
            error_type=error_type,
            error_message=error_message,
            file_name=file_name,
            line_number=line_number,
            column_number=column_number,
            stack_trace=stderr.strip(),
            stdout=stdout,
            stderr=stderr,
        )

    @classmethod
    def _parse_javascript(cls, result: ExecutionResult) -> ErrorObservation:
        stderr = result.stderr or ""
        stdout = result.stdout or ""

        # Node.js stack trace usually begins or contains:
        # /path/to/solution.js:5
        #     return items.reduce(...) + taxRate;
        #                                ^
        # ReferenceError: taxRate is not defined
        #     at calculateTotal (/path/to/solution.js:5:34)
        file_name = None
        line_number = None
        column_number = None

        # 1. Look for script header: /path/to/file.js:12 or /path/to/file.js:12:34
        file_line_match = re.search(r"^([a-zA-Z]:[\\/][^\n\r:]+|[^\s\n\r:]+\.js):(\d+)(?::(\d+))?", stderr, re.MULTILINE)
        if file_line_match:
            file_name = file_line_match.group(1)
            line_number = int(file_line_match.group(2))
            if file_line_match.group(3):
                column_number = int(file_line_match.group(3))

        # 2. Extract column pointer if available: e.g. "       ^"
        if column_number is None:
            col_match = re.search(r"(\s+)\^", stderr)
            if col_match:
                column_number = len(col_match.group(1))

        # 3. Extract error type and message: "TypeError: Cannot read properties of undefined..."
        error_match = re.search(r"^([A-Z][a-zA-Z0-9_]*Error):\s*(.+)$", stderr, re.MULTILINE)
        error_type = "UnknownError"
        error_message = ""

        if error_match:
            found_type = error_match.group(1).strip()
            error_type = found_type if (found_type in JS_KNOWN_ERRORS or found_type.endswith("Error")) else found_type
            error_message = error_match.group(2).strip()
        else:
            # Fallback check from stack line: "at ..."
            lines = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
            if lines:
                error_message = lines[0]

        if error_type == "UnknownError" and result.error_type:
            error_type = result.error_type

        return ErrorObservation(
            language="javascript",
            error_type=error_type,
            error_message=error_message,
            file_name=file_name,
            line_number=line_number,
            column_number=column_number,
            stack_trace=stderr.strip(),
            stdout=stdout,
            stderr=stderr,
        )

    @classmethod
    def _parse_java(cls, result: ExecutionResult) -> ErrorObservation:
        stderr = result.stderr or ""
        stdout = result.stdout or ""

        file_name = None
        line_number = None
        column_number = None
        error_type = "UnknownError"
        error_message = ""

        # Case 1: javac compilation error
        # e.g.: Calculator.java:4: error: ';' expected
        #       int number = "not_an_int"
        #                                ^
        compile_match = re.search(
            r"^([a-zA-Z]:[\\/][^\n\r:]+|[^\s\n\r:]+\.java):(\d+):\s*error:\s*(.+)$",
            stderr,
            re.MULTILINE,
        )
        if compile_match:
            file_name = compile_match.group(1)
            line_number = int(compile_match.group(2))
            error_type = "CompilationError"
            error_message = compile_match.group(3).strip()

            col_match = re.search(r"(\s+)\^", stderr)
            if col_match:
                column_number = len(col_match.group(1))

        # Case 2: java runtime exception
        # e.g.: Exception in thread "main" java.lang.NullPointerException: Cannot invoke ...
        #           at Calculator.main(Calculator.java:6)
        if not compile_match:
            runtime_match = re.search(
                r'Exception in thread "[^"]*"\s+(?:[a-zA-Z0-9_.]+\.)?([A-Za-z0-9_]*(?:Exception|Error))(?::\s*(.*))?',
                stderr,
            )
            if runtime_match:
                error_type = runtime_match.group(1).strip()
                error_message = (runtime_match.group(2) or "").strip()

                # Find line and class/file in stack trace: at ClassName.method(FileName.java:12)
                trace_match = re.search(r"at\s+[^\(]+\(([a-zA-Z0-9_]+\.java):(\d+)\)", stderr)
                if trace_match:
                    file_name = trace_match.group(1)
                    line_number = int(trace_match.group(2))

        if error_type == "UnknownError":
            if result.error_type:
                error_type = result.error_type
            elif stderr.strip():
                lines = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
                error_message = lines[-1] if lines else ""

        return ErrorObservation(
            language="java",
            error_type=error_type,
            error_message=error_message,
            file_name=file_name,
            line_number=line_number,
            column_number=column_number,
            stack_trace=stderr.strip(),
            stdout=stdout,
            stderr=stderr,
        )

    @classmethod
    def _parse_fallback(cls, result: ExecutionResult) -> ErrorObservation:
        stderr = result.stderr or ""
        stdout = result.stdout or ""
        lines = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
        error_message = lines[-1] if lines else (lines[0] if lines else "")

        return ErrorObservation(
            language=(result.language or "unknown").strip().lower(),
            error_type=result.error_type or "UnknownError",
            error_message=error_message,
            file_name=None,
            line_number=None,
            column_number=None,
            stack_trace=stderr.strip(),
            stdout=stdout,
            stderr=stderr,
        )
