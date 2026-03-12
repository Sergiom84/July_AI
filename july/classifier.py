from __future__ import annotations

import re
from pathlib import PureWindowsPath

from july.models import ClassificationResult, ExtractedContext

URL_RE = re.compile(r"https?://\S+")
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\n\r,;]+")
PROJECT_HINT_RE = re.compile(r"(?:proyecto|en)\s+([A-Z][A-Za-z0-9_-]+)")

DOMAIN_KEYWORDS = {
    "Inteligencia Artificial": (
        "ia",
        "ai",
        "llm",
        "agente",
        "agentes",
        "gpt",
        "claude",
        "codex",
        "mcp",
        "prompt",
        "gemini",
        "z.ai",
        "glm",
    ),
    "Programacion": (
        "codigo",
        "arquitectura",
        "supabase",
        "render",
        "repo",
        "repositorio",
        "proyecto",
        "python",
        "typescript",
        "bug",
        "skill",
    ),
    "Desarrollo Personal": (
        "habito",
        "productividad",
        "rutina",
        "objetivo",
        "mejora",
        "crecimiento",
    ),
    "Espiritualidad": (
        "espiritualidad",
        "meditacion",
        "ucdm",
        "curso de milagros",
        "alma",
        "oracion",
    ),
}


def extract_context(raw_input: str) -> ExtractedContext:
    urls = URL_RE.findall(raw_input)
    paths = [match.strip().rstrip(".,;") for match in WINDOWS_PATH_RE.findall(raw_input)]
    project_keys = []
    for path in paths:
        name = PureWindowsPath(path).name
        if name and name not in project_keys:
            project_keys.append(name)
    for project_hint in PROJECT_HINT_RE.findall(raw_input):
        if project_hint not in project_keys:
            project_keys.append(project_hint)
    domain = detect_domain(raw_input)
    return ExtractedContext(urls=urls, paths=paths, project_keys=project_keys, domain=domain)


def detect_domain(raw_input: str) -> str:
    lowered = raw_input.lower()
    scores: dict[str, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        scores[domain] = sum(1 for keyword in keywords if keyword in lowered)
    best_domain, best_score = max(scores.items(), key=lambda item: item[1])
    return best_domain if best_score > 0 else "Programacion"


def classify_input(raw_input: str, context: ExtractedContext) -> ClassificationResult:
    lowered = raw_input.lower()
    scores = {
        "repository_onboarding": 0.0,
        "resource_watch_later": 0.0,
        "resource_apply_to_project": 0.0,
        "memory_query": 0.0,
        "repository_audit_with_memory": 0.0,
        "external_analysis_import": 0.0,
        "architecture_collaboration": 0.0,
        "general_note": 0.2,
    }

    has_url = bool(context.urls)
    has_path = bool(context.paths)

    if has_path:
        scores["repository_onboarding"] += 0.55
    if has_url:
        scores["resource_watch_later"] += 0.35
        scores["resource_apply_to_project"] += 0.35

    if "recuerd" in lowered or "pendiente" in lowered or "ver este link" in lowered:
        scores["resource_watch_later"] += 0.45

    if "curso" in lowered or "aplicar" in lowered or "implementar" in lowered:
        scores["resource_apply_to_project"] += 0.45

    if "accede a mi memoria" in lowered or "tira de la memoria" in lowered:
        scores["memory_query"] += 0.6

    if "skill" in lowered:
        scores["memory_query"] += 0.2

    if has_path and ("supabase" in lowered or "render" in lowered or "comprueba" in lowered):
        scores["repository_audit_with_memory"] += 0.9
        scores["memory_query"] += 0.1

    if "glm" in lowered or "z.ai" in lowered or "te lo copio" in lowered or "planteamiento" in lowered:
        scores["external_analysis_import"] += 0.7

    if has_path and ("arquitectura" in lowered or "markdown" in lowered):
        scores["architecture_collaboration"] += 0.8

    if has_path and "incluyo dentro de una app" in lowered:
        scores["repository_onboarding"] += 0.35

    best_intent, best_score = max(scores.items(), key=lambda item: item[1])
    runner_up = sorted(scores.values(), reverse=True)[1]
    unclear = best_score < 0.6 or (best_score - runner_up) < 0.15

    project_key = context.project_keys[0] if context.project_keys else None
    summary = build_summary(best_intent, raw_input, context, project_key)
    clarification_question = build_clarification_question(best_intent, raw_input, context) if unclear else None

    return ClassificationResult(
        intent=best_intent,
        confidence=round(min(best_score, 0.99), 2),
        status="needs_clarification" if unclear else "ready",
        normalized_summary=summary,
        clarification_question=clarification_question,
        domain=context.domain,
        project_key=project_key,
    )


def build_summary(intent: str, raw_input: str, context: ExtractedContext, project_key: str | None) -> str:
    first_url = context.urls[0] if context.urls else None
    if intent == "resource_watch_later":
        return f"Recurso pendiente de revisar: {first_url or raw_input[:80]}"
    if intent == "resource_apply_to_project":
        suffix = f" para {project_key}" if project_key else ""
        return f"Recurso para revisar y aplicar{suffix}: {first_url or raw_input[:80]}"
    if intent == "memory_query":
        return f"Consulta de memoria: {raw_input[:120]}"
    if intent == "repository_audit_with_memory":
        return f"Auditoria de repositorio con apoyo de memoria: {project_key or context.paths[0]}"
    if intent == "architecture_collaboration":
        return f"Revision de arquitectura y markdown para {project_key or context.paths[0]}"
    if intent == "external_analysis_import":
        return "Importacion de planteamiento externo para revisar y relacionar"
    if intent == "repository_onboarding":
        return f"Onboarding de repositorio: {project_key or context.paths[0]}"
    return raw_input[:120]


def build_clarification_question(intent: str, raw_input: str, context: ExtractedContext) -> str:
    if context.urls and "aplicar" not in raw_input.lower() and "recuerd" not in raw_input.lower():
        return "He detectado un enlace, pero no tengo claro si quieres verlo mas tarde o aplicarlo a un proyecto. Debo tratarlo como recurso pendiente o como recurso accionable?"
    if context.paths and intent in {"repository_onboarding", "architecture_collaboration"}:
        return "He detectado un repositorio, pero necesito saber si quieres una revision general, una auditoria tecnica o centrarme solo en arquitectura."
    return "No tengo suficiente contexto para clasificar esta entrada con seguridad. Que accion principal quieres que tome?"
