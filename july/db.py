from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from july.config import Settings


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS inbox_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_input TEXT NOT NULL,
    source_channel TEXT NOT NULL,
    source_ref TEXT,
    detected_intent TEXT NOT NULL,
    intent_confidence REAL NOT NULL,
    status TEXT NOT NULL,
    clarification_question TEXT,
    normalized_summary TEXT NOT NULL,
    domain TEXT NOT NULL,
    project_key TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_item_id INTEGER NOT NULL REFERENCES inbox_items(id) ON DELETE CASCADE,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    details TEXT,
    project_key TEXT,
    due_hint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_item_id INTEGER REFERENCES inbox_items(id) ON DELETE SET NULL,
    memory_kind TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    distilled_knowledge TEXT NOT NULL,
    domain TEXT NOT NULL,
    scope TEXT NOT NULL,
    project_key TEXT,
    importance INTEGER NOT NULL,
    confidence REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_item_id INTEGER NOT NULL REFERENCES inbox_items(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    value TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_item_id INTEGER REFERENCES inbox_items(id) ON DELETE CASCADE,
    memory_item_id INTEGER REFERENCES memory_items(id) ON DELETE CASCADE,
    project_key TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clarification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_item_id INTEGER NOT NULL REFERENCES inbox_items(id) ON DELETE CASCADE,
    question TEXT,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key TEXT NOT NULL UNIQUE,
    project_key TEXT,
    agent_name TEXT,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT,
    discoveries TEXT,
    accomplished TEXT,
    next_steps TEXT,
    relevant_files TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT
);

