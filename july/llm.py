from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from july.config import LLMSettings

ALLOWED_INTENTS = {
    "repository_onboarding",
    "resource_watch_later",
    "resource_apply_to_project",
    "memory_query",
    "repository_audit_with_memory",
    "external_analysis_import",
    "architecture_collaboration",
    "general_note",
}

ALLOWED_DOMAINS = {
    "Inteligencia Artificial",
    "Programacion",
    "Desarrollo Personal",
    "Espiritualidad",
}


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM provider cannot fulfill a request."""


class LLMProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def enrich_capture(self, raw_input: str, plan: dict) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def draft_memory(self, raw_input: str, memory_item: dict) -> dict | None:
        raise NotImplementedError


class NoOpProvider(LLMProvider):
    def is_available(self) -> bool:
        return False

    def enrich_capture(self, raw_input: str, plan: dict) -> dict | None:
        return None

    def draft_memory(self, raw_input: str, memory_item: dict) -> dict | None:
        return None


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    def is_available(self) -> bool:
        return bool(self.settings.api_key and self.settings.base_url and self.settings.model)

    def enrich_capture(self, raw_input: str, plan: dict) -> dict | None:
        prompt = (
            "Eres un clasificador para July. Debes devolver solo JSON valido.\n"
            "Corrige o confirma la clasificacion heuristica de un input libre.\n"
            "Campos permitidos: intent, confidence, status, normalized_summary, clarification_question, domain, project_key.\n"
            f"Intentos validos: {sorted(ALLOWED_INTENTS)}.\n"
            f"Dominios validos: {sorted(ALLOWED_DOMAINS)}.\n"
            "status solo puede ser 'ready' o 'needs_clarification'.\n"
            "Si no necesitas cambiar un campo, puedes devolver el mismo valor.\n"
            "Si falta contexto, usa status='needs_clarification' y redacta una pregunta breve.\n\n"
            f"INPUT:\n{redact_sensitive_text(raw_input)}\n\n"
            f"CLASIFICACION_HEURISTICA:\n{json.dumps(plan['classification'], ensure_ascii=True)}"
        )
        content = self._chat_json(prompt)
        return validate_capture_overrides(content)

    def draft_memory(self, raw_input: str, memory_item: dict) -> dict | None:
        prompt = (
            "Eres un asistente que destila memoria para July. Devuelve solo JSON valido.\n"
            "Debes mejorar title, summary y distilled_knowledge de una memoria candidata.\n"
            "El resultado debe ser concreto, reutilizable y breve.\n"
            "Campos permitidos: title, summary, distilled_knowledge.\n\n"
            f"INPUT_ORIGINAL:\n{redact_sensitive_text(raw_input)}\n\n"
            f"MEMORIA_ACTUAL:\n{json.dumps(memory_item, ensure_ascii=True)}"
        )
        content = self._chat_json(prompt)
        return validate_memory_draft(content)

    def _chat_json(self, prompt: str) -> dict:
        if not self.is_available():
            raise LLMProviderError("LLM provider is not configured")

        payload = {
            "model": self.settings.model,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": "Responde exclusivamente con un objeto JSON valido.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=self.settings.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.settings.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMProviderError(f"LLM HTTP error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMProviderError(f"LLM connection error: {exc.reason}") from exc

        try:
            parsed = json.loads(response_body)
            content = parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise LLMProviderError("LLM response was not a valid chat completion payload") from exc

        return parse_json_from_text(content)


def create_llm_provider(settings: LLMSettings) -> LLMProvider:
    if settings.provider in {"none", ""}:
        return NoOpProvider()
    if settings.provider in {"openai_compatible", "zai"}:
        return OpenAICompatibleProvider(settings)
    return NoOpProvider()


def redact_sensitive_text(text: str) -> str:
    redacted = re.sub(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)
    redacted = re.sub(r"\b(sk|sb|rk)_[A-Za-z0-9._-]+\b", "[REDACTED_TOKEN]", redacted)
    return redacted


def parse_json_from_text(content: str) -> dict:
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return json.loads(stripped)

    match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
    if not match:
        raise LLMProviderError("LLM did not return a JSON object")
    return json.loads(match.group(0))


def validate_capture_overrides(data: dict) -> dict:
    overrides: dict[str, object] = {}
    intent = data.get("intent")
    if intent in ALLOWED_INTENTS:
        overrides["intent"] = intent

    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        confidence = None
    if confidence is not None:
        overrides["confidence"] = max(0.0, min(confidence, 0.99))

    status = data.get("status")
    if status in {"ready", "needs_clarification"}:
        overrides["status"] = status

    normalized_summary = data.get("normalized_summary")
    if isinstance(normalized_summary, str) and normalized_summary.strip():
        overrides["normalized_summary"] = normalized_summary.strip()

    clarification_question = data.get("clarification_question")
    if clarification_question is None or isinstance(clarification_question, str):
        overrides["clarification_question"] = clarification_question.strip() if isinstance(clarification_question, str) else None

    domain = data.get("domain")
    if domain in ALLOWED_DOMAINS:
        overrides["domain"] = domain

    project_key = data.get("project_key")
    if project_key is None or (isinstance(project_key, str) and project_key.strip()):
        overrides["project_key"] = project_key.strip() if isinstance(project_key, str) else None

    return overrides


def validate_memory_draft(data: dict) -> dict:
    overrides: dict[str, str] = {}
    for key in ("title", "summary", "distilled_knowledge"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            overrides[key] = value.strip()
    return overrides
