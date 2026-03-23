from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from july.cli import build_parser
from july.config import LLMSettings, Settings, UISettings
from july.db import JulyDatabase
from july.mcp import JulyMCPServer
from july.project_conversation import ProjectConversationService


def build_test_settings(db_path: Path) -> Settings:
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
            base_url=None,
        ),
    )


class ProjectConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "july-test.db"
        self.database = JulyDatabase(build_test_settings(self.db_path))
        self.service = ProjectConversationService(self.database)
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
            "import ExcelJS from 'exceljs';\nconsole.log('dashboard');\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_project_entry_returns_new_for_repo_without_context(self) -> None:
        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["project_key"], "dashboard-av")
        self.assertEqual(result["project_state"], "new")
        self.assertEqual(result["recommended_action"], "analyze_now")
        self.assertEqual(result["options"][0]["action"], "analyze_now")
        self.assertIsNotNone(result["permission_request"])

    def test_project_onboard_saves_snapshot_and_keeps_repo_read_only(self) -> None:
        readme_before = (self.repo_root / "README.md").read_text(encoding="utf-8")

        result = self.service.project_onboard(repo_path=str(self.repo_root), agent_name="codex-test", source="test")
        project_ctx = self.database.project_context("dashboard-av")
        sessions = self.database.session_context(project_key="dashboard-av")

        self.assertTrue(result["stored"]["memory_item_id"])
        self.assertEqual(result["session"]["ended"]["status"], "closed")
        self.assertEqual(len(project_ctx["memory"]), 1)
        self.assertEqual(len(sessions), 1)
        self.assertEqual((self.repo_root / "README.md").read_text(encoding="utf-8"), readme_before)

    def test_project_entry_returns_known_after_onboarding(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), source="test")

        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["project_state"], "known")
        self.assertEqual(result["recommended_action"], "resume_context")
        self.assertEqual(result["options"][0]["action"], "resume_context")

    def test_conversation_checkpoint_can_persist_clear_reusable_finding(self) -> None:
        result = self.service.conversation_checkpoint(
            "Decision: usar ExcelJS para exportaciones porque evita automatizaciones fragiles con COM.",
            repo_path=str(self.repo_root),
            persist=True,
            source="test",
        )

        self.assertEqual(result["action"], "store_directly")
        self.assertTrue(result["stored"]["memory_item_id"])

    def test_conversation_checkpoint_asks_for_tentative_note(self) -> None:
        result = self.service.conversation_checkpoint(
            "Quiz podria venir bien mover esto a otro modulo mas adelante.",
            repo_path=str(self.repo_root),
            source="test",
        )

        self.assertEqual(result["action"], "ask_user")
        self.assertIsNone(result["stored"])

    def test_project_action_analyze_now_delegates_to_onboarding(self) -> None:
        result = self.service.project_action("analyze_now", repo_path=str(self.repo_root), agent_name="codex-test")

        self.assertEqual(result["action"], "analyze_now")
        self.assertEqual(result["result"]["project_key"], "dashboard-av")
        self.assertTrue(result["result"]["stored"]["memory_item_id"])

    def test_project_action_continue_without_context_is_non_invasive(self) -> None:
        result = self.service.project_action("continue_without_context", repo_path=str(self.repo_root))

        self.assertEqual(result["action"], "continue_without_context")
        self.assertIn("sin releer ni guardar", result["message"])
        project_ctx = self.database.project_context("dashboard-av")
        self.assertEqual(project_ctx["memory"], [])


class ExposureTests(unittest.TestCase):
    def test_cli_parser_includes_project_commands(self) -> None:
        parser = build_parser()
        choices = parser._subparsers._group_actions[0].choices  # type: ignore[attr-defined]

        self.assertIn("project-entry", choices)
        self.assertIn("project-onboard", choices)
        self.assertIn("project-action", choices)
        self.assertIn("conversation-checkpoint", choices)
        self.assertIn("ui", choices)
        self.assertIn("ui-link", choices)

    def test_mcp_server_exposes_project_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = build_test_settings(Path(temp_dir) / "july-test.db")
            with patch("july.mcp.get_settings", return_value=settings):
                server = JulyMCPServer()

        self.assertIn("project_entry", server.tools)
        self.assertIn("project_onboard", server.tools)
        self.assertIn("project_action", server.tools)
        self.assertIn("conversation_checkpoint", server.tools)
        self.assertIn("project_ui_link", server.tools)


if __name__ == "__main__":
    unittest.main()
