from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str | None
    api_key: str | None
    base_url: str | None
    timeout_seconds: int


@dataclass(frozen=True)
class Settings:
    db_path: Path
    llm: LLMSettings


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def resolve_env_value(name: str, env_file_values: dict[str, str], fallback: str | None = None) -> str | None:
    return env_file_values.get(name) or os.getenv(name) or fallback


def get_settings() -> Settings:
    env_file_values = load_env_file(Path.cwd() / ".env")

    env_path = resolve_env_value("JULY_DB_PATH", env_file_values)
    db_path = Path(env_path) if env_path else Path.cwd() / "data" / "july.db"
    llm_settings = LLMSettings(
        provider=resolve_env_value("JULY_LLM_PROVIDER", env_file_values, "none").strip().lower(),
        model=resolve_env_value("JULY_LLM_MODEL", env_file_values),
        api_key=resolve_env_value("JULY_LLM_API_KEY", env_file_values),
        base_url=resolve_env_value("JULY_LLM_BASE_URL", env_file_values),
        timeout_seconds=int(resolve_env_value("JULY_LLM_TIMEOUT", env_file_values, "30")),
    )
    return Settings(db_path=db_path, llm=llm_settings)
