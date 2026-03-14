from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from july.cli import build_parser
from july.config import LLMSettings, Settings
from july.db import JulyDatabase
from july.mcp import JulyMCPServer
from july.pipeline import apply_classification_overrides, create_capture_plan
from july.project_conversation import PROJECT_ACTIONS, ProjectConversationService


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
    )


class ProjectConversationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name) / "DemoRepo"
        self.repo_root.mkdir()
        (self.repo_root / "README.md").write_text(
            "# DemoRepo\n\nAplicacion de ejemplo para probar la capa conversacional de July.\n",
            encoding="utf-8",
        )
        (self.repo_root / "AGENTS.md").write_text("Reglas del repo de pruebas.\n", encoding="utf-8")
        (self.repo_root / "pyproject.toml").write_text(
            "[project]\nname='demo'\nversion='0.1.0'\n[project.scripts]\ndemo='demo:main'\n",
            encoding="utf-8",
        )
        (self.repo_root / "main.py").write_text("print('demo')\n", encoding="utf-8")
        (self.repo_root / "tests").mkdir()

        db_path = Path(self.temp_dir.name) / "july-test.db"
        self.database = JulyDatabase(build_test_settings(db_path))
        self.service = ProjectConversationService(self.database)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_project_entry_returns_new_for_repo_without_context(self) -> None:
        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["project_state"], "new")
        self.assertEqual(result["recommended_action"], "analyze_now")
        self.assertIn("nuevo para July", result["question"])
        self.assertTrue(all(option["id"] in PROJECT_ACTIONS for option in result["options"]))

    def test_project_entry_returns_partial_when_only_memory_exists(self) -> None:
        self._capture_project_note(
            "Decision tecnica para DemoRepo porque usaremos scripts simples y configuracion local.",
            project_key="DemoRepo",
        )

        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["project_state"], "partial")
        self.assertIn("contexto parcial", result["context_summary"])

    def test_project_onboard_saves_snapshot_and_keeps_repo_read_only(self) -> None:
        result = self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")

        self.assertEqual(result["project_key"], "DemoRepo")
        self.assertEqual(result["session"]["end"]["status"], "closed")
        self.assertTrue(result["storage"]["memory_item_id"])
        self.assertFalse((self.repo_root / "JULY_CONTEXT.md").exists())

        project_ctx = self.database.project_context("DemoRepo", limit=5)
        sessions = self.database.session_context(project_key="DemoRepo", limit=5)

        self.assertTrue(project_ctx["memory"])
        self.assertTrue(sessions)
        self.assertTrue((sessions[0]["summary"] or "").strip())

    def test_project_entry_returns_known_after_onboarding(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")

        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["project_state"], "known")
        self.assertEqual(result["recommended_action"], "resume_context")
        self.assertTrue(all(option["id"] in PROJECT_ACTIONS for option in result["options"]))

    def test_project_entry_warns_about_active_sessions(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")
        self.database.session_start(
            "demo-open-session",
            project_key="DemoRepo",
            agent_name="tests",
            goal="Continuar revision",
        )

        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["recommended_action"], "resume_context")
        self.assertEqual(result["context_signals"]["active_sessions"], 1)
        self.assertIn("sesion abierta", result["question"])
        self.assertEqual(result["active_sessions"][0]["session_key"], "demo-open-session")
        self.assertIsNotNone(result["active_session_warning"])

    def test_project_entry_recommends_closing_abandoned_sessions(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")
        self.database.session_start(
            "demo-abandoned-session",
            project_key="DemoRepo",
            agent_name="tests",
            goal="Sesion olvidada",
        )
        self._backdate_session("demo-abandoned-session", hours=30)

        result = self.service.project_entry(repo_path=str(self.repo_root))

        self.assertEqual(result["recommended_action"], "close_stale_and_continue")
        self.assertIn("abandonada", result["question"])
        self.assertIn("close_stale_and_continue", [option["id"] for option in result["options"]])

    def test_conversation_checkpoint_can_persist_clear_reusable_finding(self) -> None:
        result = self.service.conversation_checkpoint(
            "Decidimos usar MCP en DemoRepo porque evita duplicar logica y deja una sola interfaz para clientes.",
            repo_path=str(self.repo_root),
            persist=True,
        )

        self.assertEqual(result["action"], "store_directly")
        self.assertIn("stored", result)
        self.assertTrue(result["stored"]["memory_item_id"])

    def test_conversation_checkpoint_asks_for_tentative_note(self) -> None:
        result = self.service.conversation_checkpoint(
            "Idea temporal para DemoRepo: probar mas tarde otra estructura por si acaso.",
            repo_path=str(self.repo_root),
        )

        self.assertEqual(result["action"], "ask_user")
        self.assertIn("question", result)
        self.assertEqual(result["pending_confirmation"]["tool"], "conversation_checkpoint")
        self.assertTrue(result["pending_confirmation"]["arguments"]["persist"])
        self.assertNotIn("stored", result)

    def test_conversation_checkpoint_ignores_sensitive_note(self) -> None:
        result = self.service.conversation_checkpoint(
            "Guardar api_key=sk-test-123 para DemoRepo",
            repo_path=str(self.repo_root),
        )

        self.assertEqual(result["action"], "ignore")
        self.assertNotIn("stored", result)

    def test_conversation_checkpoint_confirm_override_persists_ask_user(self) -> None:
        """Block E: persist=True should override ask_user when agent has confirmed."""
        result = self.service.conversation_checkpoint(
            "Idea temporal para DemoRepo: probar mas tarde otra estructura por si acaso.",
            repo_path=str(self.repo_root),
            persist=True,
        )

        # Should be stored despite being tentative, because agent confirmed
        self.assertIn(result["action"], ("store_directly", "ask_user"))
        self.assertIn("stored", result)
        self.assertTrue(result["stored"]["memory_item_id"])
        self.assertTrue(result.get("persisted_via_confirmation", False))

    def test_conversation_checkpoint_confirm_never_overrides_ignore(self) -> None:
        """Block E: persist=True must NOT override ignore (sensitive data)."""
        result = self.service.conversation_checkpoint(
            "Guardar api_key=sk-test-123 para DemoRepo",
            repo_path=str(self.repo_root),
            persist=True,
        )

        self.assertEqual(result["action"], "ignore")
        self.assertNotIn("stored", result)

    def test_conversation_checkpoint_high_confidence_resolved_error(self) -> None:
        """Block F: resolved errors with substance should store directly (primary or secondary path)."""
        result = self.service.conversation_checkpoint(
            "Error resuelto: el MCP de Claude falla con SSE porque July usaba el transport incorrecto. La solucion fue configurar stdio explicitamente.",
            repo_path=str(self.repo_root),
        )

        self.assertEqual(result["action"], "store_directly")
        # Accept either primary path reason or or high-confidence path reason
        self.assertTrue(
            "alta confianza" in result["reason"] or "durable" in result["reason"] or "reutilizable" in result["reason"]
        )

    def test_conversation_checkpoint_high_confidence_decision(self) -> None:
        """Block F: decisions with substance should store directly (primary or secondary path)."""
        result = self.service.conversation_checkpoint(
            "Decision final para DemoRepo: usaremos Supabase en lugar de Firebase porque necesitamos Row Level Security y PostgREST para las APIs.",
            repo_path=str(self.repo_root),
        )

        self.assertEqual(result["action"], "store_directly")
        # Accept either path - what matters is that it stores directly
        self.assertTrue(
            "alta confianza" in result["reason"] or "durable" in result["reason"] or "reutilizable" in result["reason"]
        )

    def test_project_action_resume_context_starts_session(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")

        result = self.service.project_action(action="resume_context", repo_path=str(self.repo_root), agent_name="tests")

        self.assertEqual(result["project_key"], "DemoRepo")
        self.assertEqual(result["session"]["status"], "active")
        self.assertIn("context_summary", result)

    def test_project_action_resume_context_reuses_open_session(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")
        self.database.session_start(
            "demo-open-session",
            project_key="DemoRepo",
            agent_name="tests",
            goal="Retomar contexto",
        )
        before = self.database.session_context(project_key="DemoRepo", limit=10)

        result = self.service.project_action(action="resume_context", repo_path=str(self.repo_root), agent_name="tests")
        after = self.database.session_context(project_key="DemoRepo", limit=10)

        self.assertEqual(len(after), len(before))
        self.assertTrue(result["reused_existing_session"])
        self.assertEqual(result["session"]["status"], "already_active")
        self.assertEqual(result["session"]["session_key"], "demo-open-session")

    def test_project_action_invalid_action_does_not_create_session(self) -> None:
        before = self.database.session_context(project_key="DemoRepo", limit=10)

        with self.assertRaises(ValueError):
            self.service.project_action(action="invented_action", repo_path=str(self.repo_root), agent_name="tests")

        after = self.database.session_context(project_key="DemoRepo", limit=10)
        self.assertEqual(len(after), len(before))

    def test_project_action_close_stale_and_continue_closes_old_session(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")
        self.database.session_start(
            "demo-abandoned-session",
            project_key="DemoRepo",
            agent_name="tests",
            goal="Sesion olvidada",
        )
        self._backdate_session("demo-abandoned-session", hours=30)

        result = self.service.project_action(
            action="close_stale_and_continue",
            repo_path=str(self.repo_root),
            agent_name="tests",
        )

        closed_row = next(
            session for session in self.database.session_context(project_key="DemoRepo", limit=10)
            if session["session_key"] == "demo-abandoned-session"
        )
        self.assertEqual(closed_row["status"], "closed_without_summary")
        self.assertEqual(result["closed_sessions"][0]["session_key"], "demo-abandoned-session")
        self.assertEqual(result["session"]["status"], "active")

    def test_project_action_refresh_context_detects_stack_changes(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")
        (self.repo_root / "package.json").write_text('{"name":"demo","scripts":{"dev":"node main.py"}}\n', encoding="utf-8")

        result = self.service.project_action(
            action="refresh_context",
            repo_path=str(self.repo_root),
            agent_name="tests",
        )

        self.assertIn("Node.js", result["comparison"]["stack"]["added"])
        self.assertTrue(result["changes_detected"])
        self.assertTrue(result["comparison"]["has_changes"])

    def test_project_action_refresh_context_reuses_open_session(self) -> None:
        self.service.project_onboard(repo_path=str(self.repo_root), agent_name="tests")
        self.database.session_start(
            "demo-open-session",
            project_key="DemoRepo",
            agent_name="tests",
            goal="Refrescar contexto",
        )
        before = self.database.session_context(project_key="DemoRepo", limit=10)

        result = self.service.project_action(
            action="refresh_context",
            repo_path=str(self.repo_root),
            agent_name="tests",
        )
        after = self.database.session_context(project_key="DemoRepo", limit=10)

        self.assertEqual(len(after), len(before))
        self.assertEqual(result["session"]["status"], "already_active")
        self.assertEqual(result["session"]["session_key"], "demo-open-session")

    def _capture_project_note(self, text: str, *, project_key: str) -> None:
        plan = create_capture_plan(text)
        plan = apply_classification_overrides(
            text,
            plan,
            {
                "project_key": project_key,
                "status": "ready",
                "clarification_question": None,
                "normalized_summary": f"Nota util para {project_key}",
            },
        )
        plan["task"] = None
        self.database.capture(text, "tests", None, plan)

    def _backdate_session(self, session_key: str, *, hours: int) -> None:
        backdated = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        with self.database.connection() as conn:
            conn.execute(
                "UPDATE sessions SET started_at = ? WHERE session_key = ?",
                (backdated, session_key),
            )


class ExposureTests(unittest.TestCase):
    def test_cli_parser_includes_project_commands(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["project-entry", "--project-key", "DemoRepo"])
        self.assertEqual(args.command, "project-entry")

        args = parser.parse_args(["project-onboard", "--project-key", "DemoRepo"])
        self.assertEqual(args.command, "project-onboard")

        args = parser.parse_args(["conversation-checkpoint", "texto"])
        self.assertEqual(args.command, "conversation-checkpoint")

        args = parser.parse_args(["project-action", "resume_context"])
        self.assertEqual(args.command, "project-action")
        self.assertEqual(args.action, "resume_context")

        args = parser.parse_args(["project-action", "close_stale_and_continue"])
        self.assertEqual(args.action, "close_stale_and_continue")

    def test_mcp_server_exposes_project_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "july-test.db"
            settings = build_test_settings(db_path)
            with patch("july.mcp.get_settings", return_value=settings):
                server = JulyMCPServer()

            self.assertIn("project_entry", server.tools)
            self.assertIn("project_onboard", server.tools)
            self.assertIn("conversation_checkpoint", server.tools)
            self.assertIn("project_action", server.tools)
            self.assertEqual(server.tools["project_action"].input_schema["properties"]["action"]["enum"], list(PROJECT_ACTIONS))


if __name__ == "__main__":
    unittest.main()
