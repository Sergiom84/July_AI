from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from july.config import get_settings
from july.db import JulyDatabase
from july.llm import LLMProviderError, create_llm_provider
from july.mcp import main as mcp_main
from july.pipeline import apply_classification_overrides, create_capture_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="july", description="July local-first memory orchestrator MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture a free-form input into July")
    capture.add_argument("text", nargs="?", help="Raw input to capture. If omitted, stdin is used.")
    capture.add_argument("--source", default="cli", help="Source channel, e.g. cli, telegram, email")
    capture.add_argument("--source-ref", default=None, help="External reference for the source message")
    capture.add_argument("--dry-run", action="store_true", help="Show the classification plan without persisting it")
    capture.add_argument("--use-llm", action="store_true", help="Ask the configured LLM provider to refine the classification")

    clarify = subparsers.add_parser("clarify", help="Answer a clarification question for an inbox item")
    clarify.add_argument("inbox_item_id", type=int)
    clarify.add_argument("answer", nargs="?", help="Clarification answer. If omitted, stdin is used.")
    clarify.add_argument("--use-llm", action="store_true", help="Ask the configured LLM provider to refine the resolved classification")

    promote = subparsers.add_parser("promote-memory", help="Promote a candidate memory to ready")
    promote.add_argument("memory_item_id", type=int)
    promote.add_argument("--title", default=None)
    promote.add_argument("--summary", default=None)
    promote.add_argument("--knowledge", default=None, help="Override distilled knowledge")
    promote.add_argument("--scope", default=None, choices=["global", "project", "session"])
    promote.add_argument("--importance", type=int, default=None)
    promote.add_argument("--use-llm", action="store_true", help="Ask the configured LLM provider to refine the memory before promoting it")

    inbox = subparsers.add_parser("inbox", help="List inbox items")
    inbox.add_argument("--limit", type=int, default=20)

    tasks = subparsers.add_parser("tasks", help="List tasks")
    tasks.add_argument("--status", default=None)
    tasks.add_argument("--limit", type=int, default=20)

    memory = subparsers.add_parser("memory", help="List memory items")
    memory.add_argument("--limit", type=int, default=20)

    project_context = subparsers.add_parser("project-context", help="Show inbox/tasks/memory for a project key")
    project_context.add_argument("project_key")
    project_context.add_argument("--limit", type=int, default=10)

    search = subparsers.add_parser("search", help="Search inbox, tasks, and memory")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)

    show = subparsers.add_parser("show", help="Show a single record")
    show.add_argument("table", choices=["inbox_items", "tasks", "memory_items", "artifacts", "project_links", "clarification_events"])
    show.add_argument("record_id", type=int)

    stats = subparsers.add_parser("stats", help="Show database stats")

    export = subparsers.add_parser("export", help="Export the database to JSON")
    export.add_argument("output", nargs="?", default="exports/july-export.json")

    subparsers.add_parser("mcp", help="Run the July MCP server over stdio")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = get_settings()
    database = JulyDatabase(settings)
    llm_provider = create_llm_provider(settings.llm)

    try:
        if args.command == "mcp":
            return mcp_main()

        if args.command == "capture":
            raw_input = args.text if args.text is not None else sys.stdin.read().strip()
            if not raw_input:
                parser.error("capture requires text or stdin input")

            plan = create_capture_plan(raw_input)
            if args.use_llm:
                plan = maybe_enrich_capture_with_llm(llm_provider, raw_input, plan)
            if args.dry_run:
                print(json.dumps(plan, indent=2, ensure_ascii=True))
                return 0

            result = database.capture(raw_input, args.source, args.source_ref, plan)
            print_capture_result(plan, result)
            return 0

        if args.command == "clarify":
            answer = args.answer if args.answer is not None else sys.stdin.read().strip()
            if not answer:
                parser.error("clarify requires an answer or stdin input")

            inbox_item = database.get_record("inbox_items", args.inbox_item_id)
            if inbox_item is None:
                print("Inbox item not found")
                return 1

            raw_input = inbox_item["raw_input"]
            plan = create_capture_plan(raw_input, clarification_answer=answer)
            if args.use_llm:
                plan = maybe_enrich_capture_with_llm(llm_provider, raw_input, plan, clarification_answer=answer)
            result = database.resolve_clarification(args.inbox_item_id, answer, plan)
            print_capture_result(plan, result)
            return 0

        if args.command == "promote-memory":
            memory_item = database.get_record("memory_items", args.memory_item_id)
            if memory_item is None:
                print("Memory item not found")
                return 1

            memory_updates = {}
            if args.use_llm:
                memory_updates = maybe_draft_memory_with_llm(llm_provider, database, memory_item)

            promoted = database.promote_memory(
                args.memory_item_id,
                title=args.title or memory_updates.get("title"),
                summary=args.summary or memory_updates.get("summary"),
                distilled_knowledge=args.knowledge or memory_updates.get("distilled_knowledge"),
                scope=args.scope,
                importance=args.importance,
            )
            print(json.dumps(dict(promoted), indent=2, ensure_ascii=True))
            return 0

        if args.command == "inbox":
            print_rows(database.list_inbox(limit=args.limit))
            return 0

        if args.command == "tasks":
            print_rows(database.list_tasks(status=args.status, limit=args.limit))
            return 0

        if args.command == "memory":
            print_rows(database.list_memory(limit=args.limit))
            return 0

        if args.command == "project-context":
            project_context = database.project_context(args.project_key, limit=args.limit)
            for section, rows in project_context.items():
                print(f"[{section}]")
                print_rows(rows)
                print()
            return 0

        if args.command == "search":
            results = database.search(args.query, limit=args.limit)
            for section, rows in results.items():
                print(f"[{section}]")
                print_rows(rows)
                print()
            return 0

        if args.command == "show":
            row = database.get_record(args.table, args.record_id)
            if row is None:
                print("Record not found")
                return 1
            print(json.dumps(dict(row), indent=2, ensure_ascii=True))
            return 0

        if args.command == "stats":
            payload = database.stats()
            payload["llm_provider_available"] = int(llm_provider.is_available())
            print(json.dumps(payload, indent=2, ensure_ascii=True))
            return 0

        if args.command == "export":
            output_path = Path(args.output)
            database.export_json(output_path)
            print(f"Exported July data to {output_path}")
            return 0
    except (ValueError, LLMProviderError) as exc:
        print(str(exc))
        return 1

    return 1


