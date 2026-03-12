from __future__ import annotations

from dataclasses import asdict

from july.classifier import classify_input, extract_context
from july.models import ClassificationResult, ExtractedContext


def create_capture_plan(raw_input: str, clarification_answer: str | None = None) -> dict:
    effective_input = compose_effective_input(raw_input, clarification_answer)
    context = extract_context(effective_input)
    classification = classify_input(effective_input, context)
    return build_plan(raw_input, context, classification, clarification_answer=clarification_answer)


def compose_effective_input(raw_input: str, clarification_answer: str | None = None) -> str:
    if not clarification_answer:
        return raw_input
    return f"{raw_input}\nAclaracion del usuario: {clarification_answer}"


def build_plan(
    raw_input: str,
    context: ExtractedContext,
    classification: ClassificationResult,
    clarification_answer: str | None = None,
) -> dict:
    task = build_task(raw_input, classification)
    memory = build_memory_candidate(raw_input, classification)
    artifacts = build_artifacts(context)

    plan = {
        "context": asdict(context),
        "classification": asdict(classification),
        "task": task,
        "memory": memory,
        "artifacts": artifacts,
    }
    if clarification_answer:
        plan["clarification_answer"] = clarification_answer
    return plan


def apply_classification_overrides(
    raw_input: str,
    base_plan: dict,
    overrides: dict,
    clarification_answer: str | None = None,
) -> dict:
    effective_input = compose_effective_input(raw_input, clarification_answer)
    context = extract_context(effective_input)
    merged = dict(base_plan["classification"])
    merged.update({key: value for key, value in overrides.items() if value is not None})

    project_key = merged.get("project_key")
    if project_key and project_key not in context.project_keys:
        context.project_keys.append(project_key)

    classification = ClassificationResult(
        intent=merged["intent"],
        confidence=float(merged["confidence"]),
        status=merged["status"],
        normalized_summary=merged["normalized_summary"],
        clarification_question=merged.get("clarification_question"),
        domain=merged["domain"],
        project_key=project_key,
    )
    return build_plan(raw_input, context, classification, clarification_answer=clarification_answer)


def build_task(raw_input: str, classification) -> dict | None:
    intent = classification.intent
    project_key = classification.project_key
    titles = {
        "resource_watch_later": "Revisar recurso pendiente",
        "resource_apply_to_project": "Evaluar recurso y aplicarlo al proyecto",
        "repository_onboarding": "Analizar nuevo repositorio",
        "repository_audit_with_memory": "Revisar repo con apoyo de memoria previa",
        "external_analysis_import": "Revisar planteamiento externo",
        "architecture_collaboration": "Revisar arquitectura del repositorio",
    }
    task_type_map = {
        "resource_watch_later": "watch_resource",
        "resource_apply_to_project": "apply_resource",
        "repository_onboarding": "review_repository",
        "repository_audit_with_memory": "audit_repository",
        "external_analysis_import": "review_external_input",
        "architecture_collaboration": "review_architecture",
    }

    if intent not in titles:
        return None

    suffix = f" ({project_key})" if project_key else ""
    return {
        "task_type": task_type_map[intent],
        "status": "needs_clarification" if classification.status == "needs_clarification" else "pending",
        "title": f"{titles[intent]}{suffix}",
        "details": raw_input,
        "project_key": project_key,
    }


def build_memory_candidate(raw_input: str, classification) -> dict | None:
    intent = classification.intent
    if intent in {"resource_watch_later", "memory_query"}:
        return None

    if classification.status == "needs_clarification":
        status = "needs_clarification"
    else:
        status = "candidate" if intent in {"resource_apply_to_project", "external_analysis_import"} else "ready"
    memory_kind = {
        "repository_onboarding": "episodic",
        "repository_audit_with_memory": "procedural",
        "architecture_collaboration": "procedural",
        "resource_apply_to_project": "semantic",
        "external_analysis_import": "semantic",
        "general_note": "semantic",
    }.get(intent, "semantic")

    return {
        "memory_kind": memory_kind,
        "title": classification.normalized_summary,
        "summary": classification.normalized_summary,
        "distilled_knowledge": infer_distilled_knowledge(raw_input, intent),
        "domain": classification.domain,
        "scope": "project" if classification.project_key else "global",
        "project_key": classification.project_key,
        "importance": 3 if intent in {"repository_audit_with_memory", "architecture_collaboration"} else 2,
        "confidence": classification.confidence,
        "status": status,
    }


def infer_distilled_knowledge(raw_input: str, intent: str) -> str:
    if intent == "repository_audit_with_memory":
        return "Entrada orientada a revisar configuraciones o decisiones tecnicas usando memoria previa como apoyo."
    if intent == "architecture_collaboration":
        return "Entrada orientada a comprender arquitectura actual, detectar buenas practicas y preparar siguientes decisiones."
    if intent == "resource_apply_to_project":
        return "Recurso externo que podria convertirse en aprendizaje aplicable a un proyecto concreto tras revision."
    if intent == "external_analysis_import":
        return "Analisis externo importado para compararlo, sintetizarlo y convertirlo en conocimiento reutilizable."
    return raw_input[:180]


def build_artifacts(context) -> list[dict]:
    artifacts = []
    for url in context.urls:
        artifacts.append({"artifact_type": "url", "value": url, "metadata_json": "{}"})
    for path in context.paths:
        artifacts.append({"artifact_type": "path", "value": path, "metadata_json": "{}"})
    return artifacts
