from __future__ import annotations

import re

from app.application.ports import TextAnalyzer


class SimpleTextAnalyzer(TextAnalyzer):
    POSITIVE = {"bueno", "genial", "excelente", "love", "great", "amazing"}
    NEGATIVE = {"malo", "terrible", "horrible", "hate", "awful", "bad"}

    def analyze(self, text: str) -> tuple[str | None, str]:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        if not normalized:
            return None, "neutral"

        tokens = set(normalized.split(" "))
        if tokens & self.POSITIVE:
            sentiment = "positive"
        elif tokens & self.NEGATIVE:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        # Detección muy simple (opcional): si hay caracteres no ASCII, asumimos 'es'
        language: str | None = "es" if any(ord(c) > 127 for c in normalized) else None
        return language, sentiment
