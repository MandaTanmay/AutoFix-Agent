import pytest
from app.execution.base import ExecutionResult
from app.analysis.error_parser import ErrorParser


# ---------------------------------------------------------------------------
# Python Test Cases
# ---------------------------------------------------------------------------

PYTHON_SYNTAX_ERROR_STDERR = """  File "solution.py", line 3
    def foo(
           ^
SyntaxError: '(' was never closed
"""

PYTHON_NAME_ERROR_STDERR = """Traceback (most recent call last):
  File "/workspace/app/solution.py", line 7, in <module>
    print(greet("World"))
  File "/workspace/app/solution.py", line 4, in greet
    return f"Hello, {formatted_name}"
                     ^^^^^^^^^^^^^^
NameError: name 'formatted_name' is not defined
"""

PYTHON_TYPE_ERROR_STDERR = """Traceback (most recent call last):
  File "solution.py", line 2, in <module>
    result = "age: " + 25
TypeError: can only concatenate str (not "int") to str
"""

PYTHON_INDEX_ERROR_STDERR = """Traceback (most recent call last):
  File "solution.py", line 4, in <module>
    item = [1, 2, 3][10]
IndexError: list index out of range
"""

PYTHON_KEY_ERROR_STDERR = """Traceback (most recent call last):
  File "solution.py", line 2, in <module>
    val = {"a": 1}["missing"]
KeyError: 'missing'
"""

PYTHON_VALUE_ERROR_STDERR = """Traceback (most recent call last):
  File "solution.py", line 2, in <module>
    num = int("abc")
ValueError: invalid literal for int() with base 10: 'abc'
"""

PYTHON_ZERO_DIVISION_STDERR = """Traceback (most recent call last):
  File "solution.py", line 3, in <module>
    calc = 10 / 0
ZeroDivisionError: division by zero
"""

PYTHON_ATTRIBUTE_ERROR_STDERR = """Traceback (most recent call last):
  File "solution.py", line 3, in <module>
    "hello".non_existing_attr()
AttributeError: 'str' object has no attribute 'non_existing_attr'
"""

PYTHON_IMPORT_ERROR_STDERR = """Traceback (most recent call last):
  File "solution.py", line 1, in <module>
    import non_existent_module
ModuleNotFoundError: No module named 'non_existent_module'
"""


def test_parse_python_syntax_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_SYNTAX_ERROR_STDERR,
        exit_code=1,
        execution_time=0.05,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.language == "python"
    assert obs.error_type == "SyntaxError"
    assert "was never closed" in obs.error_message
    assert obs.line_number == 3
    assert obs.file_name == "solution.py"


def test_parse_python_name_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_NAME_ERROR_STDERR,
        exit_code=1,
        execution_time=0.08,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "NameError"
    assert "formatted_name" in obs.error_message
    assert obs.line_number == 4
    assert obs.file_name == "/workspace/app/solution.py"


def test_parse_python_type_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_TYPE_ERROR_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "TypeError"
    assert "can only concatenate str" in obs.error_message
    assert obs.line_number == 2


def test_parse_python_index_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_INDEX_ERROR_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "IndexError"
    assert "list index out of range" in obs.error_message


def test_parse_python_key_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_KEY_ERROR_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "KeyError"
    assert "'missing'" in obs.error_message


def test_parse_python_value_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_VALUE_ERROR_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "ValueError"
    assert "invalid literal" in obs.error_message


def test_parse_python_zero_division():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_ZERO_DIVISION_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "ZeroDivisionError"
    assert "division by zero" in obs.error_message


def test_parse_python_attribute_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_ATTRIBUTE_ERROR_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "AttributeError"
    assert "has no attribute" in obs.error_message