def print_rows(rows) -> None:
    if not rows:
        print("(empty)")
        return
    for row in rows:
        print(json.dumps(dict(row), ensure_ascii=True))


def print_capture_result(plan: dict, result: dict) -> None:
    classification = plan["classification"]
    print(f"inbox_item_id={result['inbox_item_id']}")
    print(f"intent={classification['intent']} confidence={classification['confidence']}")
    print(f"status={classification['status']}")
    print(f"summary={classification['normalized_summary']}")
    if classification["clarification_question"]:
        print(f"clarification={classification['clarification_question']}")
    if result["task_id"]:
        print(f"task_id={result['task_id']}")
    if result["memory_item_id"]:
        print(f"memory_item_id={result['memory_item_id']}")


def maybe_enrich_capture_with_llm(llm_provider, raw_input: str, plan: dict, clarification_answer: str | None = None) -> dict:
    overrides = llm_provider.enrich_capture(raw_input, plan)
    if not overrides:
        return plan
    return apply_classification_overrides(raw_input, plan, overrides, clarification_answer=clarification_answer)


def maybe_draft_memory_with_llm(llm_provider, database: JulyDatabase, memory_item) -> dict:
    inbox_item_id = memory_item["inbox_item_id"]
    raw_input = ""
    if inbox_item_id:
        inbox_item = database.get_record("inbox_items", inbox_item_id)
        if inbox_item is not None:
            raw_input = inbox_item["raw_input"]
    return llm_provider.draft_memory(raw_input, dict(memory_item)) or {}
