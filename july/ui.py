from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from threading import Timer
from urllib.parse import parse_qs, urlencode, quote
import webbrowser

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from july.cockpit import ProjectCockpitService, build_ui_base_url
from july.config import Settings, get_settings
from july.db import JulyDatabase
from july.project_conversation import ProjectConversationService


TEMPLATES_DIR = Path(__file__).with_name("templates")


def create_ui_app(settings: Settings | None = None) -> FastAPI:
    effective_settings = settings or get_settings()
    database = JulyDatabase(effective_settings)
    project_service = ProjectConversationService(database)
    cockpit_service = ProjectCockpitService(database, effective_settings, project_service)
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    app = FastAPI(title="July Project Cockpit")
    app.state.settings = effective_settings
    app.state.cockpit_service = cockpit_service
    app.state.templates = templates

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "projects": cockpit_service.list_recent_projects(limit=20),
                "base_url": build_ui_base_url(effective_settings),
                "notice": request.query_params.get("notice"),
                "error": request.query_params.get("error"),
            },
        )

    @app.post("/projects/open")
    async def open_project(request: Request) -> RedirectResponse:
        form = await parse_form_data(request)
        repo_path = form.get("repo_path") or None
        project_key = form.get("project_key") or None
        if not repo_path and not project_key:
            return redirect_with_message("/", error="Necesito un repo_path o un project_key para abrir el cockpit.")

        try:
            project = cockpit_service.open_project(repo_path=repo_path, project_key=project_key)
        except ValueError as exc:
            return redirect_with_message("/", error=str(exc))

        return redirect_with_message(
            project_path(project["project_key"]),
            notice=f"Cockpit listo para {project['project_key']}.",
        )

    @app.get("/projects/{project_key}", response_class=HTMLResponse)
    async def project_page(request: Request, project_key: str) -> HTMLResponse:
        try:
            cockpit = cockpit_service.build_cockpit(project_key=project_key, limit=10)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return templates.TemplateResponse(
            request,
            "project.html",
            {
                "cockpit": cockpit,
                "base_url": build_ui_base_url(effective_settings),
                "notice": request.query_params.get("notice"),
                "error": request.query_params.get("error"),
                "project_path": project_path(project_key),
            },
        )

    @app.post("/projects/{project_key}/review")
    async def review_project(request: Request, project_key: str) -> RedirectResponse:
        form = await parse_form_data(request)
        mode = form.get("mode", "resume_context")
        try:
            result = cockpit_service.review_project(project_key=project_key, mode=mode)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        return redirect_with_message(
            project_path(project_key),
            notice=summarize_review_result(result),
        )

    @app.post("/projects/{project_key}/notes/decision")
    async def save_decision(request: Request, project_key: str) -> RedirectResponse:
        form = await parse_form_data(request)
        text = (form.get("text") or "").strip()
        if not text:
            return redirect_with_message(project_path(project_key), error="La decision no puede estar vacia.")

        try:
            cockpit_service.save_decision(project_key=project_key, text=text)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        return redirect_with_message(project_path(project_key), notice="Decision guardada en July.")

    @app.post("/projects/{project_key}/notes/finding")
    async def save_finding(request: Request, project_key: str) -> RedirectResponse:
        form = await parse_form_data(request)
        text = (form.get("text") or "").strip()
        if not text:
            return redirect_with_message(project_path(project_key), error="El hallazgo no puede estar vacio.")

        try:
            cockpit_service.save_finding(project_key=project_key, text=text)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        return redirect_with_message(project_path(project_key), notice="Hallazgo guardado en July.")

    @app.post("/projects/{project_key}/tasks")
    async def create_task(request: Request, project_key: str) -> RedirectResponse:
        form = await parse_form_data(request)
        title = (form.get("title") or "").strip()
        details = (form.get("details") or "").strip() or None
        if not title:
            return redirect_with_message(project_path(project_key), error="El pendiente necesita un titulo.")

        try:
            cockpit_service.create_task(project_key=project_key, title=title, details=details)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        return redirect_with_message(project_path(project_key), notice="Pendiente creado.")

    @app.post("/projects/{project_key}/tasks/{task_id}/status")
    async def update_task_status(request: Request, project_key: str, task_id: int) -> RedirectResponse:
        form = await parse_form_data(request)
        status = form.get("status", "pending")
        try:
            cockpit_service.update_task_status(project_key=project_key, task_id=task_id, status=status)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        return redirect_with_message(project_path(project_key), notice=f"Pendiente actualizado a {status}.")

    @app.post("/projects/{project_key}/sessions/start")
    async def start_session(request: Request, project_key: str) -> RedirectResponse:
        form = await parse_form_data(request)
        goal = (form.get("goal") or "").strip() or None
        try:
            result = cockpit_service.start_session(project_key=project_key, goal=goal)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        notice = "Sesion reutilizada." if result["reused"] else "Sesion iniciada."
        return redirect_with_message(project_path(project_key), notice=notice)

    @app.post("/projects/{project_key}/sessions/summary")
    async def summarize_session(request: Request, project_key: str) -> RedirectResponse:
        form = await parse_form_data(request)
        summary = (form.get("summary") or "").strip()
        if not summary:
            return redirect_with_message(project_path(project_key), error="El resumen de sesion no puede estar vacio.")

        close_after_summary = form.get("close_after_summary") in {"1", "true", "on", "yes"}
        try:
            cockpit_service.prepare_next_session(
                project_key=project_key,
                summary=summary,
                discoveries=(form.get("discoveries") or "").strip() or None,
                accomplished=(form.get("accomplished") or "").strip() or None,
                next_steps=(form.get("next_steps") or "").strip() or None,
                relevant_files=(form.get("relevant_files") or "").strip() or None,
                close_after_summary=close_after_summary,
            )
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        notice = "Sesion resumida y cerrada." if close_after_summary else "Resumen de sesion guardado."
        return redirect_with_message(project_path(project_key), notice=notice)

    @app.post("/projects/{project_key}/sessions/end")
    async def end_session(project_key: str) -> RedirectResponse:
        try:
            cockpit_service.end_session(project_key=project_key)
        except ValueError as exc:
            return redirect_with_message(project_path(project_key), error=str(exc))

        return redirect_with_message(project_path(project_key), notice="Sesion cerrada.")

    return app


