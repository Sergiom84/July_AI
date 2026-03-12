from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from july.config import get_settings
from july.db import JulyDatabase
from july.external_refs import fetch_reference_page
from july.llm import LLMProviderError, create_llm_provider
from july.mcp import main as mcp_main
from july.pipeline import (
    apply_classification_overrides,
    create_capture_plan,
    enrich_plan_with_proactive_recall,
)
from july.url_fetcher import fetch_url_metadata, is_youtube_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="july", description="July local-first memory orchestrator MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── Capture ──────────────────────────────────────────────
    capture = subparsers.add_parser("capture", help="Capture a free-form input into July")
    capture.add_argument("text", nargs="?", help="Raw input to capture. If omitted, stdin is used.")
    capture.add_argument("--source", default="cli", help="Source channel, e.g. cli, telegram, email")
    capture.add_argument("--source-ref", default=None, help="External reference for the source message")
    capture.add_argument("--dry-run", action="store_true", help="Show the classification plan without persisting it")
    capture.add_argument("--use-llm", action="store_true", help="Ask the configured LLM provider to refine the classification")
    capture.add_argument("--fetch-urls", action="store_true", help="Fetch metadata for detected URLs")
    capture.add_argument("--model-name", default=None, help="Name of the model contributing this input (for traceability)")

    # ── Clarify ──────────────────────────────────────────────
    clarify = subparsers.add_parser("clarify", help="Answer a clarification question for an inbox item")
    clarify.add_argument("inbox_item_id", type=int)
    clarify.add_argument("answer", nargs="?", help="Clarification answer. If omitted, stdin is used.")
    clarify.add_argument("--use-llm", action="store_true", help="Ask the configured LLM provider to refine the resolved classification")

    # ── Promote memory ───────────────────────────────────────
    promote = subparsers.add_parser("promote-memory", help="Promote a candidate memory to ready")
    promote.add_argument("memory_item_id", type=int)
    promote.add_argument("--title", default=None)
    promote.add_argument("--summary", default=None)
    promote.add_argument("--knowledge", default=None, help="Override distilled knowledge")
    promote.add_argument("--scope", default=None, choices=["global", "project", "session"])
    promote.add_argument("--importance", type=int, default=None)
    promote.add_argument("--use-llm", action="store_true", help="Ask the configured LLM provider to refine the memory before promoting it")

    # ── List commands ────────────────────────────────────────
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
    show.add_argument("table", choices=[
        "inbox_items", "tasks", "memory_items", "artifacts", "project_links",
        "clarification_events", "sessions", "topic_keys", "topic_links",
        "model_contributions", "url_metadata", "external_references",
    ])
    show.add_argument("record_id", type=int)

    stats = subparsers.add_parser("stats", help="Show database stats")

    export = subparsers.add_parser("export", help="Export the database to JSON")
    export.add_argument("output", nargs="?", default="exports/july-export.json")

    subparsers.add_parser("mcp", help="Run the July MCP server over stdio")

    # ── Session protocol ─────────────────────────────────────
    ss = subparsers.add_parser("session-start", help="Start a new working session")
    ss.add_argument("session_key", help="Unique key for this session")
    ss.add_argument("--project", default=None, help="Project key for the session")
    ss.add_argument("--agent", default=None, help="Agent or model name")
    ss.add_argument("--goal", default=None, help="Session goal")

    ssm = subparsers.add_parser("session-summary", help="Save a summary for an active session")
    ssm.add_argument("session_key")
    ssm.add_argument("summary", nargs="?", help="Summary text. If omitted, stdin is used.")
    ssm.add_argument("--discoveries", default=None)
    ssm.add_argument("--accomplished", default=None)
    ssm.add_argument("--next-steps", default=None)
    ssm.add_argument("--relevant-files", default=None)

    se = subparsers.add_parser("session-end", help="Close a session")
    se.add_argument("session_key")

    sc = subparsers.add_parser("session-context", help="Recover context from recent sessions")
    sc.add_argument("--project", default=None, help="Filter by project key")
    sc.add_argument("--limit", type=int, default=5)

    sl = subparsers.add_parser("sessions", help="List sessions")
    sl.add_argument("--status", default=None)
    sl.add_argument("--limit", type=int, default=20)

    # ── Topic keys ───────────────────────────────────────────
    tc = subparsers.add_parser("topic-create", help="Create a topic key for grouping related knowledge")
    tc.add_argument("topic_key", help="Stable key like 'auth/jwt-flow' or 'mcp/integration'")
    tc.add_argument("label", help="Human readable label")
    tc.add_argument("--domain", default="Programacion")
    tc.add_argument("--description", default=None)

    tl = subparsers.add_parser("topic-link", help="Link an item to a topic key")
    tl.add_argument("topic_key")
    tl.add_argument("--inbox-item-id", type=int, default=None)
    tl.add_argument("--memory-item-id", type=int, default=None)
    tl.add_argument("--session-id", type=int, default=None)

    tctx = subparsers.add_parser("topic-context", help="Show everything linked to a topic key")
    tctx.add_argument("topic_key")
    tctx.add_argument("--limit", type=int, default=20)

    tls = subparsers.add_parser("topics", help="List all topic keys")
    tls.add_argument("--limit", type=int, default=50)

    # ── Model contributions ──────────────────────────────────
    mc = subparsers.add_parser("model-contribution", help="Record a contribution from an AI model")
    mc.add_argument("model_name", help="Name of the model (claude, codex, zai, gpt, perplexity, genspark...)")
    mc.add_argument("contribution_type", help="Type: proposal, architecture, decision, analysis, suggestion")
    mc.add_argument("title")
    mc.add_argument("content", nargs="?", help="Content text. If omitted, stdin is used.")
    mc.add_argument("--project", default=None)
    mc.add_argument("--domain", default=None)
    mc.add_argument("--adopted", action="store_true")
    mc.add_argument("--notes", default=None)

    mcl = subparsers.add_parser("model-contributions", help="List model contributions")
    mcl.add_argument("--model", default=None)
    mcl.add_argument("--project", default=None)
    mcl.add_argument("--limit", type=int, default=20)

    mca = subparsers.add_parser("adopt-contribution", help="Mark a model contribution as adopted")
    mca.add_argument("contribution_id", type=int)
    mca.add_argument("--notes", default=None)

    # ── URL fetch ────────────────────────────────────────────
    uf = subparsers.add_parser("fetch-url", help="Fetch metadata from a URL and store it")
    uf.add_argument("url")
    uf.add_argument("--artifact-id", type=int, default=None)

    # ── External references ──────────────────────────────────
    ef = subparsers.add_parser("fetch-reference", help="Fetch content from a known reference source")
    ef.add_argument("source_key", choices=["skills.sh", "agents.md"])

    efl = subparsers.add_parser("external-references", help="List stored external references")
    efl.add_argument("--project", default=None)
    efl.add_argument("--limit", type=int, default=20)

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

        # ── Capture ──────────────────────────────────────────
        if args.command == "capture":
            raw_input = args.text if args.text is not None else sys.stdin.read().strip()
            if not raw_input:
                parser.error("capture requires text or stdin input")

            plan = create_capture_plan(raw_input)
            if args.use_llm:
                plan = maybe_enrich_capture_with_llm(llm_provider, raw_input, plan)

            # Proactive recall
            project_key = plan["classification"].get("project_key")
            recall = database.proactive_recall(raw_input, project_key=project_key)
            plan = enrich_plan_with_proactive_recall(plan, recall)

            if args.dry_run:
                print(json.dumps(plan, indent=2, ensure_ascii=True))
                return 0

            result = database.capture(raw_input, args.source, args.source_ref, plan)

            # Fetch URL metadata if requested
            if args.fetch_urls:
                for url in plan["context"].get("urls", []):
                    meta = fetch_url_metadata(url)
                    database.save_url_metadata(url, **{k: v for k, v in meta.items() if k != "url"})

            # Record model contribution if specified
            if args.model_name:
                database.save_model_contribution(
                    model_name=args.model_name,
                    contribution_type="capture_input",
                    title=plan["classification"]["normalized_summary"],
                    content=raw_input,
                    inbox_item_id=result["inbox_item_id"],
                    project_key=project_key,
                )

            print_capture_result(plan, result)
            print_proactive_hints(plan)
            return 0

        # ── Clarify ──────────────────────────────────────────
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

        # ── Promote memory ───────────────────────────────────
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

        # ── List commands ────────────────────────────────────
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
            project_ctx = database.project_context(args.project_key, limit=args.limit)
            for section, rows in project_ctx.items():
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

        # ── Session protocol ─────────────────────────────────
        if args.command == "session-start":
            result = database.session_start(
                args.session_key,
                project_key=args.project,
                agent_name=args.agent,
                goal=args.goal,
            )
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "session-summary":
            summary = args.summary if args.summary is not None else sys.stdin.read().strip()
            if not summary:
                parser.error("session-summary requires a summary text")
            result = database.session_summary(
                args.session_key,
                summary=summary,
                discoveries=args.discoveries,
                accomplished=args.accomplished,
                next_steps=args.next_steps,
                relevant_files=args.relevant_files,
            )
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "session-end":
            result = database.session_end(args.session_key)
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "session-context":
            rows = database.session_context(project_key=args.project, limit=args.limit)
            if not rows:
                print("(no sessions found)")
            else:
                for row in rows:
                    print(json.dumps(row, indent=2, ensure_ascii=True))
            return 0

        if args.command == "sessions":
            print_rows(database.list_sessions(status=args.status, limit=args.limit))
            return 0

        # ── Topic keys ───────────────────────────────────────
        if args.command == "topic-create":
            result = database.create_topic(
                args.topic_key, args.label, args.domain, description=args.description
            )
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "topic-link":
            result = database.link_to_topic(
                args.topic_key,
                inbox_item_id=args.inbox_item_id,
                memory_item_id=args.memory_item_id,
                session_id=args.session_id,
            )
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "topic-context":
            result = database.topic_context(args.topic_key, limit=args.limit)
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "topics":
            print_rows(database.list_topics(limit=args.limit))
            return 0

        # ── Model contributions ──────────────────────────────
        if args.command == "model-contribution":
            content = args.content if args.content is not None else sys.stdin.read().strip()
            if not content:
                parser.error("model-contribution requires content")
            result = database.save_model_contribution(
                model_name=args.model_name,
                contribution_type=args.contribution_type,
                title=args.title,
                content=content,
                project_key=args.project,
                domain=args.domain,
                adopted=args.adopted,
                notes=args.notes,
            )
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "model-contributions":
            print_rows(database.list_model_contributions(
                model_name=args.model, project_key=args.project, limit=args.limit,
            ))
            return 0

        if args.command == "adopt-contribution":
            result = database.adopt_contribution(args.contribution_id, notes=args.notes)
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        # ── URL fetch ────────────────────────────────────────
        if args.command == "fetch-url":
            meta = fetch_url_metadata(args.url)
            db_result = database.save_url_metadata(
                args.url,
                artifact_id=args.artifact_id,
                **{k: v for k, v in meta.items() if k not in ("url", "fetch_status")},
                fetch_status=meta["fetch_status"],
            )
            combined = {**meta, **db_result}
            print(json.dumps(combined, indent=2, ensure_ascii=True))
            return 0

        # ── External references ──────────────────────────────
        if args.command == "fetch-reference":
            result = fetch_reference_page(args.source_key)
            print(json.dumps(result, indent=2, ensure_ascii=True))
            return 0

        if args.command == "external-references":
            print_rows(database.list_external_references(
                project_key=args.project, limit=args.limit,
            ))
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

    # External reference suggestions
    ext_refs = plan.get("external_ref_suggestions", [])
    if ext_refs:
        print("\n--- Sugerencias de referencia externa ---")
        for ref in ext_refs:
            print(f"  [{ref['source_name']}] {ref['reason']}")
            print(f"    URL: {ref['source_url']}")


def print_proactive_hints(plan: dict) -> None:
    hints = plan.get("proactive_hints", [])
    recall = plan.get("proactive_recall", {})
    memories = recall.get("related_memories", [])
    sessions = recall.get("related_sessions", [])

    if not hints and not memories and not sessions:
        return

    print("\n--- Recuperacion proactiva ---")
    if memories:
        print(f"  Memorias relacionadas encontradas: {len(memories)}")
        for mem in memories[:3]:
            print(f"    [{mem.get('memory_kind', '?')}] {mem.get('title', '?')}")
            if mem.get("project_key"):
                print(f"      proyecto: {mem['project_key']}")
    if sessions:
        print(f"  Sesiones recientes relevantes: {len(sessions)}")
        for sess in sessions[:2]:
            print(f"    [{sess.get('session_key', '?')}] {sess.get('goal', sess.get('summary', '?')[:80])}")
    if hints:
        print("  Sugerencias:")
        for hint in hints:
            print(f"    > {hint}")


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
