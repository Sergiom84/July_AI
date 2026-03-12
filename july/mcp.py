from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable

from july.config import get_settings
from july.db import JulyDatabase
from july.llm import LLMProviderError, create_llm_provider
from july.pipeline import apply_classification_overrides, create_capture_plan

PROTOCOL_VERSION = "2025-03-26"


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
        self.initialized = False
        self.tools = self._build_tools()

    def _build_tools(self) -> dict[str, ToolSpec]:
        return {
            "capture_input": ToolSpec(
                name="capture_input",
                title="Capture Input",
                description="Capture a free-form input into July and optionally refine classification with the configured LLM.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Raw free-form input from the user."},
                        "source": {"type": "string", "description": "Source channel such as cli, telegram, email, or mcp."},
                        "source_ref": {"type": "string", "description": "Optional external message id or reference."},
                        "use_llm": {"type": "boolean", "description": "Whether to refine classification using the configured LLM."},
                        "dry_run": {"type": "boolean", "description": "When true, return the plan without saving it."},
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
                    "serverInfo": {"name": "July", "version": "0.1.0"},
                    "instructions": "July exposes memory capture, search, clarification, and project context tools.",
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

    def tool_capture_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_input = require_string(arguments, "text")
        source = arguments.get("source", "mcp")
        source_ref = arguments.get("source_ref")
        use_llm = bool(arguments.get("use_llm", False))
        dry_run = bool(arguments.get("dry_run", False))

        plan = create_capture_plan(raw_input)
        if use_llm:
            plan = self._maybe_enrich_capture_with_llm(raw_input, plan)
        if dry_run:
            return {"saved": False, "plan": plan}

        result = self.database.capture(raw_input, source, source_ref, plan)
        return {"saved": True, "result": result, "plan": plan}

    def tool_search_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = require_string(arguments, "query")
        limit = int(arguments.get("limit", 10))
        return rows_to_dicts(self.database.search(query, limit=limit))

    def tool_project_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        project_key = require_string(arguments, "project_key")
        limit = int(arguments.get("limit", 10))
        return rows_to_dicts(self.database.project_context(project_key, limit=limit))

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