def test_parse_python_import_error():
    res = ExecutionResult(
        success=False,
        stderr=PYTHON_IMPORT_ERROR_STDERR,
        exit_code=1,
        execution_time=0.02,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "ModuleNotFoundError"
    assert "No module named" in obs.error_message


# ---------------------------------------------------------------------------
# JavaScript Test Cases
# ---------------------------------------------------------------------------

JS_REFERENCE_ERROR_STDERR = """/tmp/runner/solution.js:5
    return items.reduce((acc, curr) => acc + curr.price, 0) + taxRate;
                                                              ^
ReferenceError: taxRate is not defined
    at calculateTotal (/tmp/runner/solution.js:5:63)
    at Object.<anonymous> (/tmp/runner/solution.js:8:1)
"""

JS_TYPE_ERROR_STDERR = """/tmp/runner/solution.js:2
    const name = obj.user.name;
                          ^
TypeError: Cannot read properties of undefined (reading 'name')
    at /tmp/runner/solution.js:2:27
"""

JS_SYNTAX_ERROR_STDERR = """/tmp/runner/solution.js:2
    const total = 100 + ;
                        ^
SyntaxError: Unexpected token ';'
    at compileSource (node:vm:360:9)
"""


def test_parse_javascript_reference_error():
    res = ExecutionResult(
        success=False,
        stderr=JS_REFERENCE_ERROR_STDERR,
        exit_code=1,
        execution_time=0.04,
        language="javascript",
    )
    obs = ErrorParser.parse(res)
    assert obs.language == "javascript"
    assert obs.error_type == "ReferenceError"
    assert "taxRate is not defined" in obs.error_message
    assert obs.line_number == 5
    assert "/tmp/runner/solution.js" in (obs.file_name or "")


def test_parse_javascript_type_error():
    res = ExecutionResult(
        success=False,
        stderr=JS_TYPE_ERROR_STDERR,
        exit_code=1,
        execution_time=0.04,
        language="javascript",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "TypeError"
    assert "Cannot read properties" in obs.error_message
    assert obs.line_number == 2


def test_parse_javascript_syntax_error():
    res = ExecutionResult(
        success=False,
        stderr=JS_SYNTAX_ERROR_STDERR,
        exit_code=1,
        execution_time=0.04,
        language="javascript",
    )
    obs = ErrorParser.parse(res)
    assert obs.error_type == "SyntaxError"
    assert "Unexpected token" in obs.error_message
    assert obs.line_number == 2


# ---------------------------------------------------------------------------
# Java Test Cases
# ---------------------------------------------------------------------------

JAVA_COMPILE_ERROR_STDERR = """Calculator.java:4: error: ';' expected
        int number = "not_an_int"
                                 ^
Calculator.java:4: error: incompatible types: String cannot be converted to int
        int number = "not_an_int"
                     ^
2 errors
"""

JAVA_RUNTIME_EXCEPTION_STDERR = """Exception in thread "main" java.lang.NullPointerException: Cannot invoke "String.length()" because "str" is null
\tat Calculator.main(Calculator.java:6)
"""


def test_parse_java_compilation_error():
    res = ExecutionResult(
        success=False,
        stderr=JAVA_COMPILE_ERROR_STDERR,
        exit_code=1,
        execution_time=0.2,
        language="java",
    )
    obs = ErrorParser.parse(res)
    assert obs.language == "java"
    assert obs.error_type == "CompilationError"
    assert "expected" in obs.error_message
    assert obs.line_number == 4
    assert obs.file_name == "Calculator.java"


def test_parse_java_runtime_exception():
    res = ExecutionResult(
        success=False,
        stderr=JAVA_RUNTIME_EXCEPTION_STDERR,
        exit_code=1,
        execution_time=0.2,
        language="java",
    )
    obs = ErrorParser.parse(res)
    assert obs.language == "java"
    assert obs.error_type == "NullPointerException"
    assert 'because "str" is null' in obs.error_message
    assert obs.line_number == 6
    assert obs.file_name == "Calculator.java"


# ---------------------------------------------------------------------------
# Robustness & Unknown Error Handling
# ---------------------------------------------------------------------------

def test_parse_unknown_error_format_does_not_crash():
    res = ExecutionResult(
        success=False,
        stderr="Random crash dump without standard formatting\nFatal 0xdeadbeef",
        exit_code=139,
        execution_time=0.01,
        language="python",
    )
    obs = ErrorParser.parse(res)
    assert obs.language == "python"
    assert obs.error_type == "UnknownError"
    assert obs.stderr == "Random crash dump without standard formatting\nFatal 0xdeadbeef"
    assert "Fatal 0xdeadbeef" in obs.error_message


def test_parse_empty_stderr_does_not_crash():
    res = ExecutionResult(
        success=False,
        stderr="",
        exit_code=1,
        execution_time=0.01,
        language="c_plus_plus",
    )
    obs = ErrorParser.parse(res)
    assert obs.language == "c_plus_plus"
    assert obs.error_type == "UnknownError"
    assert obs.stderr == ""
