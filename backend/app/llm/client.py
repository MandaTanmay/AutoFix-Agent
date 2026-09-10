import os
from typing import List, Optional
from dotenv import load_dotenv

from app.analysis.models import ErrorObservation
from app.llm.models import RepairDiagnosis, RepairAttempt
from app.llm.prompts import create_diagnosis_prompt, format_previous_attempts

load_dotenv()


class LLMDiagnosisClient:
    """
    Client for LLM-based code failure diagnosis using LangChain, Groq,
    and structured Pydantic output.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0,
        chat_model=None,
    ):
        """
        Initialize diagnosis client.
        Allows passing `chat_model` directly to support mocking/testing
        without requiring a live GROQ_API_KEY.
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model_name = model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.temperature = temperature
        self._custom_chat_model = chat_model

    def _get_model(self):
        """Instantiate ChatGroq model with structured output."""
        if self._custom_chat_model is not None:
            # If custom mock model provides with_structured_output
            if hasattr(self._custom_chat_model, "with_structured_output"):
                return self._custom_chat_model.with_structured_output(RepairDiagnosis)
            return self._custom_chat_model

        if not self.api_key or self.api_key.strip() == "your_groq_api_key_here":
            raise ValueError(
                "GROQ_API_KEY is not set or is using the placeholder value. "
                "Please configure GROQ_API_KEY in your .env file."
            )

        # Lazy import so tests without groq credentials don't fail at import time
        from langchain_groq import ChatGroq

        base_llm = ChatGroq(
            groq_api_key=self.api_key,
            model=self.model_name,
            temperature=self.temperature,
        )
        return base_llm.with_structured_output(RepairDiagnosis)

    def diagnose(
        self,
        language: str,
        source_code: str,
        observation: ErrorObservation,
        previous_attempts: Optional[List[RepairAttempt]] = None,
    ) -> RepairDiagnosis:
        """
        Diagnose an observed error and propose a repair strategy.
        Outputs a strictly typed RepairDiagnosis model.
        """
        prompt_template = create_diagnosis_prompt()
        previous_attempts_text = format_previous_attempts(previous_attempts)

        chain = prompt_template | self._get_model()

        result = chain.invoke(
            {
                "language": language,
                "source_code": source_code,
                "error_type": observation.error_type,
                "error_message": observation.error_message,
                "file_name": observation.file_name or "unknown",
                "line_number": observation.line_number or "unknown",
                "column_number": observation.column_number or "unknown",
                "stack_trace": observation.stack_trace or "",
                "stdout": observation.stdout or "",
                "stderr": observation.stderr or "",
                "previous_attempts_text": previous_attempts_text,
            }
        )

        # If model returned a raw dict instead of instance
        if isinstance(result, dict):
            return RepairDiagnosis(**result)
        return result
