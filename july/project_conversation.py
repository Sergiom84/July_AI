from __future__ import annotations

import json
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from july.db import JulyDatabase
from july.external_refs import suggest_references_for_context
from july.pipeline import apply_classification_overrides, create_capture_plan, enrich_plan_with_proactive_recall

README_NAMES = ("README.md", "README.txt", "README.rst")
MANIFEST_NAMES = (
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
    "Dockerfile",
    "deno.json",
    "tsconfig.json",
)
ENTRYPOINT_NAMES = (
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "src/main.py",
    "src/main.ts",
    "src/index.ts",
    "src/index.js",
)
TOPIC_PATTERNS = {
    "auth/jwt-flow": ("jwt", "token", "refresh token", "auth", "autentic"),
    "mcp/integration": ("mcp", "model context protocol"),
    "database/supabase": ("supabase",),
    "deploy/render": ("render", "deploy"),
    "llm/openai": ("openai", "gpt"),
    "llm/anthropic": ("anthropic", "claude"),
    "project/structure": ("estructura de proyecto", "arquitectura", "repo", "repositorio"),
}
SENSITIVE_PATTERNS = (
    "api_key",
    "api key",
    "token=",
    "secret",
    "password",
    "private key",
    "bearer ",
    "sk-",
    "sb_publishable_",
    "sb_secret_",
    "xoxb-",
)
TENTATIVE_PATTERNS = ("quiz", "tal vez", "igual", "probar", "idea", "propuesta", "borrador", "tentativ")
EPHEMERAL_PATTERNS = ("manana", "luego", "recordar", "pendiente", "temporal", "mas tarde")
DURABLE_PATTERNS = (
    "decid",
    "eleg",
    "usar ",
    "obligatorio",
    "siempre",
    "evitar",
    "resuelto",
    "solucion",
    "causa",
    "procedimiento",
    "flujo",
    "configur",
    "arquitect",
)
REUSABLE_PATTERNS = (
    "error",
    "bug",
    "mcp",
    "supabase",
    "render",
    "deploy",
    "auth",
    "jwt",
    "comando",
    "paso",
    "entrypoint",
    "integracion",
)
INTEGRATION_KEYWORDS = {
    "supabase": "Supabase",
    "render": "Render",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "claude": "Anthropic",
    "telegram": "Telegram",
    "email": "Email",
    "obsidian": "Obsidian",
    "sqlite": "SQLite",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "docker": "Docker",
    "github": "GitHub",
    "mcp": "MCP",
}
PROJECT_ACTIONS = (
    "analyze_now",
    "resume_context",
    "refresh_context",
    "continue_without_context",
    "close_stale_and_continue",
)


