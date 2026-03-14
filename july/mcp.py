from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable

from july.config import get_settings
from july.db import JulyDatabase
from july.external_refs import fetch_reference_page, suggest_references_for_context
from july.llm import LLMProviderError, create_llm_provider
from july.pipeline import (
    apply_classification_overrides,
    create_capture_plan,
    enrich_plan_with_proactive_recall,
)
from july.project_conversation import PROJECT_ACTIONS, ProjectConversationService
from july.url_fetcher import fetch_url_metadata

PROTOCOL_VERSION = "2026-03-14"


@dataclass(slots=True)
class ToolSpec:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


class JulyMCPServer:
    def __init__(self) -> None:
        settings = get_settings()
        self.database = JulyDatabase(settings)
        self.llm_provider = create_llm_provider(settings.llm)
        self.project_service = ProjectConversationService(self.database)
        self.initialized = False
        self.tools = self._build_tools()

    def _build_tools(self) -> dict[str, ToolSpec]:
        return {
            "capture_input": ToolSpec(
                name="capture_input",
                title="Capture Input",
                description="Capture a free-form input into July with proactive recall and external reference suggestions.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Raw free-form input from the user."},
                        "source": {"type": "string", "description": "Source channel such as cli, telegram, email, or mcp."},
                        "source_ref": {"type": "string", "description": "Optional external message id or reference."},
                        "use_llm": {"type": "boolean", "description": "Whether to refine classification using the configured LLM."},
                        "dry_run": {"type": "boolean", "description": "When true, return the plan without saving it."},
                        "fetch_urls": {"type": "boolean", "description": "Fetch metadata for detected URLs."},
                        "model_name": {"type": "string", "description": "Name of the contributing model for traceability."},
                    },
                    "required": ["text"],
                },
                handler=self.tool_capture_input,
            ),
            "search_context": ToolSpec(
                name="search_context",
                title="Search Context",
                description="Search inbox, tasks, and memory items stored in July.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query."},
                        "limit": {"type": "integer", "description": "Maximum number of rows per section."},
                    },
                    "required": ["query"],
                },
                handler=self.tool_search_context,
            ),
            "project_context": ToolSpec(
                name="project_context",
                title="Project Context",
                description="Return inbox items, tasks, and memory linked to a project key.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string", "description": "Project key to inspect."},
                        "limit": {"type": "integer", "description": "Maximum rows per section."},
                    },
                    "required": ["project_key"],
                },
                handler=self.tool_project_context,
            ),
            "project_entry": ToolSpec(
                name="project_entry",
                title="Project Entry",
                description="Return the conversational opening state for a repository: project state, summary, greeting, and options.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string", "description": "Optional path inside the repository."},
                        "project_key": {"type": "string", "description": "Optional explicit project key override."},
                        "limit": {"type": "integer", "description": "Maximum amount of context to inspect."},
                    },
                },
                handler=self.tool_project_entry,
            ),
            "project_onboard": ToolSpec(
                name="project_onboard",
                title="Project Onboard",
                description="Run a read-only onboarding snapshot for a project and persist it using July sessions and memory.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "repo_path": {"type": "string"},
                        "project_key": {"type": "string"},
                        "session_key": {"type": "string"},
                        "agent_name": {"type": "string"},
                        "goal": {"type": "string"},
                    },
                },
                handler=self.tool_project_onboard,
            ),
            "conversation_checkpoint": ToolSpec(
                name="conversation_checkpoint",
                title="Conversation Checkpoint",
                description="Classify a conversational finding as store_directly, ask_user, or ignore, and optionally persist it. ask_user responses include a pending_confirmation payload for the agent.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Candidate finding, decision, or reusable note."},
                        "repo_path": {"type": "string"},
                        "project_key": {"type": "string"},
                        "persist": {"type": "boolean", "description": "Persist the checkpoint when it is safe to do so."},
                        "source": {"type": "string"},
                        "source_ref": {"type": "string"},
                        "model_name": {"type": "string"},
                    },
                    "required": ["text"],
                },
                handler=self.tool_conversation_checkpoint,
            ),
            "project_action": ToolSpec(
                name="project_action",
                title="Project Action",
                description="Execute a project action based on user's choice from project_entry. Actions: analyze_now, resume_context, refresh_context, continue_without_context, close_stale_and_continue.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": list(PROJECT_ACTIONS),
                            "description": "Action to execute: analyze_now, resume_context, refresh_context, continue_without_context, close_stale_and_continue",
                        },
                        "repo_path": {"type": "string"},
                        "project_key": {"type": "string"},
                        "agent_name": {"type": "string"},
                        "goal": {"type": "string"},
                    },
                    "required": ["action"],
                },
                handler=self.tool_project_action,
            ),
            "list_inbox": ToolSpec(
                name="list_inbox",
                title="List Inbox",
                description="List the latest inbox items captured by July.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "description": "Maximum number of inbox items."},
                    },
                },
                handler=self.tool_list_inbox,
            ),
            "clarify_input": ToolSpec(
                name="clarify_input",
                title="Clarify Input",
                description="Resolve a needs_clarification inbox item by providing the user's answer.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "inbox_item_id": {"type": "integer", "description": "Inbox item id to clarify."},
                        "answer": {"type": "string", "description": "Clarification answer from the user."},
                        "use_llm": {"type": "boolean", "description": "Whether to refine resolved classification using the configured LLM."},
                    },
                    "required": ["inbox_item_id", "answer"],
                },
                handler=self.tool_clarify_input,
            ),
            "promote_memory": ToolSpec(
                name="promote_memory",
                title="Promote Memory",
                description="Promote a candidate memory into stable ready memory, optionally refining it with the configured LLM.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "memory_item_id": {"type": "integer", "description": "Memory item id to promote."},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "knowledge": {"type": "string", "description": "Override distilled knowledge."},
                        "scope": {"type": "string", "enum": ["global", "project", "session"]},
                        "importance": {"type": "integer"},
                        "use_llm": {"type": "boolean"},
                    },
                    "required": ["memory_item_id"],
                },
                handler=self.tool_promote_memory,
            ),
            # ── Session protocol ─────────────────────────────
            "session_start": ToolSpec(
                name="session_start",
                title="Session Start",
                description="Start a new working session. Returns session id and status.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_key": {"type": "string", "description": "Unique session key."},
                        "project_key": {"type": "string"},
                        "agent_name": {"type": "string"},
                        "goal": {"type": "string"},
                    },
                    "required": ["session_key"],
                },
                handler=self.tool_session_start,
            ),
            "session_summary": ToolSpec(
                name="session_summary",
                title="Session Summary",
                description="Save a structured summary for the current session before closing it.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_key": {"type": "string"},
                        "summary": {"type": "string"},
                        "discoveries": {"type": "string"},
                        "accomplished": {"type": "string"},
                        "next_steps": {"type": "string"},
                        "relevant_files": {"type": "string"},
                    },
                    "required": ["session_key", "summary"],
                },
                handler=self.tool_session_summary,
            ),
            "session_end": ToolSpec(
                name="session_end",
                title="Session End",
                description="Close a session. If no summary was saved, it will be marked as closed_without_summary.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "session_key": {"type": "string"},
                    },
                    "required": ["session_key"],
                },
                handler=self.tool_session_end,
            ),
            "session_context": ToolSpec(
                name="session_context",
                title="Session Context",
                description="Recover context from recent sessions, optionally filtered by project.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                },
                handler=self.tool_session_context,
            ),
            # ── Topic keys ───────────────────────────────────
            "topic_create": ToolSpec(
                name="topic_create",
                title="Create Topic",
                description="Create a stable topic key for grouping related knowledge across sessions and projects.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic_key": {"type": "string", "description": "Stable key like 'auth/jwt-flow' or 'mcp/integration'."},
                        "label": {"type": "string"},
                        "domain": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["topic_key", "label"],
                },
                handler=self.tool_topic_create,
            ),
            "topic_link": ToolSpec(
                name="topic_link",
                title="Link to Topic",
                description="Link an inbox item, memory item, or session to a topic key.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic_key": {"type": "string"},
                        "inbox_item_id": {"type": "integer"},
                        "memory_item_id": {"type": "integer"},
                        "session_id": {"type": "integer"},
                    },
                    "required": ["topic_key"],
                },
                handler=self.tool_topic_link,
            ),
            "topic_context": ToolSpec(
                name="topic_context",
                title="Topic Context",
                description="Show everything linked to a topic key: memories, sessions, inbox items.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "topic_key": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["topic_key"],
                },
                handler=self.tool_topic_context,
            ),
            # ── Model contributions ──────────────────────────
            "save_model_contribution": ToolSpec(
                name="save_model_contribution",
                title="Save Model Contribution",
                description="Record a contribution (proposal, decision, analysis) from an AI model for traceability.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "model_name": {"type": "string"},
                        "contribution_type": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "project_key": {"type": "string"},
                        "domain": {"type": "string"},
                        "adopted": {"type": "boolean"},
                        "notes": {"type": "string"},
                    },
                    "required": ["model_name", "contribution_type", "title", "content"],
                },
                handler=self.tool_save_model_contribution,
            ),
            # ── URL fetch ────────────────────────────────────
            "fetch_url": ToolSpec(
                name="fetch_url",
                title="Fetch URL Metadata",
                description="Fetch title, description, and content from a URL. Special handling for YouTube.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "artifact_id": {"type": "integer"},
                    },
                    "required": ["url"],
                },
                handler=self.tool_fetch_url,
            ),
            # ── External references ──────────────────────────
            "fetch_reference": ToolSpec(
                name="fetch_reference",
                title="Fetch External Reference",
                description="Fetch content from a known reference source (skills.sh, agents.md) for inspiration.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source_key": {"type": "string", "enum": ["skills.sh", "agents.md"]},
                    },
                    "required": ["source_key"],
                },
                handler=self.tool_fetch_reference,
            ),
            # ── Proactive recall ─────────────────────────────
            "proactive_recall": ToolSpec(
                name="proactive_recall",
                title="Proactive Recall",
                description="Search memory proactively for related items. Returns memories, sessions, and suggestions.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Input text to find related knowledge."},
                        "project_key": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["text"],
                },
                handler=self.tool_proactive_recall,
            ),
        }

    def serve_stdio(self) -> int:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._emit_error(None, -32700, "Parse error")
                continue
            self._handle_message(request)
        return 0

    def _handle_message(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        message_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            self._emit_result(
                message_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "July", "version": "0.5.0"},
                    "instructions": (
                        "July exposes memory capture, project entry and onboarding, "
                        "conversation checkpoints, search, sessions, topic keys, "
                        "model traceability, URL fetching, external references, "
                        "proactive recall, and project context tools."
                    ),
                },
            )
            return

        if method == "notifications/initialized":
            self.initialized = True
            return

        if method == "ping":
            self._emit_result(message_id, {})
            return

        if method == "tools/list":
            self._emit_result(
                message_id,
                {
                    "tools": [
                        {
                            "name": tool.name,
                            "title": tool.title,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in self.tools.values()
                    ]
                },
            )
            return

        if method == "tools/call":
            self._handle_tool_call(message_id, params)
            return

        self._emit_error(message_id, -32601, f"Method not found: {method}")

    def _handle_tool_call(self, message_id: Any, params: dict[str, Any]) -> None:
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        tool = self.tools.get(tool_name)
        if tool is None:
            self._emit_error(message_id, -32602, f"Unknown tool: {tool_name}")
            return

        try:
            result = tool.handler(arguments)
            self._emit_result(
                message_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=True)}],
                    "structuredContent": result,
                },
            )
        except (ValueError, LLMProviderError) as exc:
            self._emit_result(
                message_id,
                {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            )
        except Exception as exc:  # pragma: no cover
            self._emit_result(
                message_id,
                {
                    "content": [{"type": "text", "text": f"Unexpected server error: {exc}"}],
                    "isError": True,
                },
            )

    def _emit_result(self, message_id: Any, result: dict[str, Any]) -> None:
        response = {"jsonrpc": "2.0", "id": message_id, "result": result}
        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()

    def _emit_error(self, message_id: Any, code: int, message: str) -> None:
        response = {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}
        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()

    # ── Tool handlers ────────────────────────────────────────

    def tool_capture_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_input = require_string(arguments, "text")
        source = arguments.get("source", "mcp")
        source_ref = arguments.get("source_ref")
        use_llm = bool(arguments.get("use_llm", False))
        dry_run = bool(arguments.get("dry_run", False))
        fetch_urls = bool(arguments.get("fetch_urls", False))
        model_name = arguments.get("model_name")

        plan = create_capture_plan(raw_input)
        if use_llm:
            plan = self._maybe_enrich_capture_with_llm(raw_input, plan)

        # Proactive recall
        project_key = plan["classification"].get("project_key")
        recall = self.database.proactive_recall(raw_input, project_key=project_key)
        plan = enrich_plan_with_proactive_recall(plan, recall)

        if dry_run:
            return {"saved": False, "plan": plan}

        result = self.database.capture(raw_input, source, source_ref, plan)

        # Fetch URL metadata
        if fetch_urls:
            for url in plan["context"].get("urls", []):
                meta = fetch_url_metadata(url)
                self.database.save_url_metadata(url, **{k: v for k, v in meta.items() if k != "url"})

        # Record model contribution
        if model_name:
            self.database.save_model_contribution(
                model_name=model_name,
                contribution_type="capture_input",
                title=plan["classification"]["normalized_summary"],
                content=raw_input,
                inbox_item_id=result["inbox_item_id"],
                project_key=project_key,
            )

        return {"saved": True, "result": result, "plan": plan}

    def tool_search_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = require_string(arguments, "query")
        limit = int(arguments.get("limit", 10))
        return rows_to_dicts(self.database.search(query, limit=limit))

    def tool_project_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        project_key = require_string(arguments, "project_key")
        limit = int(arguments.get("limit", 10))
        return rows_to_dicts(self.database.project_context(project_key, limit=limit))

    def tool_project_entry(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = int(arguments.get("limit", 5))
        return self.project_service.project_entry(
            repo_path=arguments.get("repo_path"),
            project_key=arguments.get("project_key"),
            limit=limit,
        )

    def tool_project_onboard(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.project_onboard(
            repo_path=arguments.get("repo_path"),
            project_key=arguments.get("project_key"),
            session_key=arguments.get("session_key"),
            agent_name=arguments.get("agent_name", "mcp"),
            goal=arguments.get("goal"),
        )

    def tool_conversation_checkpoint(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.conversation_checkpoint(
            require_string(arguments, "text"),
            repo_path=arguments.get("repo_path"),
            project_key=arguments.get("project_key"),
            source=arguments.get("source", "mcp_checkpoint"),
            source_ref=arguments.get("source_ref"),
            persist=bool(arguments.get("persist", False)),
            model_name=arguments.get("model_name"),
        )

    def tool_project_action(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.project_service.project_action(
            action=require_string(arguments, "action"),
            repo_path=arguments.get("repo_path"),
            project_key=arguments.get("project_key"),
            agent_name=arguments.get("agent_name", "mcp"),
            goal=arguments.get("goal"),
        )

    def tool_list_inbox(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = int(arguments.get("limit", 20))
        return {"items": [dict(row) for row in self.database.list_inbox(limit=limit)]}

    def tool_clarify_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        inbox_item_id = int(arguments["inbox_item_id"])
        answer = require_string(arguments, "answer")
        use_llm = bool(arguments.get("use_llm", False))

        inbox_item = self.database.get_record("inbox_items", inbox_item_id)
        if inbox_item is None:
            raise ValueError(f"Inbox item {inbox_item_id} not found")

        raw_input = inbox_item["raw_input"]
        plan = create_capture_plan(raw_input, clarification_answer=answer)
        if use_llm:
            plan = self._maybe_enrich_capture_with_llm(raw_input, plan, clarification_answer=answer)
        result = self.database.resolve_clarification(inbox_item_id, answer, plan)
        return {"resolved": True, "result": result, "plan": plan}

    def tool_promote_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        memory_item_id = int(arguments["memory_item_id"])
        memory_item = self.database.get_record("memory_items", memory_item_id)
        if memory_item is None:
            raise ValueError(f"Memory item {memory_item_id} not found")

        updates: dict[str, Any] = {}
        if bool(arguments.get("use_llm", False)):
            updates = self._maybe_draft_memory_with_llm(memory_item)

        promoted = self.database.promote_memory(
            memory_item_id,
            title=arguments.get("title") or updates.get("title"),
            summary=arguments.get("summary") or updates.get("summary"),
            distilled_knowledge=arguments.get("knowledge") or updates.get("distilled_knowledge"),
            scope=arguments.get("scope"),
            importance=arguments.get("importance"),
        )
        return {"promoted": True, "memory_item": dict(promoted)}

    def tool_session_start(self, arguments: dict[str, Any]) -> dict[str, Any]:
        session_key = require_string(arguments, "session_key")
        return self.database.session_start(
            session_key,
            project_key=arguments.get("project_key"),
            agent_name=arguments.get("agent_name"),
            goal=arguments.get("goal"),
        )

    def tool_session_summary(self, arguments: dict[str, Any]) -> dict[str, Any]:
        session_key = require_string(arguments, "session_key")
        summary = require_string(arguments, "summary")
        return self.database.session_summary(
            session_key,
            summary=summary,
            discoveries=arguments.get("discoveries"),
            accomplished=arguments.get("accomplished"),
            next_steps=arguments.get("next_steps"),
            relevant_files=arguments.get("relevant_files"),
        )

    def tool_session_end(self, arguments: dict[str, Any]) -> dict[str, Any]:
        session_key = require_string(arguments, "session_key")
        return self.database.session_end(session_key)

    def tool_session_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        project_key = arguments.get("project_key")
        limit = int(arguments.get("limit", 5))
        return {"sessions": self.database.session_context(project_key=project_key, limit=limit)}

    def tool_topic_create(self, arguments: dict[str, Any]) -> dict[str, Any]:
        topic_key = require_string(arguments, "topic_key")
        label = require_string(arguments, "label")
        domain = arguments.get("domain", "Programacion")
        description = arguments.get("description")
        return self.database.create_topic(topic_key, label, domain, description=description)

    def tool_topic_link(self, arguments: dict[str, Any]) -> dict[str, Any]:
        topic_key = require_string(arguments, "topic_key")
        return self.database.link_to_topic(
            topic_key,
            inbox_item_id=arguments.get("inbox_item_id"),
            memory_item_id=arguments.get("memory_item_id"),
            session_id=arguments.get("session_id"),
        )

    def tool_topic_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        topic_key = require_string(arguments, "topic_key")
        limit = int(arguments.get("limit", 20))
        return self.database.topic_context(topic_key, limit=limit)

    def tool_save_model_contribution(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.database.save_model_contribution(
            model_name=require_string(arguments, "model_name"),
            contribution_type=require_string(arguments, "contribution_type"),
            title=require_string(arguments, "title"),
            content=require_string(arguments, "content"),
            project_key=arguments.get("project_key"),
            domain=arguments.get("domain"),
            adopted=bool(arguments.get("adopted", False)),
            notes=arguments.get("notes"),
        )

    def tool_fetch_url(self, arguments: dict[str, Any]) -> dict[str, Any]:
        url = require_string(arguments, "url")
        artifact_id = arguments.get("artifact_id")
        meta = fetch_url_metadata(url)
        db_result = self.database.save_url_metadata(
            url,
            artifact_id=artifact_id,
            **{k: v for k, v in meta.items() if k not in ("url", "fetch_status")},
            fetch_status=meta["fetch_status"],
        )
        return {**meta, **db_result}

    def tool_fetch_reference(self, arguments: dict[str, Any]) -> dict[str, Any]:
        source_key = require_string(arguments, "source_key")
        return fetch_reference_page(source_key)

    def tool_proactive_recall(self, arguments: dict[str, Any]) -> dict[str, Any]:
        text = require_string(arguments, "text")
        project_key = arguments.get("project_key")
        limit = int(arguments.get("limit", 5))
        recall = self.database.proactive_recall(text, project_key=project_key, limit=limit)

        # Also add external reference suggestions
        ext_suggestions = suggest_references_for_context(text, project_key=project_key)
        recall["external_ref_suggestions"] = ext_suggestions
        return recall

    def _maybe_enrich_capture_with_llm(
        self,
        raw_input: str,
        plan: dict[str, Any],
        clarification_answer: str | None = None,
    ) -> dict[str, Any]:
        overrides = self.llm_provider.enrich_capture(raw_input, plan)
        if not overrides:
            return plan
        return apply_classification_overrides(raw_input, plan, overrides, clarification_answer=clarification_answer)

    def _maybe_draft_memory_with_llm(self, memory_item) -> dict[str, Any]:
        inbox_item_id = memory_item["inbox_item_id"]
        raw_input = ""
        if inbox_item_id:
            inbox_item = self.database.get_record("inbox_items", inbox_item_id)
            if inbox_item is not None:
                raw_input = inbox_item["raw_input"]
        return self.llm_provider.draft_memory(raw_input, dict(memory_item)) or {}


def require_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Argument '{key}' must be a non-empty string")
    return value.strip()


def rows_to_dicts(result: dict[str, Any]) -> dict[str, Any]:
    return {
        section: [dict(row) for row in rows]
        for section, rows in result.items()
    }


def main() -> int:
    server = JulyMCPServer()
    return server.serve_stdio()
