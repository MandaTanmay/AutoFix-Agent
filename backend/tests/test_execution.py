import pytest
import shutil
from app.execution.manager import ExecutionManager
from app.execution.python_executor import PythonExecutor
from app.execution.samples import (
    PYTHON_SUCCESS,
    PYTHON_NAME_ERROR,
    JAVASCRIPT_ERROR,
    JAVA_COMPILATION_ERROR,
)


@pytest.fixture
def manager():
    return ExecutionManager(default_timeout=3.0)


@pytest.fixture
def python_executor():
    return PythonExecutor(timeout=3.0)


def test_python_executor_success(python_executor):
    result = python_executor.execute(PYTHON_SUCCESS)
    assert result.success is True
    assert result.exit_code == 0
    assert "Result: 30" in result.stdout.strip()
    assert result.error_type is None
    assert result.execution_time > 0


def test_python_executor_name_error(python_executor):
    result = python_executor.execute(PYTHON_NAME_ERROR)
    assert result.success is False
    assert result.exit_code != 0
    assert "NameError" in result.stderr
    assert result.error_type == "NameError"


def test_python_executor_timeout():
    slow_code = """
import time
time.sleep(2)
"""
    executor = PythonExecutor(timeout=0.5)
    result = executor.execute(slow_code)
    assert result.success is False
    assert result.exit_code == -1
    assert result.error_type == "TimeoutError"
    assert "timed out" in result.stderr


def test_execution_manager_routing(manager):
    result = manager.execute("python", PYTHON_SUCCESS)
    assert result.success is True
    assert "Result: 30" in result.stdout

    # Test alias
    result_alias = manager.execute("py", PYTHON_SUCCESS)
    assert result_alias.success is True


def test_execution_manager_unsupported_language(manager):
    with pytest.raises(ValueError, match="Unsupported language 'ruby'"):
        manager.execute("ruby", "puts 'hello'")


def test_javascript_error_if_node_available(manager):
    if not shutil.which("node"):
        pytest.skip("Node.js is not installed in the environment.")
    result = manager.execute("javascript", JAVASCRIPT_ERROR)
    assert result.success is False
    assert result.exit_code != 0
    assert result.error_type == "ReferenceError"


def test_java_compilation_error_if_javac_available(manager):
    if not shutil.which("javac") or not shutil.which("java"):
        pytest.skip("Java SDK is not installed in the environment.")
    result = manager.execute("java", JAVA_COMPILATION_ERROR)
    assert result.success is False
    assert result.exit_code != 0
    assert result.error_type == "CompilationError"
