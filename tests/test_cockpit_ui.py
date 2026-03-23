from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from july.config import LLMSettings, Settings, UISettings
from july.cockpit import ProjectCockpitService
from july.db import JulyDatabase
from july.project_conversation import ProjectConversationService
from july.ui import create_ui_app


def build_test_settings(db_path: Path, *, base_url: str | None = None) -> Settings:
    return Settings(
        db_path=db_path,
        llm=LLMSettings(
            provider="none",
            model=None,
            api_key=None,
            base_url=None,
            timeout_seconds=30,
        ),
        ui=UISettings(
            host="127.0.0.1",
            port=4317,
            base_url=base_url,
        ),
    )


class ProjectCockpitServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "july-test.db"
        self.settings = build_test_settings(self.db_path)
        self.database = JulyDatabase(self.settings)
        self.project_service = ProjectConversationService(self.database)
        self.cockpit = ProjectCockpitService(self.database, self.settings, self.project_service)
        self.repo_root = self.root / "Dashboard_AV"
        (self.repo_root / "src").mkdir(parents=True)
        (self.repo_root / "README.md").write_text(
            "# Dashboard AV\n\nAplicacion para revisar metricas y automatizar paneles.\n",
            encoding="utf-8",
        )
        (self.repo_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "dashboard-av",
                    "scripts": {"dev": "vite", "build": "vite build", "test": "vitest"},
                    "dependencies": {"exceljs": "^4.4.0"},
                }
            ),
            encoding="utf-8",
        )
        (self.repo_root / "src" / "index.ts").write_text(
            "console.log('dashboard');\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_open_project_registers_canonical_project(self) -> None:
        project = self.cockpit.open_project(repo_path=str(self.repo_root))
        projects = self.database.list_projects(limit=10)

        self.assertEqual(project["project_key"], "dashboard-av")
        self.assertEqual(projects[0]["repo_root"], str(self.repo_root.resolve()))

    def test_project_ui_link_works_without_repo_path_after_registration(self) -> None:
        self.cockpit.open_project(repo_path=str(self.repo_root))

        result = self.cockpit.project_ui_link(project_key="dashboard-av")

        self.assertEqual(result["project_key"], "dashboard-av")
        self.assertEqual(result["repo_root"], str(self.repo_root.resolve()))
        self.assertTrue(result["url"].endswith("/projects/dashboard-av"))

    def test_project_ui_link_uses_configured_base_url(self) -> None:
        settings = build_test_settings(self.db_path, base_url="http://127.0.0.1:9999/july")
        database = JulyDatabase(settings)
        cockpit = ProjectCockpitService(database, settings, ProjectConversationService(database))

        cockpit.open_project(repo_path=str(self.repo_root))
        result = cockpit.project_ui_link(project_key="dashboard-av")

        self.assertEqual(result["url"], "http://127.0.0.1:9999/july/projects/dashboard-av")

    def test_manual_task_can_be_created_and_updated(self) -> None:
        self.cockpit.open_project(repo_path=str(self.repo_root))

        created = self.cockpit.create_task(project_key="dashboard-av", title="Probar cockpit")
        updated = self.cockpit.update_task_status(
            project_key="dashboard-av",
            task_id=created["id"],
            status="done",
        )

        self.assertEqual(created["task_type"], "manual_follow_up")
        self.assertEqual(updated["status"], "done")

    def test_prepare_next_session_can_close_open_session(self) -> None:
        self.cockpit.open_project(repo_path=str(self.repo_root))
        self.cockpit.start_session(project_key="dashboard-av", goal="Validar cockpit")

        result = self.cockpit.prepare_next_session(
            project_key="dashboard-av",
            summary="Sesion cerrada desde cockpit",
            next_steps="Abrir la UI",
            close_after_summary=True,
        )

        self.assertEqual(result["summary"]["status"], "summarized")
        self.assertEqual(result["ended"]["status"], "closed")


class ProjectUIRoutesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "july-test.db"
        self.settings = build_test_settings(self.db_path, base_url="http://127.0.0.1:4317")
        self.repo_root = self.root / "Dashboard_AV"
        (self.repo_root / "src").mkdir(parents=True)
        (self.repo_root / "README.md").write_text(
            "# Dashboard AV\n\nAplicacion para revisar metricas y automatizar paneles.\n",
            encoding="utf-8",
        )
        (self.repo_root / "package.json").write_text(
            json.dumps({"name": "dashboard-av", "scripts": {"dev": "vite"}}),
            encoding="utf-8",
        )
        (self.repo_root / "src" / "index.ts").write_text("console.log('dashboard');\n", encoding="utf-8")
        self.app = create_ui_app(self.settings)
        self.client = TestClient(self.app)
        self.database = JulyDatabase(self.settings)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_home_page_renders(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("July Project Cockpit", response.text)
        self.assertIn("Abrir una consola de proyecto", response.text)

    def test_open_project_route_redirects_to_project_cockpit(self) -> None:
        response = self.client.post(
            "/projects/open",
            data={"repo_path": str(self.repo_root)},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertIn("/projects/dashboard-av", response.headers["location"])

    def test_project_page_supports_structured_writes(self) -> None:
        self.client.post("/projects/open", data={"repo_path": str(self.repo_root)}, follow_redirects=False)

        decision_response = self.client.post(
            "/projects/dashboard-av/notes/decision",
            data={"text": "Decision: usar cockpit local porque reduce ambiguedad."},
            follow_redirects=False,
        )
        task_response = self.client.post(
            "/projects/dashboard-av/tasks",
            data={"title": "Conectar deep links"},
            follow_redirects=False,
        )

        project_ctx = self.database.project_context("dashboard-av")

        self.assertEqual(decision_response.status_code, 303)
        self.assertEqual(task_response.status_code, 303)
        self.assertTrue(any(row["title"].startswith("Decision") for row in project_ctx["memory"]))
        self.assertTrue(any(row["title"] == "Conectar deep links" for row in project_ctx["tasks"]))

    def test_project_page_prioritizes_context_console(self) -> None:
        self.client.post("/projects/open", data={"repo_path": str(self.repo_root)}, follow_redirects=False)

        response = self.client.get("/projects/dashboard-av")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Timeline de contexto", response.text)
        self.assertIn("Acciones de escritura", response.text)
        self.assertIn("Guardar decision duradera", response.text)


if __name__ == "__main__":
    unittest.main()