class ProjectConversationService:
    def __init__(self, database: JulyDatabase) -> None:
        self.database = database

    def project_entry(
        self,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        limit: int = 5,
        staleness_days: int = 30,
        abandoned_session_hours: int = 24,
    ) -> dict[str, Any]:
        repo_root = detect_repo_root(Path(repo_path) if repo_path else Path.cwd())
        resolved_project_key = derive_project_key(repo_root, project_key=project_key)
        project_ctx = self.database.project_context(resolved_project_key, limit=limit)
        sessions = self.database.session_context(project_key=resolved_project_key, limit=limit)
        active_sessions = self.database.find_active_sessions(
            resolved_project_key,
            limit=limit,
            abandoned_after_hours=abandoned_session_hours,
        )
        
        # Block A: enriched recall - use repo content or existing context for better search
        recall_query = build_recall_query(project_ctx, sessions, repo_root)
        recall = self.database.proactive_recall(recall_query, project_key=resolved_project_key, limit=5)
        
        state = assess_project_state(project_ctx, sessions, staleness_days=staleness_days)
        staleness = detect_context_staleness(sessions, staleness_days=staleness_days)
        summary = build_context_summary(
            resolved_project_key,
            state,
            project_ctx,
            sessions,
            staleness=staleness,
            active_sessions=active_sessions,
        )
        question, options, recommended_action = build_entry_prompt(
            state,
            staleness=staleness,
            active_sessions=active_sessions,
        )
        
        return {
            "repo_root": str(repo_root),
            "project_key": resolved_project_key,
            "project_state": state,
            "context_summary": summary,
            "greeting": (
                f"Hola, soy July. Estoy en {resolved_project_key} y puedo ayudarte como arquitecto y colaborador."
            ),
            "question": question,
            "options": options,
            "recommended_action": recommended_action,
            "active_session_warning": build_active_session_warning(active_sessions),
            "context_signals": {
                "inbox_items": len(project_ctx["inbox"]),
                "tasks": len(project_ctx["tasks"]),
                "memory_items": len(project_ctx["memory"]),
                "sessions": len(sessions),
                "summarized_sessions": sum(1 for session in sessions if (session.get("summary") or "").strip()),
                "ready_memory": sum(1 for memory in project_ctx["memory"] if memory["status"] == "ready"),
                "active_sessions": len(active_sessions),
                "abandoned_sessions": sum(1 for session in active_sessions if session.get("is_abandoned")),
            },
            "active_sessions": active_sessions,
            "related_context": recall,
            "staleness": staleness,
            "recall_query": recall_query,
        }

    def project_onboard(
        self,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        session_key: str | None = None,
        agent_name: str = "july",
        goal: str | None = None,
    ) -> dict[str, Any]:
        entry = self.project_entry(repo_path=repo_path, project_key=project_key)
        repo_root = Path(entry["repo_root"])
        resolved_project_key = entry["project_key"]
        analysis = analyze_repository(repo_root, project_state=entry["project_state"])
        resolved_session_key = session_key or build_session_key(resolved_project_key)

        session_start = self.database.session_start(
            resolved_session_key,
            project_key=resolved_project_key,
            agent_name=agent_name,
            goal=goal or f"Onboarding conversacional de {resolved_project_key}",
        )

        raw_input = build_onboarding_raw_input(resolved_project_key, repo_root, analysis)
        base_plan = create_capture_plan(raw_input)
        plan = apply_classification_overrides(
            raw_input,
            base_plan,
            {
                "intent": "repository_onboarding",
                "confidence": 0.95,
                "status": "ready",
                "normalized_summary": f"Snapshot inicial del proyecto {resolved_project_key}",
                "clarification_question": None,
                "project_key": resolved_project_key,
            },
        )
        plan["task"] = None
        if plan["memory"]:
            plan["memory"]["title"] = f"Snapshot inicial del proyecto {resolved_project_key}"
            plan["memory"]["summary"] = analysis["snapshot_summary"]
            plan["memory"]["distilled_knowledge"] = raw_input
            plan["memory"]["memory_kind"] = "episodic"
            plan["memory"]["scope"] = "project"
            plan["memory"]["project_key"] = resolved_project_key
            plan["memory"]["importance"] = 4
            plan["memory"]["confidence"] = 0.95
            plan["memory"]["status"] = "ready"

        capture_result = self.database.capture(raw_input, "project_onboard", str(repo_root), plan)

        session_summary = self.database.session_summary(
            resolved_session_key,
            summary=analysis["snapshot_summary"],
            discoveries="; ".join(analysis["discoveries"]),
            accomplished="; ".join(
                [
                    "Revision read-only del repositorio",
                    "Snapshot inicial del proyecto guardado en la BD de July",
                ]
            ),
            next_steps="; ".join(analysis["suggested_next_steps"]),
            relevant_files="; ".join(analysis["files_consulted"]),
        )
        session_end = self.database.session_end(resolved_session_key)

        return {
            "project_key": resolved_project_key,
            "project_state": entry["project_state"],
            "repo_root": str(repo_root),
            "analysis": analysis,
            "storage": capture_result,
            "session": {
                "start": session_start,
                "summary": session_summary,
                "end": session_end,
            },
        }

    def conversation_checkpoint(
        self,
        text: str,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        source: str = "conversation_checkpoint",
        source_ref: str | None = None,
        persist: bool = False,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        repo_root = detect_repo_root(Path(repo_path) if repo_path else Path.cwd())
        resolved_project_key = derive_project_key(repo_root, project_key=project_key)
        checkpoint = classify_checkpoint(text)
        recall = self.database.proactive_recall(text, project_key=resolved_project_key, limit=3)
        checkpoint["project_key"] = resolved_project_key
        checkpoint["repo_root"] = str(repo_root)
        checkpoint["related_context"] = recall
        checkpoint["external_ref_suggestions"] = suggest_references_for_context(text, project_key=resolved_project_key)

        if checkpoint["action"] == "ask_user":
            question = (
                "Esto parece util para futuras iteraciones, pero aun es ambiguo. Quieres que lo guarde como referencia?"
            )
            checkpoint["question"] = question
            checkpoint["pending_confirmation"] = {
                "kind": "checkpoint_persist",
                "question": question,
                "project_key": resolved_project_key,
                "confirmation_action": "persist",
                "tool": "conversation_checkpoint",
                "arguments": {
                    "text": text,
                    "project_key": resolved_project_key,
                    "repo_path": str(repo_root),
                    "persist": True,
                },
            }
        elif checkpoint["action"] == "ignore":
            checkpoint["question"] = "No conviene guardarlo automaticamente en July."

        # persist=True allows overriding ask_user (agent has confirmed with user)
        # but never overrides ignore (sensitive data)
        can_persist = checkpoint["action"] in ("store_directly", "ask_user")
        if persist and can_persist:
            raw_input = text.strip()
            base_plan = create_capture_plan(raw_input)
            plan = apply_classification_overrides(
                raw_input,
                base_plan,
                {
                    "confidence": max(0.86, float(base_plan["classification"]["confidence"])),
                    "status": "ready",
                    "clarification_question": None,
                    "normalized_summary": build_checkpoint_summary(raw_input, resolved_project_key),
                    "project_key": resolved_project_key,
                },
            )
            plan["task"] = None
            if plan["memory"]:
                plan["memory"]["status"] = "ready"
                plan["memory"]["project_key"] = resolved_project_key
                plan["memory"]["scope"] = "project"
                plan["memory"]["importance"] = 4 if checkpoint["kind"] in {"decision", "resolved_error"} else 3
                plan["memory"]["memory_kind"] = "procedural" if checkpoint["kind"] != "reference" else "semantic"

            recall = self.database.proactive_recall(raw_input, project_key=resolved_project_key, limit=3)
            plan = enrich_plan_with_proactive_recall(plan, recall)
            capture_result = self.database.capture(raw_input, source, source_ref or str(repo_root), plan)
            checkpoint["stored"] = capture_result

            # Mark if this was persisted via confirmation override
            if checkpoint["action"] == "ask_user":
                checkpoint["persisted_via_confirmation"] = True

            if model_name:
                self.database.save_model_contribution(
                    model_name=model_name,
                    contribution_type=checkpoint["kind"],
                    title=plan["classification"]["normalized_summary"],
                    content=raw_input,
                    inbox_item_id=capture_result["inbox_item_id"],
                    project_key=resolved_project_key,
                    adopted=True,
                )

            self._maybe_link_topic(raw_input, checkpoint, capture_result)

        return checkpoint

    def _maybe_link_topic(self, raw_input: str, checkpoint: dict[str, Any], capture_result: dict[str, Any]) -> None:
        topic_key = detect_topic_key(raw_input)
        if not topic_key or not capture_result.get("memory_item_id"):
            return

        existing_topics = {row["topic_key"] for row in self.database.list_topics(limit=100)}
        if topic_key not in existing_topics:
            search_term = topic_key.split("/", 1)[-1].replace("-", " ")
            search_result = self.database.search(search_term, limit=2)
            has_related_context = any(search_result.values())
            if not has_related_context:
                return
            self.database.create_topic(topic_key, topic_key.replace("/", " ").title(), "Programacion")

        self.database.link_to_topic(topic_key, memory_item_id=capture_result["memory_item_id"])
        checkpoint["topic_key"] = topic_key

    def project_action(
        self,
        *,
        action: str,
        repo_path: str | None = None,
        project_key: str | None = None,
        agent_name: str = "july",
        goal: str | None = None,
    ) -> dict[str, Any]:
        """Execute a project action based on user's choice from project_entry.

        Block C: Single entry point for post-entry actions.
        Actions that continue work start a session automatically with a generated session key.
        """
        if action not in PROJECT_ACTIONS:
            allowed = ", ".join(PROJECT_ACTIONS)
            raise ValueError(f"Unknown action: {action}. Allowed actions: {allowed}")

        repo_root = detect_repo_root(Path(repo_path) if repo_path else Path.cwd())
        resolved_project_key = derive_project_key(repo_root, project_key=project_key)

        if action == "analyze_now":
            # Delegate to project_onboard - it already creates its own session
            return self.project_onboard(
                repo_path=repo_path,
                project_key=project_key,
                agent_name=agent_name,
                goal=goal or f"Onboarding de {resolved_project_key}",
            )

        active_sessions = self.database.find_active_sessions(resolved_project_key, limit=5)
        reuse_session_actions = {"resume_context", "refresh_context"}
        reused_active_session = active_sessions[0] if action in reuse_session_actions and active_sessions else None
        closed_sessions: list[dict[str, Any]] = []

        if action == "close_stale_and_continue":
            closed_sessions = self._close_active_sessions(active_sessions)
            active_sessions = self.database.find_active_sessions(resolved_project_key, limit=5)

        if reused_active_session:
            session = {
                "session_id": reused_active_session["id"],
                "session_key": reused_active_session["session_key"],
                "status": "already_active",
                "started_at": reused_active_session["started_at"],
            }
        else:
            session_key = build_session_key(resolved_project_key)
            session = self.database.session_start(
                session_key,
                project_key=resolved_project_key,
                agent_name=agent_name,
                goal=goal or f"Sesion de trabajo en {resolved_project_key}",
            )

        if action in ("resume_context", "close_stale_and_continue"):
            return self._build_resume_context_response(
                resolved_project_key,
                session,
                reused_existing_session=bool(reused_active_session),
                active_sessions=active_sessions,
                closed_sessions=closed_sessions,
            )

        if action == "refresh_context":
            analysis = analyze_repository(repo_root, project_state="known")
            previous_snapshot = self.database.latest_project_onboarding(resolved_project_key)
            previous_analysis = parse_onboarding_snapshot(previous_snapshot["raw_input"]) if previous_snapshot else None
            comparison = compare_repository_analysis(previous_analysis, analysis)
            changes_detected = comparison["changes_detected"]

            if previous_snapshot:
                message = (
                    "Contexto refrescado. "
                    + ("Se detectaron cambios respecto al ultimo snapshot." if changes_detected else "No se detectaron cambios estructurales relevantes desde el ultimo snapshot.")
                )
            else:
                message = "Contexto refrescado. No habia snapshot previo guardado para comparar."

            return {
                "session": session,
                "project_key": resolved_project_key,
                "current_analysis": analysis,
                "previous_snapshot": previous_snapshot,
                "previous_analysis": previous_analysis,
                "comparison": comparison,
                "changes_detected": changes_detected,
                "message": message,
                "active_sessions": active_sessions,
                "closed_sessions": closed_sessions,
            }

        if action == "continue_without_context":
            # Minimal response - just session started
            return {
                "session": session,
                "project_key": resolved_project_key,
                "message": "Sesion iniciada sin recuperacion de contexto previo.",
                "active_sessions": active_sessions,
                "closed_sessions": closed_sessions,
            }

        raise RuntimeError(f"Validated action reached unexpected branch: {action}")

    def _build_resume_context_response(
        self,
        project_key: str,
        session: dict[str, Any],
        *,
        reused_existing_session: bool,
        active_sessions: list[dict[str, Any]],
        closed_sessions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        project_ctx = self.database.project_context(project_key, limit=10)
        sessions = self.database.session_context(project_key=project_key, limit=5)
        staleness = detect_context_staleness(sessions)

        ready_memories = [m for m in project_ctx["memory"] if _get_row_field(m, "status") == "ready"]
        pending_tasks = [t for t in project_ctx["tasks"] if _get_row_field(t, "status") != "done"]
        latest_session = sessions[0] if sessions else None

        suggested_next_step = None
        latest_next_steps = _get_row_field(latest_session, "next_steps", "") if latest_session else ""
        if latest_next_steps.strip():
            suggested_next_step = latest_next_steps
        elif pending_tasks:
            suggested_next_step = f"Tarea pendiente: {_get_row_field(pending_tasks[0], 'title')}"

        response = {
            "session": session,
            "project_key": project_key,
            "context_summary": build_context_summary(
                project_key,
                "known",
                project_ctx,
                sessions,
                staleness=staleness,
                active_sessions=active_sessions,
            ),
            "latest_session": latest_session,
            "ready_memories": ready_memories[:5],
            "pending_tasks": pending_tasks[:5],
            "suggested_next_step": suggested_next_step,
            "active_sessions": active_sessions,
            "reused_existing_session": reused_existing_session,
        }
        if closed_sessions:
            response["closed_sessions"] = closed_sessions
        return response

    def _close_active_sessions(self, active_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        closed_sessions: list[dict[str, Any]] = []
        for active_session in active_sessions:
            closed = self.database.session_end(active_session["session_key"])
            closed_sessions.append(
                {
                    "session_key": active_session["session_key"],
                    "previous_status": active_session["status"],
                    "closed_status": closed["status"],
                    "ended_at": closed["ended_at"],
                }
            )
        return closed_sessions


def detect_repo_root(start_path: Path) -> Path:
    current = start_path.resolve()
    if current.is_file():
        current = current.parent

    best_match = current
    best_score = -1
    for candidate in [current, *current.parents]:
        score = sum(1 for marker in (".git", "AGENTS.md", *README_NAMES, *MANIFEST_NAMES) if (candidate / marker).exists())
        if (candidate / ".git").exists():
            return candidate
        if score > best_score:
            best_match = candidate
            best_score = score
    return best_match


def derive_project_key(repo_root: Path, *, project_key: str | None = None) -> str:
    return project_key.strip() if project_key else repo_root.name


def assess_project_state(
    project_ctx: dict[str, list[Any]],
    sessions: list[dict[str, Any]],
    *,
    staleness_days: int = 30,
) -> str:
    has_ready_memory = any(memory["status"] == "ready" for memory in project_ctx["memory"])
    has_summary = any((session.get("summary") or "").strip() for session in sessions)
    has_next_step = any((session.get("next_steps") or "").strip() for session in sessions) or bool(project_ctx["tasks"])
    has_any_context = bool(project_ctx["inbox"] or project_ctx["memory"] or project_ctx["tasks"] or sessions)

    if has_ready_memory and has_summary and has_next_step:
        # Check for staleness - if the latest session is too old, downgrade to partial
        staleness = detect_context_staleness(sessions, staleness_days=staleness_days)
        if staleness["is_stale"]:
            return "partial"  # Downgrade known to partial when stale
        return "known"
    if has_any_context:
        return "partial"
    return "new"


def detect_context_staleness(sessions: list[dict[str, Any]], staleness_days: int = 30) -> dict[str, Any]:
    """Check if the latest session is older than the staleness threshold.
    
    Returns:
        {
            "is_stale": bool,
            "days_since_last_session": int | None,
            "last_session_date": str | None,
        }
    """
    if not sessions:
        return {"is_stale": False, "days_since_last_session": None, "last_session_date": None}
    
    # Find the latest session with a started_at timestamp
    latest_session = None
    latest_date = None
    
    for session in sessions:
        started_at = session.get("started_at")
        if not started_at:
            continue
        try:
            # Parse ISO format timestamp
            if isinstance(started_at, str):
                session_date = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            else:
                continue
        except (ValueError, TypeError):
            continue
        
        if latest_date is None or session_date > latest_date:
            latest_date = session_date
            latest_session = session
    
    if latest_date is None:
        return {"is_stale": False, "days_since_last_session": None, "last_session_date": None}
    
    now = datetime.now(UTC)
    days_since = (now - latest_date).days
    
    return {
        "is_stale": days_since > staleness_days,
        "days_since_last_session": days_since,
        "last_session_date": latest_date.isoformat(),
    }


def build_recall_query(
    project_ctx: dict[str, list[Any]],
    sessions: list[dict[str, Any]],
    repo_root: Path,
) -> str:
    """Build a rich recall query from existing context or repo content.
    
    Block A: Instead of searching on bare project key, use actual content.
    """
    query_parts: list[str] = []
    
    # From existing memory titles (handle both dict and sqlite3.Row)
    for memory in project_ctx.get("memory", [])[:3]:
        title = _get_row_field(memory, "title")
        if title:
            query_parts.append(title)
    
    # From latest session summary
    for session in sessions[:2]:
        summary = (_get_row_field(session, "summary") or "").strip()
        if summary:
            query_parts.append(summary[:100])
        next_steps = (_get_row_field(session, "next_steps") or "").strip()
        if next_steps:
            query_parts.append(next_steps[:80])
    
    # From tasks
    for task in project_ctx.get("tasks", [])[:2]:
        title = _get_row_field(task, "title")
        if title:
            query_parts.append(title)
    
    # If we have context, use it
    if query_parts:
        return " ".join(query_parts)[:300]
    
    # Otherwise, try to extract from repo
    try:
        consulted = collect_consulted_files(repo_root)
        file_texts = {rel_path: read_limited_text(repo_root / rel_path) for rel_path in consulted}
        objective = extract_objective(file_texts)
        stack = detect_stack(repo_root)
        integrations = detect_integrations(file_texts)
        
        repo_parts = [objective]
        if stack:
            repo_parts.append(" ".join(stack[:3]))
        if integrations:
            repo_parts.append(" ".join(integrations[:3]))
        
        return " ".join(repo_parts)[:300]
    except Exception:
        return repo_root.name


def _get_row_field(row: Any, field: str, default: str = "") -> str:
    """Get a field from either a dict or sqlite3.Row object."""
    try:
        if isinstance(row, dict):
            return row.get(field, default) or default
        # sqlite3.Row supports both indexing and keys()
        return str(row[field]) if field in row.keys() else default
    except (KeyError, TypeError, IndexError):
        return default


def build_context_summary(
    project_key: str,
    state: str,
    project_ctx: dict[str, list[Any]],
    sessions: list[dict[str, Any]],
    *,
    staleness: dict[str, Any] | None = None,
    active_sessions: list[dict[str, Any]] | None = None,
) -> str:
    latest_session = next((session for session in sessions if (session.get("summary") or "").strip()), None)
    latest_memory = project_ctx["memory"][0] if project_ctx["memory"] else None
    active_session_note = summarize_active_sessions(active_sessions)

    if state == "new":
        parts = [f"No hay contexto util guardado todavia para {project_key}"]
        if active_session_note:
            parts.append(active_session_note)
        return ". ".join(parts) + "."

    if state == "partial":
        parts = [f"Hay contexto parcial de {project_key}"]
        if active_session_note:
            parts.append(active_session_note)
        if latest_memory:
            parts.append(f"ultima memoria: {latest_memory['title']}")
        if latest_session:
            parts.append(f"ultima sesion resumida: {latest_session['summary']}")
        elif sessions:
            parts.append("hay sesiones previas sin resumen util")
        if project_ctx["tasks"]:
            parts.append(f"tareas registradas: {len(project_ctx['tasks'])}")
        # Add staleness note if context is stale
        if staleness and staleness.get("is_stale"):
            days = staleness.get("days_since_last_session")
            if days is not None:
                parts.append(f"ultima actividad hace {days} dias")
        parts.append("falta una foto consolidada o un siguiente paso claro")
        return ". ".join(parts) + "."

    parts = [f"Ya hay contexto reutilizable de {project_key}"]
    if active_session_note:
        parts.append(active_session_note)
    if latest_session:
        parts.append(f"ultimo resumen: {latest_session['summary']}")
        if latest_session.get("next_steps"):
            parts.append(f"siguiente paso recordado: {latest_session['next_steps']}")
    if latest_memory:
        parts.append(f"memoria destacada: {latest_memory['title']}")
    return ". ".join(parts) + "."


def build_entry_prompt(
    state: str,
    *,
    staleness: dict[str, Any] | None = None,
    active_sessions: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, str]], str]:
    if active_sessions:
        open_count = len(active_sessions)
        abandoned_count = sum(1 for session in active_sessions if session.get("is_abandoned"))
        session_note = (
            f"Hay {open_count} sesion abierta sin cerrar."
            if open_count == 1
            else f"Hay {open_count} sesiones abiertas sin cerrar."
        )
        if abandoned_count:
            session_note += (
                f" {abandoned_count} parece abandonada."
                if abandoned_count == 1
                else f" {abandoned_count} parecen abandonadas."
            )
        options = [{"id": "resume_context", "label": "Retomar sesion abierta"}]
        recommended_action = "resume_context"
        if abandoned_count:
            options.append({"id": "close_stale_and_continue", "label": "Cerrar y seguir"})
            recommended_action = "close_stale_and_continue"
        options.extend(
            [
                {"id": "refresh_context", "label": "Revisar estado actual"},
                {"id": "continue_without_context", "label": "Abrir otra sesion"},
            ]
        )
        return (f"{session_note} Quieres retomar antes de abrir otra?", options, recommended_action)
    if state == "new":
        return (
            "Veo que este proyecto es nuevo para July. Quieres que lo analice ahora?",
            [
                {"id": "analyze_now", "label": "Si, analiza ahora"},
                {"id": "continue_without_context", "label": "Continuar sin onboarding"},
            ],
            "analyze_now",
        )
    if state == "partial":
        return (
            "Hay contexto parcial de este proyecto. Quieres que refresque el estado y complete la foto inicial?",
            [
                {"id": "refresh_context", "label": "Si, refresca contexto"},
                {"id": "analyze_now", "label": "Haz onboarding completo"},
                {"id": "continue_without_context", "label": "Continuar sin refrescar"},
            ],
            "refresh_context",
        )
    return (
        "Ya tenemos contexto previo util de este proyecto. Quieres que recupere donde lo dejamos?",
        [
            {"id": "resume_context", "label": "Si, recupera contexto"},
            {"id": "refresh_context", "label": "Revisa solo lo que haya cambiado"},
            {"id": "continue_without_context", "label": "Continuar sin recuperar"},
        ],
        "resume_context",
    )


def build_active_session_warning(active_sessions: list[dict[str, Any]] | None) -> str | None:
    if not active_sessions:
        return None
    abandoned_count = sum(1 for session in active_sessions if session.get("is_abandoned"))
    if abandoned_count:
        return (
            "Hay sesiones abiertas sin cerrar y al menos una parece abandonada. "
            "Conviene retomarla o cerrarla antes de abrir otra."
        )
    return "Hay una sesion abierta sin cerrar. Conviene retomarla antes de abrir otra."


def summarize_active_sessions(active_sessions: list[dict[str, Any]] | None) -> str | None:
    if not active_sessions:
        return None
    open_count = len(active_sessions)
    abandoned_count = sum(1 for session in active_sessions if session.get("is_abandoned"))
    note = (
        "hay 1 sesion abierta sin cerrar"
        if open_count == 1
        else f"hay {open_count} sesiones abiertas sin cerrar"
    )
    if abandoned_count:
        note += (
            " y 1 parece abandonada"
            if abandoned_count == 1
            else f" y {abandoned_count} parecen abandonadas"
        )
    return note


def analyze_repository(repo_root: Path, *, project_state: str) -> dict[str, Any]:
    files_consulted = collect_consulted_files(repo_root)
    file_texts = {rel_path: read_limited_text(repo_root / rel_path) for rel_path in files_consulted}
    objective = extract_objective(file_texts)
    stack = detect_stack(repo_root)
    commands = detect_commands(repo_root)
    integrations = detect_integrations(file_texts)
    entrypoints = detect_entrypoints(repo_root)
    open_questions = detect_open_questions(repo_root, file_texts, commands, entrypoints)
    suggested_next_steps = build_suggested_next_steps(project_state, open_questions, entrypoints)
    summary = build_snapshot_summary(repo_root.name, objective, stack, entrypoints, suggested_next_steps)

    discoveries = [
        f"Objetivo detectado: {objective}",
        f"Stack visible: {', '.join(stack) if stack else 'sin detectar'}",
    ]
    if commands:
        discoveries.append(f"Comandos utiles: {', '.join(commands[:5])}")
    if integrations:
        discoveries.append(f"Integraciones visibles: {', '.join(integrations)}")

    return {
        "objective": objective,
        "stack": stack,
        "commands": commands,
        "integrations": integrations,
        "entrypoints": entrypoints,
        "open_questions": open_questions,
        "suggested_next_steps": suggested_next_steps,
        "files_consulted": files_consulted,
        "snapshot_summary": summary,
        "discoveries": discoveries,
    }


def collect_consulted_files(repo_root: Path) -> list[str]:
    consulted: list[str] = []

    for readme_name in README_NAMES:
        if (repo_root / readme_name).exists():
            consulted.append(readme_name)
            break

    if (repo_root / "AGENTS.md").exists():
        consulted.append("AGENTS.md")

    for manifest_name in MANIFEST_NAMES:
        if (repo_root / manifest_name).exists():
            consulted.append(manifest_name)

    for entrypoint_name in ENTRYPOINT_NAMES:
        if (repo_root / entrypoint_name).exists():
            consulted.append(entrypoint_name)

    return consulted


def read_limited_text(path: Path, max_chars: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def extract_objective(file_texts: dict[str, str]) -> str:
    readme_text = next((text for name, text in file_texts.items() if name.startswith("README")), "")
    if not readme_text:
        return "No se detecto un objetivo claro en README."

    paragraphs = []
    current: list[str] = []
    for line in readme_text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if stripped.startswith("#"):
            continue
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current))

    for paragraph in paragraphs:
        if len(paragraph) >= 40:
            return paragraph[:220]
    return paragraphs[0][:220] if paragraphs else "No se detecto un objetivo claro en README."


