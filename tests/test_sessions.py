from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from july.config import LLMSettings, Settings
from july.db import JulyDatabase


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


class SessionLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "july-test.db"
        self.database = JulyDatabase(build_test_settings(db_path))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_session_summary_does_not_close_session(self) -> None:
        self.database.session_start("ses-summary")

        result = self.database.session_summary("ses-summary", summary="Resumen de prueba")
        row = self.database.get_record("sessions", 1)

        self.assertEqual(result["status"], "summarized")
        self.assertIn("summarized_at", result)
        self.assertEqual(row["status"], "summarized")
        self.assertEqual(row["summary"], "Resumen de prueba")
        self.assertIsNone(row["ended_at"])

    def test_session_end_after_summary_marks_session_closed(self) -> None:
        self.database.session_start("ses-close")
        self.database.session_summary("ses-close", summary="Resumen listo")

        result = self.database.session_end("ses-close")
        row = self.database.get_record("sessions", 1)

        self.assertEqual(result["status"], "closed")
        self.assertIsNotNone(result["ended_at"])
        self.assertEqual(row["status"], "closed")
        self.assertIsNotNone(row["ended_at"])

    def test_session_end_without_summary_marks_session_closed_without_summary(self) -> None:
        self.database.session_start("ses-no-summary")

        result = self.database.session_end("ses-no-summary")
        row = self.database.get_record("sessions", 1)

        self.assertEqual(result["status"], "closed_without_summary")
        self.assertEqual(row["status"], "closed_without_summary")
        self.assertIsNotNone(row["ended_at"])


if __name__ == "__main__":
    unittest.main()
