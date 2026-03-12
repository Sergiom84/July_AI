"""External reference sources for July.

July can consult external catalogs (skills.sh, agents.md, etc.) to suggest
skills, agents, patterns or tools that could benefit a project.
These are reference points — July creates its own implementations after reviewing them.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

KNOWN_SOURCES: dict[str, dict] = {
    "skills.sh": {
        "url": "https://skills.sh/",
        "name": "Skills.sh",
        "type": "skill_catalog",
        "description": "Catalog of reusable AI coding skills and prompts.",
    },
    "agents.md": {
        "url": "https://agents.md/#examples",
        "name": "Agents.md",
        "type": "agent_catalog",
        "description": "Reference examples of agent configurations and patterns.",
    },
}


def suggest_references_for_context(
    raw_input: str,
    project_key: str | None = None,
    intent: str | None = None,
) -> list[dict]:
    """Decide which external references might be useful for a given input.

    Returns a list of suggestion dicts with source_name, source_url, reason.
    This is a heuristic — it does not fetch the pages yet.
    """
    lowered = raw_input.lower()
    suggestions: list[dict] = []

    # Suggest skills.sh when the input involves creating reusable patterns,
    # architecture decisions, or project scaffolding
    skill_triggers = (
        "skill", "patron", "pattern", "plantilla", "template", "reutiliz",
        "workflow", "pipeline", "estructura", "scaffolding", "crear proyecto",
        "desde cero", "nuevo proyecto", "quiero hacer",
    )
    if any(t in lowered for t in skill_triggers) or intent in (
        "architecture_collaboration", "repository_onboarding",
    ):
        suggestions.append({
            "source_name": "Skills.sh",
            "source_url": "https://skills.sh/",
            "reference_type": "skill_catalog",
            "reason": (
                "Este input podria beneficiarse de una skill reutilizable. "
                "Consultar skills.sh para ver patrones existentes antes de crear uno propio."
            ),
        })

    # Suggest agents.md when the input involves agent configuration,
    # orchestration, or sub-agent creation
    agent_triggers = (
        "agent", "agente", "sub-agent", "orquest", "orchestr",
        "mcp", "automatiz", "delegar", "bot", "asistente",
    )
    if any(t in lowered for t in agent_triggers) or intent in (
        "architecture_collaboration", "external_analysis_import",
    ):
        suggestions.append({
            "source_name": "Agents.md",
            "source_url": "https://agents.md/#examples",
            "reference_type": "agent_catalog",
            "reason": (
                "Este input podria beneficiarse de un patron de agente. "
                "Consultar agents.md para ver ejemplos de configuracion y tomar referencia."
            ),
        })

    return suggestions


def fetch_reference_page(source_key: str, timeout: int = 15) -> dict:
    """Fetch a known external reference page and extract basic info.

    Returns a dict with title, description, raw_text_excerpt, fetch_status.
    """
    source = KNOWN_SOURCES.get(source_key)
    if source is None:
        return {"fetch_status": "unknown_source", "source_key": source_key}

    url = source["url"]
    result: dict = {
        "source_key": source_key,
        "url": url,
        "name": source["name"],
        "title": None,
        "description": source["description"],
        "raw_text_excerpt": None,
        "fetch_status": "pending",
    }

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            ctype = response.headers.get("Content-Type", "")
            if "text/html" not in ctype:
                result["fetch_status"] = "not_html"
                return result

            raw = response.read(256_000)
            body = raw.decode("utf-8", errors="replace")

            title_match = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
            if title_match:
                result["title"] = html.unescape(title_match.group(1)).strip()[:200]

            # Extract visible text
            text = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text).strip()
            result["raw_text_excerpt"] = text[:3000]

            result["fetch_status"] = "fetched"
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        result["fetch_status"] = f"error: {exc}"

    return result