def detect_stack(repo_root: Path) -> list[str]:
    stack: list[str] = []
    if (repo_root / "pyproject.toml").exists() or (repo_root / "requirements.txt").exists():
        stack.append("Python")
    if (repo_root / "package.json").exists():
        stack.append("Node.js")
    if (repo_root / "tsconfig.json").exists():
        stack.append("TypeScript")
    elif (repo_root / "package.json").exists():
        stack.append("JavaScript")
    if (repo_root / "go.mod").exists():
        stack.append("Go")
    if (repo_root / "Cargo.toml").exists():
        stack.append("Rust")
    if list(repo_root.glob("*.csproj")) or list(repo_root.glob("*.sln")):
        stack.append(".NET")
    if (repo_root / "Dockerfile").exists():
        stack.append("Docker")
    if (repo_root / "tests").exists():
        stack.append("Tests visibles")
    return dedupe_preserve_order(stack)


def detect_commands(repo_root: Path) -> list[str]:
    commands: list[str] = []

    package_json_path = repo_root / "package.json"
    if package_json_path.exists():
        try:
            payload = json.loads(package_json_path.read_text(encoding="utf-8"))
            for script_name in ("dev", "start", "build", "test"):
                if script_name in payload.get("scripts", {}):
                    commands.append(f"npm run {script_name}")
        except (OSError, json.JSONDecodeError):
            pass

    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            scripts = payload.get("project", {}).get("scripts", {})
            for script_name in scripts:
                commands.append(script_name)
        except (OSError, tomllib.TOMLDecodeError):
            pass

    return dedupe_preserve_order(commands)[:8]


