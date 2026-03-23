from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from july.analyzer import analyze_codebase
from july.db import JulyDatabase
from july.pipeline import apply_classification_overrides, create_capture_plan


README_NAMES = ("README.md", "README.txt", "README")
OPTIONAL_DOCS = ("AGENTS.md",)
MANIFEST_FILES = (
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
)
ENTRYPOINT_FILES = (
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "server.js",
    "app.js",
    "main.ts",
    "index.ts",
    "server.ts",
    "src/main.ts",
    "src/index.ts",
    "src/main.js",
    "src/index.js",
)

STACK_HINTS = {
    "python": "Python",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "pipfile": "Python",
    "package.json": "Node.js",
    "index.ts": "TypeScript",
    "main.ts": "TypeScript",
    "server.ts": "TypeScript",
    "cargo.toml": "Rust",
    "go.mod": "Go",
    "composer.json": "PHP",
    "gemfile": "Ruby",
    "dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
}

INTEGRATION_KEYWORDS = {
    "supabase": "Supabase",
    "render": "Render",
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "claude": "Anthropic",
    "ollama": "Ollama",
    "mcp": "MCP",
    "excel": "Excel",
    "google sheets": "Google Sheets",
    "stripe": "Stripe",
    "postgres": "Postgres",
    "sqlite": "SQLite",
    "docker": "Docker",
}

TOPIC_PATTERNS = {
    "mcp/integration": ("mcp", "model context protocol"),
    "auth/jwt-flow": ("jwt", "token", "refresh token"),
    "excel/automation": ("excel", "spreadsheet"),
    "repo/structure": ("arquitectura", "entrypoint", "estructura"),
}

SENSITIVE_PATTERNS = (
    "api key",
    "apikey",
    "secret",
    "password",
    "token=",
    "bearer ",
    "sk-",
    "sb_publishable_",
    "anon key",
)
TENTATIVE_PATTERNS = (
    "quiz",
    "tal vez",
    "igual",
    "puede que",
    "podria",
    "podriamos",
    "maybe",
    "might",
    "draft",
    "tentative",
)
DURABLE_PATTERNS = (
    "decision",
    "decid",
    "eleg",
    "usar",
    "obligatorio",
    "siempre",
    "evitar",
    "fix",
    "solucion",
    "resuelto",
    "resolv",
    "error",
    "configur",
    "workflow",
    "mcp",
)
REUSABLE_PATTERNS = (
    "porque",
    "para ",
    "para evitar",
    "para que",
    "con ",
    "sin ",
    "como ",
)


@dataclass(slots=True)
class RepositorySurface:
    repo_root: Path
    repo_name: str
    manifests: list[str]
    entrypoints: list[str]
    docs: list[str]
    stack: list[str]


