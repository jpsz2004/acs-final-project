from __future__ import annotations

import re

from app.application.ports import TextAnalyzer


class SimpleTextAnalyzer(TextAnalyzer):
    POSITIVE = {"bueno", "genial", "excelente", "love", "great", "amazing"}
    NEGATIVE = {"malo", "terrible", "horrible", "hate", "awful", "bad"}

    def analyze(self, text: str) -> tuple[str | None, str, float]:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        if not normalized:
            return None, "neutral", 0.0

        tokens = set(normalized.split(" "))
        if tokens & self.POSITIVE:
            sentiment = "positive"
            score = 1.0
        elif tokens & self.NEGATIVE:
            sentiment = "negative"
            score = -1.0
        else:
            sentiment = "neutral"
            score = 0.0

        language: str | None = "es" if any(ord(c) > 127 for c in normalized) else None
        return language, sentiment, score