def detect_integrations(file_texts: dict[str, str]) -> list[str]:
    lowered = "\n".join(file_texts.values()).lower()
    integrations = [label for keyword, label in INTEGRATION_KEYWORDS.items() if keyword in lowered]
    return dedupe_preserve_order(integrations)


def detect_entrypoints(repo_root: Path) -> list[str]:
    entrypoints = [name for name in ENTRYPOINT_NAMES if (repo_root / name).exists()]
    return dedupe_preserve_order(entrypoints)[:8]


def detect_open_questions(
    repo_root: Path,
    file_texts: dict[str, str],
    commands: list[str],
    entrypoints: list[str],
) -> list[str]:
    questions: list[str] = []
    if not any(name.startswith("README") for name in file_texts):
        questions.append("Falta README en la raiz para explicar el objetivo del proyecto.")
    if "AGENTS.md" not in file_texts:
        questions.append("No hay AGENTS.md con instrucciones especificas para agentes.")
    if not commands:
        questions.append("No se detectaron comandos operativos claros en manifests visibles.")
    if not entrypoints:
        questions.append("No se detecto un entrypoint claro en rutas comunes.")
    if not (repo_root / "tests").exists():
        questions.append("No se detectaron tests visibles en la raiz del proyecto.")
    return questions[:5]


