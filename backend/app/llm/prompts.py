import json
from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from app.analysis.models import ErrorObservation
from app.llm.models import RepairAttempt

DIAGNOSIS_SYSTEM_PROMPT = """You are an expert autonomous code debugging and repair agent.
Your role is to diagnose code execution failures based strictly on the provided source code, language, error observation, and prior repair history.

CRITICAL CONSTRAINTS:
1. You must ONLY diagnose the provided code.
2. You have NO filesystem access, NO shell access, and cannot execute commands.
3. You must produce structured output conforming strictly to the requested schema.
4. Do NOT output arbitrary markdown prose outside the structured output fields.
"""

DIAGNOSIS_USER_TEMPLATE = """Language: {language}

Source Code:
```{language}
{source_code}
```

Error Observation:
- Error Type: {error_type}
- Error Message: {error_message}
- File Name: {file_name}
- Line Number: {line_number}
- Column: {column_number}

Stack Trace / Error Details:
```
{stack_trace}
```

Stdout:
```
{stdout}
```

Stderr:
```
{stderr}
```

Previous Repair Attempts:
{previous_attempts_text}

Analyze the error, determine the root cause, estimate your confidence (0.0 to 1.0), and outline an exact repair strategy.
"""


def format_previous_attempts(attempts: Optional[List[RepairAttempt]]) -> str:
    """Format previous repair attempts into readable text for the prompt."""
    if not attempts:
        return "None. This is the first diagnosis attempt."

    formatted = []
    for att in attempts:
        formatted.append(
            f"--- Attempt #{att.iteration} ---\n"
            f"Modified Code:\n{att.modified_code}\n"
            f"Failure Reason: {att.failure_reason}\n"
        )
    return "\n".join(formatted)


def create_diagnosis_prompt() -> ChatPromptTemplate:
    """Construct the LangChain ChatPromptTemplate for diagnosis."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", DIAGNOSIS_SYSTEM_PROMPT),
            ("user", DIAGNOSIS_USER_TEMPLATE),
        ]
    )