CREATE TABLE IF NOT EXISTS topic_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_key_id INTEGER NOT NULL REFERENCES topic_keys(id) ON DELETE CASCADE,
    inbox_item_id INTEGER REFERENCES inbox_items(id) ON DELETE SET NULL,
    memory_item_id INTEGER REFERENCES memory_items(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_contributions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    contribution_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    inbox_item_id INTEGER REFERENCES inbox_items(id) ON DELETE SET NULL,
    memory_item_id INTEGER REFERENCES memory_items(id) ON DELETE SET NULL,
    session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    project_key TEXT,
    domain TEXT,
    adopted INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS url_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER REFERENCES artifacts(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    resolved_title TEXT,
    description TEXT,
    content_type TEXT,
    extracted_text TEXT,
    youtube_video_id TEXT,
    youtube_channel TEXT,
    youtube_duration TEXT,
    fetch_status TEXT NOT NULL DEFAULT 'pending',
    fetched_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS external_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    reference_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    relevance_note TEXT,
    inbox_item_id INTEGER REFERENCES inbox_items(id) ON DELETE SET NULL,
    memory_item_id INTEGER REFERENCES memory_items(id) ON DELETE SET NULL,
    project_key TEXT,
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS inbox_items_fts USING fts5(
    raw_input,
    normalized_summary,
    content='inbox_items',
    content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts USING fts5(
    title,
    summary,
    distilled_knowledge,
    content='memory_items',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS inbox_items_ai AFTER INSERT ON inbox_items BEGIN
    INSERT INTO inbox_items_fts(rowid, raw_input, normalized_summary)
    VALUES (new.id, new.raw_input, new.normalized_summary);
END;

CREATE TRIGGER IF NOT EXISTS inbox_items_ad AFTER DELETE ON inbox_items BEGIN
    INSERT INTO inbox_items_fts(inbox_items_fts, rowid, raw_input, normalized_summary)
    VALUES ('delete', old.id, old.raw_input, old.normalized_summary);
END;

CREATE TRIGGER IF NOT EXISTS inbox_items_au AFTER UPDATE ON inbox_items BEGIN
    INSERT INTO inbox_items_fts(inbox_items_fts, rowid, raw_input, normalized_summary)
    VALUES ('delete', old.id, old.raw_input, old.normalized_summary);
    INSERT INTO inbox_items_fts(rowid, raw_input, normalized_summary)
    VALUES (new.id, new.raw_input, new.normalized_summary);
END;

CREATE TRIGGER IF NOT EXISTS memory_items_ai AFTER INSERT ON memory_items BEGIN
    INSERT INTO memory_items_fts(rowid, title, summary, distilled_knowledge)
    VALUES (new.id, new.title, new.summary, new.distilled_knowledge);
END;

CREATE TRIGGER IF NOT EXISTS memory_items_ad AFTER DELETE ON memory_items BEGIN
    INSERT INTO memory_items_fts(memory_items_fts, rowid, title, summary, distilled_knowledge)
    VALUES ('delete', old.id, old.title, old.summary, old.distilled_knowledge);
END;

CREATE TRIGGER IF NOT EXISTS memory_items_au AFTER UPDATE ON memory_items BEGIN
    INSERT INTO memory_items_fts(memory_items_fts, rowid, title, summary, distilled_knowledge)
    VALUES ('delete', old.id, old.title, old.summary, old.distilled_knowledge);
    INSERT INTO memory_items_fts(rowid, title, summary, distilled_knowledge)
    VALUES (new.id, new.title, new.summary, new.distilled_knowledge);
END;
"""


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class JulyDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.settings.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA_SQL)

    def capture(self, raw_input: str, source_channel: str, source_ref: str | None, plan: dict) -> dict:
        timestamp = utc_now()
        classification = plan["classification"]

        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO inbox_items (
                    raw_input, source_channel, source_ref, detected_intent, intent_confidence,
                    status, clarification_question, normalized_summary, domain, project_key,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_input,
                    source_channel,
                    source_ref,
                    classification["intent"],
                    classification["confidence"],
                    classification["status"],
                    classification["clarification_question"],
                    classification["normalized_summary"],
                    classification["domain"],
                    classification["project_key"],
                    timestamp,
                    timestamp,
                ),
            )
            inbox_item_id = cursor.lastrowid

            task_id = self._insert_task(conn, inbox_item_id, plan["task"], timestamp)
            memory_item_id = self._insert_memory(conn, inbox_item_id, plan["memory"], timestamp)
            self._insert_artifacts(conn, inbox_item_id, plan["artifacts"], timestamp)
            self._insert_project_links(conn, inbox_item_id, memory_item_id, plan, timestamp)

        return {
            "inbox_item_id": inbox_item_id,
            "task_id": task_id,
            "memory_item_id": memory_item_id,
        }

    def resolve_clarification(self, inbox_item_id: int, answer: str, plan: dict) -> dict:
        timestamp = utc_now()
        classification = plan["classification"]

        with self.connection() as conn:
            inbox_item = conn.execute(
                "SELECT * FROM inbox_items WHERE id = ?",
                (inbox_item_id,),
            ).fetchone()
            if inbox_item is None:
                raise ValueError(f"Inbox item {inbox_item_id} not found")

            conn.execute(
                """
                INSERT INTO clarification_events (inbox_item_id, question, answer, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    inbox_item_id,
                    inbox_item["clarification_question"],
                    answer,
                    timestamp,
                ),
            )

            self._delete_derived_records(conn, inbox_item_id)

            conn.execute(
                """
                UPDATE inbox_items
                SET detected_intent = ?, intent_confidence = ?, status = ?, clarification_question = ?,
                    normalized_summary = ?, domain = ?, project_key = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    classification["intent"],
                    classification["confidence"],
                    classification["status"],
                    classification["clarification_question"],
                    classification["normalized_summary"],
                    classification["domain"],
                    classification["project_key"],
                    timestamp,
                    inbox_item_id,
                ),
            )

            task_id = self._insert_task(conn, inbox_item_id, plan["task"], timestamp)
            memory_item_id = self._insert_memory(conn, inbox_item_id, plan["memory"], timestamp)
            self._insert_artifacts(conn, inbox_item_id, plan["artifacts"], timestamp)
            self._insert_project_links(conn, inbox_item_id, memory_item_id, plan, timestamp)

        return {
            "inbox_item_id": inbox_item_id,
            "task_id": task_id,
            "memory_item_id": memory_item_id,
        }

    def promote_memory(
        self,
        memory_item_id: int,
        *,
        title: str | None = None,
        summary: str | None = None,
        distilled_knowledge: str | None = None,
        scope: str | None = None,
        importance: int | None = None,
    ) -> sqlite3.Row:
        timestamp = utc_now()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM memory_items WHERE id = ?",
                (memory_item_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Memory item {memory_item_id} not found")

            new_title = title or row["title"]
            new_summary = summary or row["summary"]
            new_distilled = distilled_knowledge or row["distilled_knowledge"]
            new_scope = scope or row["scope"]
            new_importance = importance if importance is not None else row["importance"]

            conn.execute(
                """
                UPDATE memory_items
                SET title = ?, summary = ?, distilled_knowledge = ?, scope = ?,
                    importance = ?, status = 'ready', updated_at = ?
                WHERE id = ?
                """,
                (
                    new_title,
                    new_summary,
                    new_distilled,
                    new_scope,
                    new_importance,
                    timestamp,
                    memory_item_id,
                ),
            )
            return conn.execute(
                "SELECT * FROM memory_items WHERE id = ?",
                (memory_item_id,),
            ).fetchone()

    def project_context(self, project_key: str, limit: int = 10) -> dict[str, list[sqlite3.Row]]:
        with self.connection() as conn:
            inbox_rows = conn.execute(
                """
                SELECT id, detected_intent, status, normalized_summary, created_at
                FROM inbox_items
                WHERE project_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (project_key, limit),
            ).fetchall()
            task_rows = conn.execute(
                """
                SELECT id, task_type, status, title, created_at
                FROM tasks
                WHERE project_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (project_key, limit),
            ).fetchall()
            memory_rows = conn.execute(
                """
                SELECT id, memory_kind, status, title, summary, created_at
                FROM memory_items
                WHERE project_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (project_key, limit),
            ).fetchall()
        return {"inbox": inbox_rows, "tasks": task_rows, "memory": memory_rows}

    def _insert_task(self, conn: sqlite3.Connection, inbox_item_id: int, task: dict | None, timestamp: str) -> int | None:
        if not task:
            return None
        cursor = conn.execute(
            """
            INSERT INTO tasks (
                inbox_item_id, task_type, status, title, details, project_key, due_hint,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inbox_item_id,
                task["task_type"],
                task["status"],
                task["title"],
                task["details"],
                task["project_key"],
                task.get("due_hint"),
                timestamp,
                timestamp,
            ),
        )
        return cursor.lastrowid

    def _insert_memory(self, conn: sqlite3.Connection, inbox_item_id: int, memory: dict | None, timestamp: str) -> int | None:
        if not memory:
            return None
        cursor = conn.execute(
            """
            INSERT INTO memory_items (
                inbox_item_id, memory_kind, title, summary, distilled_knowledge, domain,
                scope, project_key, importance, confidence, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                inbox_item_id,
                memory["memory_kind"],
                memory["title"],
                memory["summary"],
                memory["distilled_knowledge"],
                memory["domain"],
                memory["scope"],
                memory["project_key"],
                memory["importance"],
                memory["confidence"],
                memory["status"],
                timestamp,
                timestamp,
            ),
        )
        return cursor.lastrowid

    def _insert_artifacts(self, conn: sqlite3.Connection, inbox_item_id: int, artifacts: list[dict], timestamp: str) -> None:
        for artifact in artifacts:
            conn.execute(
                """
                INSERT INTO artifacts (inbox_item_id, artifact_type, value, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    inbox_item_id,
                    artifact["artifact_type"],
                    artifact["value"],
                    artifact["metadata_json"],
                    timestamp,
                ),
            )

    def _insert_project_links(
        self,
        conn: sqlite3.Connection,
        inbox_item_id: int,
        memory_item_id: int | None,
        plan: dict,
        timestamp: str,
    ) -> None:
        for project_key in plan["context"]["project_keys"]:
            relation_type = "derived_from_input" if memory_item_id else "mentioned_in_input"
            conn.execute(
                """
                INSERT INTO project_links (
                    inbox_item_id, memory_item_id, project_key, relation_type, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    inbox_item_id,
                    memory_item_id,
                    project_key,
                    relation_type,
                    plan["classification"]["confidence"],
                    timestamp,
                ),
            )

    def _delete_derived_records(self, conn: sqlite3.Connection, inbox_item_id: int) -> None:
        conn.execute("DELETE FROM tasks WHERE inbox_item_id = ?", (inbox_item_id,))
        conn.execute("DELETE FROM project_links WHERE inbox_item_id = ?", (inbox_item_id,))
        conn.execute("DELETE FROM artifacts WHERE inbox_item_id = ?", (inbox_item_id,))
        conn.execute("DELETE FROM memory_items WHERE inbox_item_id = ?", (inbox_item_id,))

    def list_inbox(self, limit: int = 20) -> list[sqlite3.Row]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, detected_intent, status, domain, project_key, normalized_summary, created_at
                FROM inbox_items
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def list_tasks(self, status: str | None = None, limit: int = 20) -> list[sqlite3.Row]:
        query = """
            SELECT id, inbox_item_id, task_type, status, project_key, title, created_at
            FROM tasks
        """
        params: list[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self.connection() as conn:
            cursor = conn.execute(query, tuple(params))
            return cursor.fetchall()

    def list_memory(self, limit: int = 20) -> list[sqlite3.Row]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, inbox_item_id, memory_kind, status, domain, scope, project_key, title, created_at
                FROM memory_items
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()

    def search(self, query: str, limit: int = 10) -> dict[str, list[sqlite3.Row]]:
        with self.connection() as conn:
            try:
                inbox_rows = conn.execute(
                    """
                    SELECT inbox_items.id, inbox_items.detected_intent, inbox_items.status,
                           inbox_items.domain, inbox_items.project_key, inbox_items.normalized_summary
                    FROM inbox_items_fts
                    JOIN inbox_items ON inbox_items_fts.rowid = inbox_items.id
                    WHERE inbox_items_fts MATCH ?
                    ORDER BY inbox_items.id DESC
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()

                memory_rows = conn.execute(
                    """
                    SELECT memory_items.id, memory_items.memory_kind, memory_items.status,
                           memory_items.domain, memory_items.scope, memory_items.project_key, memory_items.title
                    FROM memory_items_fts
                    JOIN memory_items ON memory_items_fts.rowid = memory_items.id
                    WHERE memory_items_fts MATCH ?
                    ORDER BY memory_items.id DESC
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                inbox_rows = conn.execute(
                    """
                    SELECT id, detected_intent, status, domain, project_key, normalized_summary
                    FROM inbox_items
                    WHERE raw_input LIKE ? OR normalized_summary LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
                memory_rows = conn.execute(
                    """
                    SELECT id, memory_kind, status, domain, scope, project_key, title
                    FROM memory_items
                    WHERE title LIKE ? OR summary LIKE ? OR distilled_knowledge LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", f"%{query}%", limit),
                ).fetchall()

            task_rows = conn.execute(
                """
                SELECT id, inbox_item_id, task_type, status, project_key, title
                FROM tasks
                WHERE title LIKE ? OR details LIKE ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()

        return {"inbox": inbox_rows, "memory": memory_rows, "tasks": task_rows}

    def get_record(self, table: str, record_id: int) -> sqlite3.Row | None:
        allowed_tables = {
            "inbox_items", "tasks", "memory_items", "artifacts", "project_links",
            "clarification_events", "sessions", "topic_keys", "topic_links",
            "model_contributions", "url_metadata", "external_references",
        }
        if table not in allowed_tables:
            raise ValueError(f"Unsupported table: {table}")
        with self.connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,))
            return cursor.fetchone()

    # ── Session protocol ──────────────────────────────────────────────

    def session_start(
        self,
        session_key: str,
        *,
        project_key: str | None = None,
        agent_name: str | None = None,
        goal: str | None = None,
    ) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?", (session_key,)
            ).fetchone()
            if existing:
                return {"session_id": existing["id"], "status": "already_active", "started_at": existing["started_at"]}
            cursor = conn.execute(
                """
                INSERT INTO sessions (session_key, project_key, agent_name, goal, status, started_at)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (session_key, project_key, agent_name, goal, timestamp),
            )
        return {"session_id": cursor.lastrowid, "status": "active", "started_at": timestamp}

    def session_summary(
        self,
        session_key: str,
        *,
        summary: str,
        discoveries: str | None = None,
        accomplished: str | None = None,
        next_steps: str | None = None,
        relevant_files: str | None = None,
    ) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?", (session_key,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Session '{session_key}' not found")
            conn.execute(
                """
                UPDATE sessions
                SET summary = ?, discoveries = ?, accomplished = ?,
                    next_steps = ?, relevant_files = ?, status = 'summarized',
                    ended_at = ?
                WHERE session_key = ?
                """,
                (summary, discoveries, accomplished, next_steps, relevant_files, timestamp, session_key),
            )
        return {"session_key": session_key, "status": "summarized", "ended_at": timestamp}

    def session_end(self, session_key: str) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_key = ?", (session_key,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Session '{session_key}' not found")
            new_status = "closed" if row["summary"] else "closed_without_summary"
            conn.execute(
                "UPDATE sessions SET status = ?, ended_at = COALESCE(ended_at, ?) WHERE session_key = ?",
                (new_status, timestamp, session_key),
            )
        return {"session_key": session_key, "status": new_status, "ended_at": timestamp}

    def session_context(self, project_key: str | None = None, limit: int = 5) -> list[dict]:
        with self.connection() as conn:
            if project_key:
                rows = conn.execute(
                    """
                    SELECT id, session_key, project_key, agent_name, goal, status,
                           summary, discoveries, next_steps, started_at, ended_at
                    FROM sessions
                    WHERE project_key = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (project_key, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, session_key, project_key, agent_name, goal, status,
                           summary, discoveries, next_steps, started_at, ended_at
                    FROM sessions
                    ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def list_sessions(self, status: str | None = None, limit: int = 20) -> list[sqlite3.Row]:
        query = """
            SELECT id, session_key, project_key, agent_name, goal, status, started_at, ended_at
            FROM sessions
        """
        params: list[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.connection() as conn:
            return conn.execute(query, tuple(params)).fetchall()

    # ── Topic keys ────────────────────────────────────────────────────

    def create_topic(self, topic_key: str, label: str, domain: str, description: str | None = None) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            existing = conn.execute(
                "SELECT * FROM topic_keys WHERE topic_key = ?", (topic_key,)
            ).fetchone()
            if existing:
                return {"topic_id": existing["id"], "status": "already_exists"}
            cursor = conn.execute(
                """
                INSERT INTO topic_keys (topic_key, label, domain, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (topic_key, label, domain, description, timestamp, timestamp),
            )
        return {"topic_id": cursor.lastrowid, "status": "created"}

    def link_to_topic(
        self,
        topic_key: str,
        *,
        inbox_item_id: int | None = None,
        memory_item_id: int | None = None,
        session_id: int | None = None,
    ) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            topic = conn.execute(
                "SELECT id FROM topic_keys WHERE topic_key = ?", (topic_key,)
            ).fetchone()
            if topic is None:
                raise ValueError(f"Topic '{topic_key}' not found")
            conn.execute(
                """
                INSERT INTO topic_links (topic_key_id, inbox_item_id, memory_item_id, session_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (topic["id"], inbox_item_id, memory_item_id, session_id, timestamp),
            )
        return {"linked": True, "topic_key": topic_key}

    def topic_context(self, topic_key: str, limit: int = 20) -> dict:
        with self.connection() as conn:
            topic = conn.execute(
                "SELECT * FROM topic_keys WHERE topic_key = ?", (topic_key,)
            ).fetchone()
            if topic is None:
                raise ValueError(f"Topic '{topic_key}' not found")
            links = conn.execute(
                """
                SELECT tl.id, tl.inbox_item_id, tl.memory_item_id, tl.session_id, tl.created_at
                FROM topic_links tl
                WHERE tl.topic_key_id = ?
                ORDER BY tl.id DESC LIMIT ?
                """,
                (topic["id"], limit),
            ).fetchall()
            memory_ids = [l["memory_item_id"] for l in links if l["memory_item_id"]]
            memories = []
            for mid in memory_ids:
                row = conn.execute(
                    "SELECT id, memory_kind, status, title, summary, domain, scope, project_key FROM memory_items WHERE id = ?",
                    (mid,),
                ).fetchone()
                if row:
                    memories.append(dict(row))
        return {"topic": dict(topic), "links": [dict(l) for l in links], "memories": memories}

    def list_topics(self, limit: int = 50) -> list[sqlite3.Row]:
        with self.connection() as conn:
            return conn.execute(
                "SELECT id, topic_key, label, domain, description, created_at FROM topic_keys ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

    # ── Model contributions / traceability ────────────────────────────

    def save_model_contribution(
        self,
        model_name: str,
        contribution_type: str,
        title: str,
        content: str,
        *,
        inbox_item_id: int | None = None,
        memory_item_id: int | None = None,
        session_id: int | None = None,
        project_key: str | None = None,
        domain: str | None = None,
        adopted: bool = False,
        notes: str | None = None,
    ) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_contributions (
                    model_name, contribution_type, title, content,
                    inbox_item_id, memory_item_id, session_id,
                    project_key, domain, adopted, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_name, contribution_type, title, content,
                    inbox_item_id, memory_item_id, session_id,
                    project_key, domain, int(adopted), notes, timestamp,
                ),
            )
        return {"contribution_id": cursor.lastrowid, "model_name": model_name}

    def list_model_contributions(
        self, model_name: str | None = None, project_key: str | None = None, limit: int = 20
    ) -> list[sqlite3.Row]:
        query = """
            SELECT id, model_name, contribution_type, title, project_key, domain, adopted, created_at
            FROM model_contributions
        """
        clauses: list[str] = []
        params: list[object] = []
        if model_name:
            clauses.append("model_name = ?")
            params.append(model_name)
        if project_key:
            clauses.append("project_key = ?")
            params.append(project_key)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self.connection() as conn:
            return conn.execute(query, tuple(params)).fetchall()

    def adopt_contribution(self, contribution_id: int, notes: str | None = None) -> dict:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM model_contributions WHERE id = ?", (contribution_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Contribution {contribution_id} not found")
            conn.execute(
                "UPDATE model_contributions SET adopted = 1, notes = COALESCE(?, notes) WHERE id = ?",
                (notes, contribution_id),
            )
        return {"adopted": True, "contribution_id": contribution_id}

    # ── URL metadata ──────────────────────────────────────────────────

    def save_url_metadata(
        self,
        url: str,
        *,
        artifact_id: int | None = None,
        resolved_title: str | None = None,
        description: str | None = None,
        content_type: str | None = None,
        extracted_text: str | None = None,
        youtube_video_id: str | None = None,
        youtube_channel: str | None = None,
        youtube_duration: str | None = None,
        fetch_status: str = "fetched",
    ) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO url_metadata (
                    artifact_id, url, resolved_title, description, content_type,
                    extracted_text, youtube_video_id, youtube_channel, youtube_duration,
                    fetch_status, fetched_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id, url, resolved_title, description, content_type,
                    extracted_text, youtube_video_id, youtube_channel, youtube_duration,
                    fetch_status, timestamp, timestamp,
                ),
            )
        return {"url_metadata_id": cursor.lastrowid, "url": url, "fetch_status": fetch_status}

    def get_url_metadata(self, url: str) -> sqlite3.Row | None:
        with self.connection() as conn:
            return conn.execute(
                "SELECT * FROM url_metadata WHERE url = ? ORDER BY id DESC LIMIT 1",
                (url,),
            ).fetchone()

    # ── External references (skills.sh, agents.md, etc.) ─────────────

    def save_external_reference(
        self,
        source_url: str,
        source_name: str,
        reference_type: str,
        title: str,
        *,
        description: str | None = None,
        relevance_note: str | None = None,
        inbox_item_id: int | None = None,
        memory_item_id: int | None = None,
        project_key: str | None = None,
    ) -> dict:
        timestamp = utc_now()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO external_references (
                    source_url, source_name, reference_type, title,
                    description, relevance_note, inbox_item_id, memory_item_id,
                    project_key, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_url, source_name, reference_type, title,
                    description, relevance_note, inbox_item_id, memory_item_id,
                    project_key, timestamp,
                ),
            )
        return {"external_reference_id": cursor.lastrowid, "source_name": source_name}

    def list_external_references(self, project_key: str | None = None, limit: int = 20) -> list[sqlite3.Row]:
        if project_key:
            query = """
                SELECT id, source_url, source_name, reference_type, title, relevance_note, project_key, created_at
                FROM external_references WHERE project_key = ? ORDER BY id DESC LIMIT ?
            """
            params: tuple = (project_key, limit)
        else:
            query = """
                SELECT id, source_url, source_name, reference_type, title, relevance_note, project_key, created_at
                FROM external_references ORDER BY id DESC LIMIT ?
            """
            params = (limit,)
        with self.connection() as conn:
            return conn.execute(query, params).fetchall()

    # ── Proactive recall ──────────────────────────────────────────────

    def proactive_recall(self, raw_input: str, project_key: str | None = None, limit: int = 5) -> dict:
        """Search memory proactively for related items when a new input arrives."""
        words = [w for w in raw_input.lower().split() if len(w) > 3]
        if not words:
            return {"related_memories": [], "related_sessions": [], "suggestions": []}

        with self.connection() as conn:
            # Search in memory via FTS
            fts_query = " OR ".join(words[:8])
            try:
                memory_rows = conn.execute(
                    """
                    SELECT memory_items.id, memory_items.memory_kind, memory_items.status,
                           memory_items.domain, memory_items.scope, memory_items.project_key,
                           memory_items.title, memory_items.summary, memory_items.distilled_knowledge
                    FROM memory_items_fts
                    JOIN memory_items ON memory_items_fts.rowid = memory_items.id
                    WHERE memory_items_fts MATCH ?
                    ORDER BY memory_items.importance DESC, memory_items.id DESC
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                like_pattern = f"%{words[0]}%"
                memory_rows = conn.execute(
                    """
                    SELECT id, memory_kind, status, domain, scope, project_key,
                           title, summary, distilled_knowledge
                    FROM memory_items
                    WHERE title LIKE ? OR summary LIKE ? OR distilled_knowledge LIKE ?
                    ORDER BY importance DESC, id DESC
                    LIMIT ?
                    """,
                    (like_pattern, like_pattern, like_pattern, limit),
                ).fetchall()

            # Also search recent sessions for relevant context
            session_rows = []
            if project_key:
                session_rows = conn.execute(
                    """
                    SELECT id, session_key, project_key, goal, status, summary, next_steps, started_at
                    FROM sessions
                    WHERE project_key = ? AND summary IS NOT NULL
                    ORDER BY id DESC LIMIT 3
                    """,
                    (project_key,),
                ).fetchall()

            # Build suggestions
            suggestions = []
            for mem in memory_rows:
                if mem["status"] == "ready" and mem["scope"] == "global":
                    suggestions.append({
                        "type": "reuse_memory",
                        "memory_id": mem["id"],
                        "title": mem["title"],
                        "reason": f"Memoria global reutilizable: {mem['distilled_knowledge'][:120]}",
                    })
                elif mem["project_key"] and mem["project_key"] != project_key:
                    suggestions.append({
                        "type": "cross_project",
                        "memory_id": mem["id"],
                        "title": mem["title"],
                        "from_project": mem["project_key"],
                        "reason": f"Ya resolviste algo parecido en {mem['project_key']}: {mem['title']}",
                    })

        return {
            "related_memories": [dict(r) for r in memory_rows],
            "related_sessions": [dict(r) for r in session_rows],
            "suggestions": suggestions,
        }

    def stats(self) -> dict[str, int]:
        with self.connection() as conn:
            return {
                "inbox_items": conn.execute("SELECT COUNT(*) FROM inbox_items").fetchone()[0],
                "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
                "memory_items": conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0],
                "artifacts": conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
                "project_links": conn.execute("SELECT COUNT(*) FROM project_links").fetchone()[0],
                "clarification_events": conn.execute("SELECT COUNT(*) FROM clarification_events").fetchone()[0],
                "sessions": conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
                "topic_keys": conn.execute("SELECT COUNT(*) FROM topic_keys").fetchone()[0],
                "model_contributions": conn.execute("SELECT COUNT(*) FROM model_contributions").fetchone()[0],
                "url_metadata": conn.execute("SELECT COUNT(*) FROM url_metadata").fetchone()[0],
                "external_references": conn.execute("SELECT COUNT(*) FROM external_references").fetchone()[0],
            }

    def export_json(self, output_path: Path) -> None:
        payload: dict[str, list[dict]] = {}
        with self.connection() as conn:
            for table in (
                "inbox_items", "tasks", "memory_items", "artifacts", "project_links",
                "clarification_events", "sessions", "topic_keys", "topic_links",
                "model_contributions", "url_metadata", "external_references",
        ):
                rows = conn.execute(f"SELECT * FROM {table} ORDER BY id ASC").fetchall()
                payload[table] = [dict(row) for row in rows]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