def build_suggested_next_steps(project_state: str, open_questions: list[str], entrypoints: list[str]) -> list[str]:
    next_steps = []
    if project_state == "new":
        next_steps.append("Confirmar el objetivo inmediato del usuario antes de hacer cambios.")
    elif project_state == "partial":
        next_steps.append("Refrescar solo las zonas del repo que ya tienen contexto parcial.")
    else:
        next_steps.append("Validar si el contexto previo sigue vigente antes de retomar trabajo.")

    if entrypoints:
        next_steps.append(f"Revisar primero entrypoints visibles: {', '.join(entrypoints[:3])}.")
    if open_questions:
        next_steps.append(f"Resolver la duda principal: {open_questions[0]}")
    return next_steps[:4]


def build_snapshot_summary(
    project_name: str,
    objective: str,
    stack: list[str],
    entrypoints: list[str],
    suggested_next_steps: list[str],
) -> str:
    parts = [f"Snapshot inicial de {project_name}"]
    parts.append(f"objetivo: {objective}")
    if stack:
        parts.append(f"stack visible: {', '.join(stack)}")
    if entrypoints:
        parts.append(f"entrypoints: {', '.join(entrypoints[:4])}")
    if suggested_next_steps:
        parts.append(f"siguiente paso sugerido: {suggested_next_steps[0]}")
    return ". ".join(parts) + "."


