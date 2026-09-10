import ast
import re
from typing import NamedTuple


class LanguageDetection(NamedTuple):
    language: str
    confidence: float


def detect_language(source_code: str) -> LanguageDetection:
    """Detect one of the supported languages without executing the source."""
    source = source_code.strip()

    try:
        ast.parse(source)
        if re.search(r"(^|\n)\s*(def|class|import|from)\s+", source) or re.search(
            r"\b(print|elif|None|True|False|raise|lambda)\b", source
        ):
            return LanguageDetection("python", 0.98)
    except SyntaxError:
        pass

    if re.search(r"\b(const|let|var)\s+\w+\s*=|console\.log\s*\(|=>", source):
        return LanguageDetection("javascript", 0.95)

    if re.search(
        r"\b(public|private|protected)?\s*(class|interface|static\s+void)\b|System\.out\.|package\s+[\w.]+;",
        source,
    ):
        return LanguageDetection("java", 0.95)

    return LanguageDetection("unknown", 0.0)