"""Tests for developer profile and level inference."""
from __future__ import annotations

import tempfile
from pathlib import Path

from july.config import Settings, LLMSettings, UISettings
from july.db import JulyDatabase


def _make_db() -> JulyDatabase:
    tmp = tempfile.mkdtemp()
    settings = Settings(
        db_path=Path(tmp) / "test.db",
        llm=LLMSettings(provider="none", model=None, api_key=None, base_url=None, timeout_seconds=30),
        ui=UISettings(host="127.0.0.1", port=4317, base_url=None),
    )
    return JulyDatabase(settings)


def test_ensure_creates_profile():
    db = _make_db()
    profile = db.ensure_developer_profile()
    assert profile["profile_key"] == "default"
    assert profile["inferred_level"] == "junior"
    assert profile["total_interactions"] == 0


def test_ensure_idempotent():
    db = _make_db()
    p1 = db.ensure_developer_profile()
    p2 = db.ensure_developer_profile()
    assert p1["id"] == p2["id"]


def test_record_interaction_increments():
    db = _make_db()
    db.record_developer_interaction("decision", complexity="basic")
    profile = db.get_developer_profile()
    assert profile["total_interactions"] == 1
    assert profile["decisions_count"] == 1


def test_record_architecture_question():
    db = _make_db()
    db.record_developer_interaction("architecture_question", detail="asked about layers")
    profile = db.get_developer_profile()
    assert profile["architecture_questions"] == 1


def test_level_stays_junior_initially():
    db = _make_db()
    result = db.record_developer_interaction("general")
    assert result["level"] == "junior"


def test_level_progresses_to_mid():
    db = _make_db()
    # Simulate enough interactions to reach mid
    for _ in range(10):
        db.record_developer_interaction("general")
    for _ in range(6):
        db.record_developer_interaction("decision", complexity="intermediate")
    for _ in range(4):
        db.record_developer_interaction("architecture_question")

    result = db.record_developer_interaction("general")
    assert result["level"] in ("mid", "senior")


def test_level_progresses_to_senior():
    db = _make_db()
    # Simulate extensive interactions
    for _ in range(50):
        db.record_developer_interaction("general")
    for _ in range(15):
        db.record_developer_interaction("decision", complexity="advanced")
    for _ in range(10):
        db.record_developer_interaction("architecture_question")
    for _ in range(10):
        db.record_developer_interaction("smell_fix")
    for _ in range(10):
        db.record_developer_interaction("pattern_apply")

    result = db.record_developer_interaction("general")
    assert result["level"] == "senior"


def test_get_developer_level_default():
    db = _make_db()
    level = db.get_developer_level()
    assert level == "junior"


def test_copilot_hint_junior():
    from july.project_conversation import build_copilot_hint
    architect = {
        "insights": [{"pattern": "MVC", "confidence": 0.7,
                       "detail": "Controllers y models", "suggestion": "Agrega services"}],
        "code_smells_count": 5,
        "proactive_questions": ["Quieres reorganizar?"],
        "suggestions": ["Separa en capas"],
    }
    hint = build_copilot_hint("junior", architect)
    assert "MVC" in hint
    assert "puntos de mejora" in hint


def test_copilot_hint_senior():
    from july.project_conversation import build_copilot_hint
    architect = {
        "insights": [{"pattern": "Clean", "confidence": 0.9,
                       "detail": "Capas ok", "suggestion": "Todo bien"}],
        "code_smells_count": 1,
        "proactive_questions": [],
        "suggestions": [],
    }
    hint = build_copilot_hint("senior", architect)
    assert "limpio" in hint.lower() or "flags" in hint.lower()