def build_onboarding_raw_input(project_key: str, repo_root: Path, analysis: dict[str, Any]) -> str:
    lines = [
        f"Onboarding de proyecto {project_key}.",
        f"Ruta del repo: {repo_root}",
        f"Objetivo detectado: {analysis['objective']}",
        f"Stack visible: {', '.join(analysis['stack']) if analysis['stack'] else 'sin detectar'}",
        f"Comandos utiles: {', '.join(analysis['commands']) if analysis['commands'] else 'sin detectar'}",
        f"Integraciones visibles: {', '.join(analysis['integrations']) if analysis['integrations'] else 'sin detectar'}",
        f"Entrypoints visibles: {', '.join(analysis['entrypoints']) if analysis['entrypoints'] else 'sin detectar'}",
        f"Dudas abiertas: {' | '.join(analysis['open_questions']) if analysis['open_questions'] else 'ninguna critica'}",
        f"Siguientes pasos sugeridos: {' | '.join(analysis['suggested_next_steps']) if analysis['suggested_next_steps'] else 'confirmar objetivo actual del usuario'}",
    ]
    return "\n".join(lines)


def parse_onboarding_snapshot(raw_input: str) -> dict[str, Any]:
    snapshot = {
        "objective": "",
        "stack": [],
        "commands": [],
        "integrations": [],
        "entrypoints": [],
        "open_questions": [],
        "suggested_next_steps": [],
    }
    prefix_map = {
        "Objetivo detectado: ": ("objective", False),
        "Stack visible: ": ("stack", True),
        "Comandos utiles: ": ("commands", True),
        "Integraciones visibles: ": ("integrations", True),
        "Entrypoints visibles: ": ("entrypoints", True),
        "Dudas abiertas: ": ("open_questions", True),
        "Siguientes pasos sugeridos: ": ("suggested_next_steps", True),
    }
    for line in raw_input.splitlines():
        stripped = line.strip()
        for prefix, (field, is_list) in prefix_map.items():
            if not stripped.startswith(prefix):
                continue
            value = stripped.removeprefix(prefix).strip()
            snapshot[field] = parse_snapshot_list(value) if is_list else value
            break
    return snapshot


