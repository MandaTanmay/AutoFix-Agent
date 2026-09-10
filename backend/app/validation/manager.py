from typing import Dict, Optional
from app.validation.base import BaseValidator, TestFailureDetail, ValidationResult
from app.validation.python_validator import PythonValidator
from app.validation.javascript_validator import JavaScriptValidator
from app.validation.java_validator import JavaValidator


class ValidationManager:
    """Coordinates language-specific test validation suites."""

    def __init__(self, default_timeout: float = 8.0):
        self.default_timeout = default_timeout
        self._validators: Dict[str, BaseValidator] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_validator("python", PythonValidator(timeout=self.default_timeout))
        self.register_validator("javascript", JavaScriptValidator(timeout=self.default_timeout))
        self.register_validator("java", JavaValidator(timeout=self.default_timeout))
        self._validators["py"] = self._validators["python"]
        self._validators["js"] = self._validators["javascript"]

    def register_validator(self, language: str, validator: BaseValidator) -> None:
        self._validators[language.strip().lower()] = validator

    def get_validator(self, language: str) -> BaseValidator:
        key = language.strip().lower()
        if key not in self._validators:
            raise ValueError(f"No test validator registered for language '{language}'.")
        return self._validators[key]

    def validate(
        self, language: str, code: str, test_code: str, timeout: Optional[float] = None
    ) -> ValidationResult:
        validator = self.get_validator(language)
        return validator.validate(code=code, test_code=test_code, timeout=timeout)
