from typing import Optional
from pydantic import BaseModel, Field


class ErrorObservation(BaseModel):
    """Normalized representation of an error observed during code execution."""
    language: str
    error_type: str = Field(..., description="Classification of the error, e.g., NameError, SyntaxError, CompilationError, UnknownError")
    error_message: str = Field("", description="Extracted error message / description")
    file_name: Optional[str] = Field(None, description="Name or path of the file where the error occurred")
    line_number: Optional[int] = Field(None, description="Line number of the error if detected")
    column_number: Optional[int] = Field(None, description="Column offset if detected")
    stack_trace: str = Field("", description="Full stack trace or relevant trace snippet")
    stdout: str = Field("", description="Raw standard output from the execution")
    stderr: str = Field("", description="Raw standard error from the execution")