def parse_snapshot_list(value: str) -> list[str]:
    lowered = value.lower()
    if lowered in {"sin detectar", "ninguna critica", "sin detectar.", "ninguna critica."}:
        return []
    if " | " in value:
        items = value.split(" | ")
    else:
        items = value.split(",")
    return [normalize_whitespace(item) for item in items if normalize_whitespace(item)]


def compare_repository_analysis(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous is None:
        return {
            "has_changes": False,
            "changes_detected": [],
            "objective_changed": False,
            "previous": None,
            "current": current,
        }

    changes_detected: list[str] = []
    list_comparison = {
        field: compare_string_lists(previous.get(field, []), current.get(field, []))
        for field in ("stack", "commands", "integrations", "entrypoints", "open_questions")
    }
    for field, diff in list_comparison.items():
        label = field.replace("_", " ")
        if diff["added"]:
            changes_detected.append(f"Nuevos {label}: {', '.join(diff['added'])}")
        if diff["removed"]:
            changes_detected.append(f"{label.capitalize()} ya no visibles: {', '.join(diff['removed'])}")

    previous_objective = normalize_whitespace(previous.get("objective", ""))
    current_objective = normalize_whitespace(current.get("objective", ""))
    objective_changed = bool(previous_objective and current_objective and previous_objective != current_objective)
    if objective_changed:
        changes_detected.append("Cambio en el objetivo detectado del proyecto")

    return {
        "has_changes": bool(changes_detected),
        "changes_detected": changes_detected,
        "objective_changed": objective_changed,
        "objective": {
            "previous": previous_objective or None,
            "current": current_objective or None,
        },
        "stack": list_comparison["stack"],
        "commands": list_comparison["commands"],
        "integrations": list_comparison["integrations"],
        "entrypoints": list_comparison["entrypoints"],
        "open_questions": list_comparison["open_questions"],
        "previous": previous,
        "current": current,
    }


def compare_string_lists(previous: list[str], current: list[str]) -> dict[str, list[str]]:
    previous_normalized = dedupe_preserve_order([normalize_whitespace(item) for item in previous if normalize_whitespace(item)])
    current_normalized = dedupe_preserve_order([normalize_whitespace(item) for item in current if normalize_whitespace(item)])
    added = [item for item in current_normalized if item not in previous_normalized]
    removed = [item for item in previous_normalized if item not in current_normalized]
    return {"added": added, "removed": removed}


def build_session_key(project_key: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    return f"onboard-{project_key}-{timestamp}"


def classify_checkpoint(text: str) -> dict[str, Any]:
    lowered = text.lower()
    matched = {
        "sensitive": [pattern for pattern in SENSITIVE_PATTERNS if pattern in lowered],
        "tentative": [pattern for pattern in TENTATIVE_PATTERNS if pattern in lowered],
        "ephemeral": [pattern for pattern in EPHEMERAL_PATTERNS if pattern in lowered],
        "durable": [pattern for pattern in DURABLE_PATTERNS if pattern in lowered],
        "reusable": [pattern for pattern in REUSABLE_PATTERNS if pattern in lowered],
    }

    if matched["sensitive"]:
        action = "ignore"
        reason = "Contiene senales de informacion sensible o secreto crudo."
    else:
        durable = bool(matched["durable"])
        reusable = bool(matched["reusable"])
        specific = len(text.strip()) >= 40 and any(token in lowered for token in (" porque ", " para ", " con ", " sin ", " al ", " ya que ", " debido "))
        tentative = bool(matched["tentative"])
        ephemeral = bool(matched["ephemeral"])
        kind = detect_checkpoint_kind(lowered)

        # Primary path: all four conditions met
        if durable and reusable and specific and not tentative:
            action = "store_directly"
            reason = "Parece durable, reutilizable, especifico y seguro de almacenar."
        # Secondary high-confidence path: resolved errors and decisions with substance
        elif _is_high_confidence_checkpoint(text, kind, tentative):
            action = "store_directly"
            reason = "Hallazgo de alta confianza: tipo reconocido, sustancial y conectado."
        elif tentative or ephemeral:
            action = "ask_user"
            reason = "Parece util, pero todavia ambiguo o temporal."
        else:
            action = "ignore"
            reason = "No aporta senal suficiente para guardarlo como conocimiento estable."

        matched["kind"] = kind

    return {
        "action": action,
        "reason": reason,
        "kind": matched.get("kind", detect_checkpoint_kind(lowered)),
        "matched_rules": matched,
    }


def _is_high_confidence_checkpoint(text: str, kind: str, tentative: bool) -> bool:
    """Secondary path for high-confidence findings that don't match all keyword conditions."""
    if kind not in ("resolved_error", "decision"):
        return False
    if tentative:
        return False
    # Must be substantial (60+ chars) and have a connector word
    is_substantial = len(text.strip()) >= 60
    lowered = text.lower()
    has_connector = any(token in lowered for token in (" porque ", " para ", " con ", " sin ", " ya que ", " debido ", " causa ", " solucion "))
    return is_substantial and has_connector


def detect_checkpoint_kind(lowered: str) -> str:
    if any(token in lowered for token in ("error", "bug", "resuelto", "solucion", "causa", "falla", "fix", "resolved")):
        return "resolved_error"
    if any(token in lowered for token in ("decid", "decision", "eleg", "choose", "chosen", "obligatorio", "siempre", "evitar")):
        return "decision"
    if any(token in lowered for token in ("paso", "procedimiento", "flujo", "configur", "workflow", "process")):
        return "workflow_improvement"
    if any(token in lowered for token in ("referencia", "link", "documentacion", "recurso", "doc ", "docs")):
        return "reference"
    return "analysis"


def build_checkpoint_summary(text: str, project_key: str) -> str:
    snippet = normalize_whitespace(text)
    return f"Checkpoint reusable para {project_key}: {snippet[:96]}"


def detect_topic_key(text: str) -> str | None:
    lowered = text.lower()
    for topic_key, patterns in TOPIC_PATTERNS.items():
        if any(pattern in lowered for pattern in patterns):
            return topic_key
    return None


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