class ProjectConversationService:
    def __init__(self, database: JulyDatabase) -> None:
        self.database = database

    def project_entry(
        self,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        repo_root, resolved_project_key = resolve_project_identity(self.database, repo_path=repo_path, project_key=project_key)
        self.database.upsert_project(
            resolved_project_key,
            str(repo_root),
            repo_name=repo_root.name,
        )
        surface = inspect_repository_surface(repo_root)
        project_ctx = self.database.project_context(resolved_project_key, limit=limit)
        sessions = self.database.session_context(project_key=resolved_project_key, limit=limit)
        project_state = assess_project_state(project_ctx, sessions)
        context_summary = build_context_summary(resolved_project_key, project_ctx, sessions, surface)
        recall = self.database.proactive_recall(
            build_recall_query(resolved_project_key, context_summary, surface),
            project_key=resolved_project_key,
            limit=3,
        )

        # Developer level for adaptive responses
        developer_level = self.database.get_developer_level()

        # Deep code analysis for proactive architect insights
        code_analysis = analyze_codebase(repo_root)
        architect = {
            "architecture_pattern": code_analysis.architecture_pattern,
            "insights": [
                {"pattern": i.pattern, "confidence": i.confidence,
                 "detail": i.detail, "suggestion": i.suggestion}
                for i in code_analysis.architecture_insights
            ],
            "code_smells_count": len(code_analysis.code_smells),
            "top_smells": [
                {"file": s.file, "kind": s.kind, "detail": s.detail, "severity": s.severity}
                for s in code_analysis.code_smells[:5]
            ],
            "proactive_questions": code_analysis.proactive_questions,
            "suggestions": code_analysis.suggestions,
            "languages": code_analysis.languages,
            "source_files": code_analysis.source_files,
        }

        return {
            "project_key": resolved_project_key,
            "repo_root": str(repo_root),
            "project_state": project_state,
            "context_summary": context_summary,
            "entry_message": build_entry_message(project_state, surface, context_summary),
            "permission_request": build_permission_request(project_state, surface),
            "recommended_action": recommended_action_for_state(project_state),
            "options": build_entry_options(project_state),
            "surface": {
                "repo_name": surface.repo_name,
                "docs": surface.docs,
                "manifests": surface.manifests,
                "entrypoints": surface.entrypoints,
                "stack": surface.stack,
            },
            "related_context": recall,
            "architect": architect,
            "developer_level": developer_level,
            "copilot_hint": build_copilot_hint(developer_level, architect),
        }

    def project_onboard(
        self,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        agent_name: str | None = None,
        source: str = "wizard",
    ) -> dict[str, Any]:
        repo_root, resolved_project_key = resolve_project_identity(self.database, repo_path=repo_path, project_key=project_key)
        self.database.upsert_project(
            resolved_project_key,
            str(repo_root),
            repo_name=repo_root.name,
        )
        analysis = analyze_repository(repo_root)
        session_key = build_session_key(resolved_project_key, prefix="onboard")

        session = self.database.session_start(
            session_key,
            project_key=resolved_project_key,
            agent_name=agent_name or "july",
            goal=f"Onboarding inicial de {resolved_project_key}",
        )

        snapshot_text = build_snapshot_text(resolved_project_key, analysis)
        plan = create_capture_plan(snapshot_text)
        plan = apply_classification_overrides(
            snapshot_text,
            plan,
            {
                "intent": "repository_onboarding",
                "confidence": 0.95,
                "status": "ready",
                "normalized_summary": f"Onboarding inicial de proyecto: {resolved_project_key}",
                "clarification_question": None,
                "domain": "Programacion",
                "project_key": resolved_project_key,
            },
        )
        plan["task"] = None
        plan["memory"] = {
            "memory_kind": "semantic",
            "title": f"Perfil inicial del proyecto {resolved_project_key}",
            "summary": build_snapshot_summary(analysis),
            "distilled_knowledge": build_distilled_knowledge(analysis),
            "domain": "Programacion",
            "scope": "project",
            "project_key": resolved_project_key,
            "importance": 4,
            "confidence": 0.95,
            "status": "ready",
        }
        capture_result = self.database.capture(snapshot_text, source, str(repo_root), plan)
        topic_link = self._maybe_link_topic(snapshot_text, capture_result["memory_item_id"])

        summary = f"Onboarding inicial completado para {resolved_project_key}."
        discoveries = build_snapshot_summary(analysis)
        next_steps = "; ".join(analysis["open_questions"]) if analysis["open_questions"] else suggest_next_step(analysis)
        relevant_files = ", ".join(analysis["files_read"])
        self.database.session_summary(
            session_key,
            summary=summary,
            discoveries=discoveries,
            next_steps=next_steps,
            relevant_files=relevant_files,
        )
        ended = self.database.session_end(session_key)

        return {
            "project_key": resolved_project_key,
            "repo_root": str(repo_root),
            "analysis": analysis,
            "snapshot": {
                "text": snapshot_text,
                "summary": build_snapshot_summary(analysis),
                "next_steps": next_steps,
            },
            "stored": capture_result,
            "session": {"started": session, "ended": ended, "session_key": session_key},
            "topic_link": topic_link,
        }

    def project_action(
        self,
        action: str,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        agent_name: str | None = None,
    ) -> dict[str, Any]:
        repo_root, resolved_project_key = resolve_project_identity(self.database, repo_path=repo_path, project_key=project_key)
        self.database.upsert_project(
            resolved_project_key,
            str(repo_root),
            repo_name=repo_root.name,
        )
        entry = self.project_entry(repo_path=str(repo_root), project_key=resolved_project_key)

        if action == "analyze_now":
            return {
                "action": action,
                "project_key": resolved_project_key,
                "result": self.project_onboard(
                    repo_path=str(repo_root),
                    project_key=resolved_project_key,
                    agent_name=agent_name,
                ),
            }

        if action == "resume_context":
            return {
                "action": action,
                "project_key": resolved_project_key,
                "message": (
                    f"Este proyecto ya tiene contexto util en July. "
                    f"{entry['context_summary']}"
                ),
                "next_step": extract_next_step(entry["related_context"], entry["context_summary"]),
            }

        if action == "refresh_context":
            analysis = analyze_repository(repo_root)
            comparison = compare_repository_with_context(analysis, entry["context_summary"])
            return {
                "action": action,
                "project_key": resolved_project_key,
                "message": (
                    "He hecho una revision selectiva y superficial del repo para refrescar el contexto."
                ),
                "refresh_summary": comparison,
                "analysis": analysis,
            }

        if action == "continue_without_context":
            return {
                "action": action,
                "project_key": resolved_project_key,
                "message": (
                    "Sigo contigo sin releer ni guardar nada ahora mismo. "
                    "Si encuentro una decision reutilizable, te preguntare si quieres guardarla."
                ),
            }

        if action == "wait":
            return {
                "action": action,
                "project_key": resolved_project_key,
                "message": "Perfecto. Espero y no analizo el repo todavia.",
            }

        if action == "do_nothing":
            return {
                "action": action,
                "project_key": resolved_project_key,
                "message": "No hago nada por ahora.",
            }

        raise ValueError(f"Unsupported project action: {action}")

    def conversation_checkpoint(
        self,
        text: str,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        persist: bool = False,
        source: str = "wizard",
    ) -> dict[str, Any]:
        repo_root, resolved_project_key = resolve_project_identity(self.database, repo_path=repo_path, project_key=project_key)
        self.database.upsert_project(
            resolved_project_key,
            str(repo_root),
            repo_name=repo_root.name,
        )
        action, reason, kind = classify_checkpoint(text)

        stored = None
        confirmation_applied = False
        effective_action = action
        if action == "ask_user" and persist:
            effective_action = "store_directly"
            confirmation_applied = True

        if effective_action == "store_directly":
            stored = self._store_checkpoint(text, resolved_project_key, kind, source)

        return {
            "project_key": resolved_project_key,
            "action": effective_action,
            "reason": reason if not confirmation_applied else f"{reason} Confirmacion aplicada por el agente.",
            "kind": kind,
            "stored": stored,
            "confirmation_applied": confirmation_applied,
        }

    def save_decision(
        self,
        text: str,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        source: str = "ui",
    ) -> dict[str, Any]:
        repo_root, resolved_project_key = resolve_project_identity(self.database, repo_path=repo_path, project_key=project_key)
        self.database.upsert_project(
            resolved_project_key,
            str(repo_root),
            repo_name=repo_root.name,
        )
        stored = self._store_checkpoint(text, resolved_project_key, "decision", source)
        return {
            "project_key": resolved_project_key,
            "action": "store_directly",
            "reason": "Decision estructurada guardada desde una accion explicita.",
            "kind": "decision",
            "stored": stored,
        }

    def save_finding(
        self,
        text: str,
        *,
        repo_path: str | None = None,
        project_key: str | None = None,
        source: str = "ui",
    ) -> dict[str, Any]:
        repo_root, resolved_project_key = resolve_project_identity(self.database, repo_path=repo_path, project_key=project_key)
        self.database.upsert_project(
            resolved_project_key,
            str(repo_root),
            repo_name=repo_root.name,
        )
        stored = self._store_checkpoint(text, resolved_project_key, "finding", source)
        return {
            "project_key": resolved_project_key,
            "action": "store_directly",
            "reason": "Hallazgo estructurado guardado desde una accion explicita.",
            "kind": "finding",
            "stored": stored,
        }

    def _store_checkpoint(self, text: str, project_key: str, kind: str, source: str) -> dict[str, Any]:
        plan = create_capture_plan(text)
        plan = apply_classification_overrides(
            text,
            plan,
            {
                "intent": "general_note",
                "confidence": 0.93,
                "status": "ready",
                "normalized_summary": build_checkpoint_title(text, kind),
                "clarification_question": None,
                "domain": "Programacion",
                "project_key": project_key,
            },
        )
        plan["task"] = None
        plan["memory"] = {
            "memory_kind": "procedural" if kind in {"decision", "resolved_error", "workflow"} else "semantic",
            "title": build_checkpoint_title(text, kind),
            "summary": summarize_text(text, limit=160),
            "distilled_knowledge": text[:400],
            "domain": "Programacion",
            "scope": "project",
            "project_key": project_key,
            "importance": 3,
            "confidence": 0.93,
            "status": "ready",
        }
        result = self.database.capture(text, source, project_key, plan)
        topic_link = self._maybe_link_topic(text, result["memory_item_id"])
        result["topic_link"] = topic_link
        return result

    def _maybe_link_topic(self, text: str, memory_item_id: int | None) -> dict[str, Any] | None:
        if not memory_item_id:
            return None

        lowered = text.lower()
        for topic_key, patterns in TOPIC_PATTERNS.items():
            if any(pattern in lowered for pattern in patterns):
                self.database.create_topic(topic_key, topic_key.split("/")[-1].replace("-", " ").title(), "Programacion")
                return self.database.link_to_topic(topic_key, memory_item_id=memory_item_id)
        return None


def detect_repo_root(repo_path: str | None) -> Path:
    start = Path(repo_path).expanduser().resolve() if repo_path else Path.cwd().resolve()
    current = start if start.is_dir() else start.parent

    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
        if any((candidate / name).exists() for name in README_NAMES + MANIFEST_FILES + OPTIONAL_DOCS):
            return candidate
    return current


def derive_project_key(repo_root: Path, *, explicit: str | None = None) -> str:
    value = explicit or repo_root.name
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


def resolve_project_identity(
    database: JulyDatabase,
    *,
    repo_path: str | None = None,
    project_key: str | None = None,
) -> tuple[Path, str]:
    explicit_key = project_key.strip().lower() if isinstance(project_key, str) and project_key.strip() else None
    if explicit_key and not repo_path:
        existing = database.get_project(explicit_key)
        if existing is None:
            raise ValueError(
                f"Project {explicit_key} not found in the registry. Provide repo_path to register it first."
            )
        return Path(existing["repo_root"]).resolve(), explicit_key

    repo_root = detect_repo_root(repo_path)
    resolved_project_key = derive_project_key(repo_root, explicit=project_key)
    existing = database.get_project(resolved_project_key)
    if existing is not None and not repo_path:
        return Path(existing["repo_root"]).resolve(), resolved_project_key
    return repo_root, resolved_project_key


def inspect_repository_surface(repo_root: Path) -> RepositorySurface:
    names = {path.name.lower(): path.name for path in repo_root.iterdir() if path.is_file()}
    manifests = [names[name.lower()] for name in MANIFEST_FILES if name.lower() in names]
    docs = [names[name.lower()] for name in README_NAMES + OPTIONAL_DOCS if name.lower() in names]
    entrypoints = []
    for relative in ENTRYPOINT_FILES:
        candidate = repo_root / relative
        if candidate.exists():
            entrypoints.append(relative)

    stack = sorted({hint for name, hint in STACK_HINTS.items() if name in names or name in [ep.lower() for ep in entrypoints]})
    return RepositorySurface(
        repo_root=repo_root,
        repo_name=repo_root.name,
        manifests=manifests,
        entrypoints=entrypoints,
        docs=docs,
        stack=stack,
    )


def analyze_repository(repo_root: Path) -> dict[str, Any]:
    surface = inspect_repository_surface(repo_root)
    files_to_read = []
    for name in README_NAMES + OPTIONAL_DOCS + MANIFEST_FILES:
        candidate = repo_root / name
        if candidate.exists():
            files_to_read.append(candidate)
    for relative in ENTRYPOINT_FILES:
        candidate = repo_root / relative
        if candidate.exists():
            files_to_read.append(candidate)

    unique_files = []
    seen: set[Path] = set()
    for path in files_to_read:
        if path not in seen:
            unique_files.append(path)
            seen.add(path)

    file_contents = {str(path.relative_to(repo_root)): read_limited_text(path) for path in unique_files[:12]}
    combined_text = "\n".join(file_contents.values()).lower()

    package_commands = extract_package_commands(repo_root / "package.json")
    visible_commands = package_commands or infer_default_commands(surface)
    integrations = detect_integrations(combined_text)
    objective = extract_objective(file_contents)
    open_questions = build_open_questions(surface, objective, visible_commands)

    return {
        "repo_name": surface.repo_name,
        "repo_root": str(repo_root),
        "files_read": list(file_contents.keys()),
        "objective": objective,
        "stack": surface.stack or ["No detectado"],
        "commands": visible_commands,
        "integrations": integrations,
        "entrypoints": surface.entrypoints,
        "open_questions": open_questions,
        "docs": surface.docs,
        "manifests": surface.manifests,
    }


def read_limited_text(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def extract_package_commands(package_json_path: Path) -> list[str]:
    if not package_json_path.exists():
        return []
    try:
        data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    scripts = data.get("scripts", {})
    commands = []
    for name in ("dev", "start", "build", "test", "lint"):
        if name in scripts:
            commands.append(f"npm run {name}")
    return commands


def infer_default_commands(surface: RepositorySurface) -> list[str]:
    commands = []
    if "package.json" in surface.manifests:
        commands.extend(["npm install", "npm run dev"])
    if any(item in surface.manifests for item in ("pyproject.toml", "requirements.txt", "Pipfile")):
        commands.extend(["python -m venv .venv", "python -m pytest"])
    return commands or ["Revisar README para comandos concretos"]


def detect_integrations(text: str) -> list[str]:
    return sorted({label for keyword, label in INTEGRATION_KEYWORDS.items() if keyword in text})


def extract_objective(file_contents: dict[str, str]) -> str:
    for name, content in file_contents.items():
        if name.lower().startswith("readme") and content.strip():
            lines = [line.strip(" #*-") for line in content.splitlines() if line.strip()]
            for line in lines:
                if len(line) > 20:
                    return summarize_text(line, limit=220)
    return "No hay una descripcion explicita; conviene confirmar el objetivo del repo."


def build_open_questions(surface: RepositorySurface, objective: str, commands: list[str]) -> list[str]:
    questions = []
    if not surface.docs:
        questions.append("Falta README o documentacion base visible.")
    if not surface.entrypoints:
        questions.append("No he detectado entrypoints obvios en superficie.")
    if objective.startswith("No hay una descripcion"):
        questions.append("Conviene confirmar el objetivo funcional del proyecto.")
    if not commands:
        questions.append("No hay comandos utiles detectados todavia.")
    return questions


def assess_project_state(project_ctx: dict[str, list[Any]], sessions: list[dict[str, Any]]) -> str:
    has_ready_memory = any(row["status"] == "ready" for row in project_ctx["memory"])
    has_session_summary = any(
        (session.get("summary") or session.get("discoveries") or session.get("next_steps")) for session in sessions
    )
    has_any_context = any(project_ctx[section] for section in ("inbox", "tasks", "memory")) or bool(sessions)

    if has_ready_memory and has_session_summary:
        return "known"
    if has_any_context:
        return "partial"
    return "new"


def build_context_summary(
    project_key: str,
    project_ctx: dict[str, list[Any]],
    sessions: list[dict[str, Any]],
    surface: RepositorySurface,
) -> str:
    if not any(project_ctx[section] for section in ("inbox", "tasks", "memory")) and not sessions:
        stack = ", ".join(surface.stack) if surface.stack else "stack no detectado"
        return f"No tengo contexto persistido de {project_key} todavia. En superficie parece un repo de {stack}."

    latest_memory = project_ctx["memory"][0]["summary"] if project_ctx["memory"] else None
    latest_session = sessions[0] if sessions else None
    parts = [f"July ya tiene algo de contexto para {project_key}."]
    if latest_memory:
        parts.append(f"Ultima memoria util: {latest_memory}")
    if latest_session and latest_session.get("summary"):
        parts.append(f"Ultima sesion: {latest_session['summary']}")
    if latest_session and latest_session.get("next_steps"):
        parts.append(f"Siguiente paso conocido: {latest_session['next_steps']}")
    return " ".join(parts)


def build_recall_query(project_key: str, context_summary: str, surface: RepositorySurface) -> str:
    terms = [project_key, context_summary, surface.repo_name]
    terms.extend(surface.stack[:3])
    terms.extend(surface.manifests[:2])
    return " ".join(term for term in terms if term)


def build_entry_message(project_state: str, surface: RepositorySurface, context_summary: str) -> str:
    if project_state == "new":
        stack = ", ".join(surface.stack) if surface.stack else "stack no detectado"
        return (
            f"Proyecto nuevo para July. Veo un repo llamado {surface.repo_name} "
            f"y en superficie parece usar {stack}. "
            "Si se ejecuta analyze_now, July leera documentacion y entrypoints en modo solo lectura "
            "para dejar una primera foto util."
        )
    if project_state == "known":
        return f"Proyecto conocido en July. {context_summary}"
    return (
        f"Contexto parcial de {surface.repo_name}. "
        f"{context_summary} Si quieres, hago un refresh selectivo antes de continuar."
    )


def build_permission_request(project_state: str, surface: RepositorySurface) -> dict[str, Any] | None:
    if project_state != "new":
        return None
    return {
        "action": "analyze_now",
        "mode": "read_only",
        "message": (
            "Voy a leer README, manifiestos y entrypoints visibles para darte mejores practicas "
            "y guardar una primera foto del proyecto. Quieres que lo haga ahora?"
        ),
        "files_hint": surface.docs + surface.manifests + surface.entrypoints[:4],
    }


def recommended_action_for_state(project_state: str) -> str:
    if project_state == "new":
        return "analyze_now"
    if project_state == "known":
        return "resume_context"
    return "refresh_context"


def build_entry_options(project_state: str) -> list[dict[str, str]]:
    if project_state == "new":
        return [
            {"action": "analyze_now", "label": "Si, analiza ahora"},
            {"action": "wait", "label": "Prefiero esperar"},
            {"action": "do_nothing", "label": "No hagas nada"},
        ]
    if project_state == "known":
        return [
            {"action": "resume_context", "label": "Resume el contexto"},
            {"action": "refresh_context", "label": "Refresca el contexto"},
            {"action": "continue_without_context", "label": "Seguimos sin refresco"},
        ]
    return [
        {"action": "refresh_context", "label": "Refresca el contexto"},
        {"action": "analyze_now", "label": "Haz onboarding completo"},
        {"action": "continue_without_context", "label": "Seguimos asi"},
    ]


def build_snapshot_text(project_key: str, analysis: dict[str, Any]) -> str:
    return (
        f"Onboarding inicial del proyecto {project_key}.\n"
        f"Objetivo visible: {analysis['objective']}\n"
        f"Stack visible: {', '.join(analysis['stack'])}\n"
        f"Comandos utiles: {', '.join(analysis['commands'])}\n"
        f"Integraciones importantes: {', '.join(analysis['integrations']) or 'ninguna detectada'}\n"
        f"Entrypoints visibles: {', '.join(analysis['entrypoints']) or 'ninguno detectado'}\n"
        f"Dudas abiertas: {', '.join(analysis['open_questions']) or 'ninguna critica'}"
    )


def build_snapshot_summary(analysis: dict[str, Any]) -> str:
    return (
        f"Objetivo: {analysis['objective']} "
        f"Stack: {', '.join(analysis['stack'])}. "
        f"Integraciones: {', '.join(analysis['integrations']) or 'ninguna detectada'}. "
        f"Entrypoints: {', '.join(analysis['entrypoints']) or 'ninguno detectado'}."
    )


def build_distilled_knowledge(analysis: dict[str, Any]) -> str:
    return (
        f"El proyecto parece orientado a {analysis['objective']} "
        f"y trabaja con {', '.join(analysis['stack'])}. "
        f"Los comandos mas utiles detectados ahora son {', '.join(analysis['commands'])}. "
        f"Las dudas abiertas principales son: {', '.join(analysis['open_questions']) or 'ninguna critica'}."
    )


def suggest_next_step(analysis: dict[str, Any]) -> str:
    if analysis["open_questions"]:
        return analysis["open_questions"][0]
    if analysis["commands"]:
        return f"Probar el flujo principal con {analysis['commands'][0]}."
    return "Confirmar el objetivo y el siguiente bloque de trabajo con el usuario."


def build_session_key(project_key: str, *, prefix: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    return f"{prefix}-{project_key}-{timestamp}"


def compare_repository_with_context(analysis: dict[str, Any], context_summary: str) -> dict[str, Any]:
    lowered = context_summary.lower()
    changes = []
    for item in analysis["stack"]:
        if item.lower() not in lowered:
            changes.append(f"Stack visible no mencionado antes: {item}")
    for item in analysis["integrations"]:
        if item.lower() not in lowered:
            changes.append(f"Integracion visible no mencionada antes: {item}")
    for item in analysis["entrypoints"]:
        if item.lower() not in lowered:
            changes.append(f"Entrypoint visible no mencionado antes: {item}")
    if not changes:
        changes.append("No veo diferencias fuertes en stack, integraciones o entrypoints frente al contexto previo.")
    return {"changes": changes, "summary": " ".join(changes[:3])}


def classify_checkpoint(text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    if any(pattern in lowered for pattern in SENSITIVE_PATTERNS):
        return "ignore", "Contiene datos sensibles o credenciales. No conviene guardarlo.", "sensitive"

    tentative = any(pattern in lowered for pattern in TENTATIVE_PATTERNS)
    durable = any(pattern in lowered for pattern in DURABLE_PATTERNS)
    reusable = any(pattern in lowered for pattern in REUSABLE_PATTERNS)
    kind = detect_checkpoint_kind(lowered)

    if durable and reusable and len(text.strip()) >= 40 and not tentative:
        return "store_directly", "Parece durable, reutilizable, especifico y seguro de almacenar.", kind
    if tentative:
        return "ask_user", "Hay senal util, pero todavia suena tentativo o ambiguo.", kind
    return "ask_user", "Puede ser util, pero necesito confirmacion antes de guardarlo.", kind


def detect_checkpoint_kind(lowered: str) -> str:
    if any(token in lowered for token in ("decision", "decid", "eleg", "usar", "evitar")):
        return "decision"
    if any(token in lowered for token in ("error", "fix", "resuelto", "resolv", "solucion")):
        return "resolved_error"
    if any(token in lowered for token in ("workflow", "paso", "flujo", "script", "automat")):
        return "workflow"
    return "finding"


def build_checkpoint_title(text: str, kind: str) -> str:
    prefixes = {
        "decision": "Decision reutilizable",
        "resolved_error": "Error resuelto",
        "workflow": "Mejora de flujo",
        "finding": "Hallazgo reusable",
    }
    return f"{prefixes.get(kind, 'Hallazgo')}: {summarize_text(text, limit=80)}"


def summarize_text(text: str, *, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def extract_next_step(recall: dict[str, Any], context_summary: str) -> str:
    related_sessions = recall.get("related_sessions", [])
    if related_sessions:
        next_steps = related_sessions[0].get("next_steps")
        if next_steps:
            return next_steps
    return context_summary


def build_copilot_hint(developer_level: str, architect: dict[str, Any]) -> str:
    """Build an adaptive hint based on developer level and architecture analysis."""
    smells_count = architect.get("code_smells_count", 0)
    insights = architect.get("insights", [])
    questions = architect.get("proactive_questions", [])
    suggestions = architect.get("suggestions", [])

    if developer_level == "junior":
        parts = []
        if insights:
            best = insights[0]
            parts.append(
                f"Tu proyecto sigue un patron de {best['pattern']}. "
                f"{best['suggestion']}"
            )
        if smells_count > 0:
            parts.append(
                f"He encontrado {smells_count} puntos de mejora en el codigo. "
                "Te los explico uno a uno si quieres."
            )
        if suggestions:
            parts.append(f"Consejo: {suggestions[0]}")
        return " ".join(parts) if parts else "Proyecto analizado. Preguntame lo que necesites."

    if developer_level == "mid":
        parts = []
        if insights:
            for i in insights[:2]:
                parts.append(f"[{i['pattern']}] {i['detail']}")
        if smells_count > 3:
            parts.append(f"{smells_count} code smells detectados. Los mas criticos primero?")
        if questions:
            parts.append(questions[0])
        return " ".join(parts) if parts else "Analisis completo. Dime en que quieres profundizar."

    # senior
    parts = []
    if smells_count > 5:
        parts.append(f"{smells_count} smells. Revisa los criticos.")
    if insights:
        for i in insights:
            if i["confidence"] < 0.8:
                parts.append(f"Patron ambiguo: {i['pattern']} ({i['confidence']:.0%})")
    if not parts:
        parts.append("Codigo limpio. Sin flags criticos.")
    return " ".join(parts)
