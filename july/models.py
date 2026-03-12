from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExtractedContext:
    urls: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    project_keys: list[str] = field(default_factory=list)
    domain: str = "Programacion"


@dataclass(slots=True)
class ClassificationResult:
    intent: str
    confidence: float
    status: str
    normalized_summary: str
    clarification_question: str | None = None
    domain: str = "Programacion"
    project_key: str | None = None
