from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextAnalysisCommand:
    job_id: str
    text_id: str