def run_ui_server(
    *,
    host: str | None = None,
    port: int | None = None,
    open_browser: bool = False,
) -> int:
    import uvicorn

    settings = get_settings()
    resolved_ui = replace(
        settings.ui,
        host=host or settings.ui.host,
        port=port or settings.ui.port,
    )
    resolved_settings = replace(settings, ui=resolved_ui)

    if open_browser:
        Timer(0.5, lambda: webbrowser.open(build_ui_base_url(resolved_settings))).start()

    uvicorn.run(
        create_ui_app(resolved_settings),
        host=resolved_ui.host,
        port=resolved_ui.port,
    )
    return 0


async def parse_form_data(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}


def project_path(project_key: str) -> str:
    return f"/projects/{quote(project_key)}"


def redirect_with_message(path: str, *, notice: str | None = None, error: str | None = None) -> RedirectResponse:
    params = {key: value for key, value in {"notice": notice, "error": error}.items() if value}
    url = path
    if params:
        url += "?" + urlencode(params)
    return RedirectResponse(url=url, status_code=303)


def summarize_review_result(result: dict[str, object]) -> str:
    action = result.get("action")
    if action == "resume_context":
        return str(result.get("message", "Contexto recuperado."))
    if action == "refresh_context":
        refresh_summary = result.get("refresh_summary")
        if isinstance(refresh_summary, dict):
            return str(refresh_summary.get("summary", "Contexto refrescado."))
        return "Contexto refrescado."
    if action == "analyze_now":
        nested = result.get("result")
        if isinstance(nested, dict):
            snapshot = nested.get("snapshot")
            if isinstance(snapshot, dict):
                return str(snapshot.get("summary", "Onboarding inicial completado."))
        return "Onboarding inicial completado."
    return str(result.get("message", "Accion ejecutada."))
