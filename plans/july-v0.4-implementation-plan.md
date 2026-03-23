# July v0.4 — Implementation Plan

## 1. Findings

### F1. `project_entry` proactive recall searches on project key string, not on project content

[`project_conversation.py:129`](july/project_conversation.py:129) — The call `self.database.proactive_recall(resolved_project_key, ...)` passes the project key (e.g. `"July"`, `"Vocabulario"`) as the search text. In [`db.py:1006`](july/db.py:1006), `proactive_recall` splits this into words > 3 chars and runs FTS. A project key like `"July"` produces zero useful words (4 chars, one word). This means cross-project intelligence on entry is essentially broken for short project names.

**Decision needed**: After onboarding exists, use the snapshot summary and detected objective as recall input instead of the bare project key.

### F2. `assess_project_state` has no staleness check

[`project_conversation.py:341`](july/project_conversation.py:341) — A project that was onboarded 6 months ago with no activity since will still return `"known"` if the original session has a summary and next steps. There is no timestamp comparison.

**Decision needed**: Use `started_at` from the newest session (already returned by [`db.py:726`](july/db.py:726)) to downgrade `"known"` to `"partial"` when the latest session is older than a threshold.

### F3. `conversation_checkpoint` with `action: ask_user` has no confirmation path

[`project_conversation.py:254`](july/project_conversation.py:254) — When `classify_checkpoint` returns `"ask_user"`, the method sets `checkpoint["question"]` but the `persist` flag at line 261 only fires when `action == "store_directly"`. There is no way for the agent to say "the user confirmed, now persist it."

**Decision needed**: Add a `force_persist` parameter or allow `persist=True` to override `ask_user` when the agent has already obtained user confirmation.

### F4. No code handles what happens after a `project_entry` option is chosen

[`project_conversation.py:389`](july/project_conversation.py:389) — `build_entry_prompt` returns options like `analyze_now`, `refresh_context`, `resume_context`, `continue_without_context`. But there is no method that accepts an option id and executes the corresponding action. The agent is expected to manually call `project_onboard` or `session_context` separately.

**Decision needed**: Add a single `project_action` method/tool that takes the chosen option and executes the right sequence internally.

### F5. No detection of stale/unclosed sessions

[`db.py:644`](july/db.py:644) — `session_start` checks for duplicate `session_key` but nothing in the codebase checks whether a project has an active (non-closed) session before starting a new one. This means `project_entry` cannot warn about abandoned sessions.

**Decision needed**: Add a query to find active sessions for a project key. Surface this in `project_entry` response.

### F6. `classify_checkpoint` keyword matching is the only heuristic

[`project_conversation.py:645`](july/project_conversation.py:645) — The `store_directly` path requires ALL of: durable keyword match, reusable keyword match, text >= 40 chars with connector words, AND no tentative keywords. This is strict — many clearly reusable findings (e.g. "Error: Claude MCP fails with SSE transport, fix is to use stdio") would fall to `ignore` because they might not match all four conditions simultaneously.

**Decision**: Add a secondary high-confidence path: if the text matches a `resolved_error` or `decision` kind AND has a minimum length AND no sensitive patterns, promote to `store_directly` even without all four keyword conditions.

---

## 2. Implementation Plan

### Block A: Enrich `project_entry` proactive recall

**Objective**: Make cross-project intelligence work on project entry by searching against meaningful content instead of the bare project key.

**Files to modify**:
- [`july/project_conversation.py`](july/project_conversation.py)

**Changes**:

1. In [`project_entry()`](july/project_conversation.py:118), after calling `analyze_repository()` (which is currently only called inside `project_onboard`), extract a lightweight recall query from available context:
   - For `"new"` state: build a recall query from the repo README objective + detected stack + detected integrations. This requires calling a subset of `analyze_repository` — specifically just `collect_consulted_files` + `read_limited_text` + `extract_objective` + `detect_stack` + `detect_integrations`. Extract these into a new function `build_recall_query_from_repo()`.
   - For `"partial"` and `"known"` states: build the recall query from the existing context summary + latest memory title + latest session summary.

2. Replace line 129: `recall = self.database.proactive_recall(resolved_project_key, ...)` with `recall = self.database.proactive_recall(recall_query, project_key=resolved_project_key, limit=5)`.

3. Add the recall query to the returned dict so the agent can see what July searched on.

**New function**:
```
def build_recall_query_from_repo(repo_root: Path) -> str
```
Reads README + manifest + stack detection (reusing existing helpers) and returns a ~200 char string suitable for FTS search.

**New function**:
```
def build_recall_query_from_context(
    project_ctx: dict, sessions: list[dict]
) -> str
```
Extracts key terms from the latest memory title, session summary, and project tasks.

**Tests needed**:
- `test_project_entry_recall_uses_repo_content_not_just_key` — verify that `related_context` for a new repo with "MCP" in the README finds cross-project MCP memories.
- `test_project_entry_recall_uses_existing_context_for_known_project` — verify that for a known project, recall searches against the summary, not the key.

---

### Block B: Add staleness detection to `assess_project_state`

**Objective**: Downgrade `"known"` to `"partial"` when the latest session is too old.

**Files to modify**:
- [`july/project_conversation.py`](july/project_conversation.py)

**Changes**:

1. Modify [`assess_project_state()`](july/project_conversation.py:341) signature to accept an optional `staleness_days: int = 30` parameter.

2. After the existing `"known"` determination (line 348), check the `started_at` of the newest session. If older than `staleness_days`, return `"partial"` instead of `"known"`.

3. Add a `"stale_context"` key to the return value — but since `assess_project_state` currently returns a bare string, change it to remain a string (to avoid breaking callers) and add a separate `detect_staleness()` function that `project_entry` calls to annotate the result.

**Actually, simpler approach**: Keep `assess_project_state` returning a string. Add a new function:

```
def detect_context_staleness(
    sessions: list[dict], staleness_days: int = 30
) -> dict
```

Returns `{"is_stale": bool, "days_since_last_session": int | None, "last_session_date": str | None}`.

Then in `project_entry`, if the state is `"known"` and `is_stale` is True, downgrade to `"partial"` and append a staleness note to the context summary.

**Tests needed**:
- `test_known_project_downgrades_to_partial_when_stale` — create a project with old sessions, verify state becomes `"partial"`.
- `test_known_project_stays_known_when_recent` — verify no downgrade for fresh sessions.

---

### Block C: Add `project_action` to close the post-entry flow

**Objective**: When the agent or user picks an option from `project_entry`, a single call executes the right action.

**Files to modify**:
- [`july/project_conversation.py`](july/project_conversation.py)
- [`july/mcp.py`](july/mcp.py)
- [`july/cli.py`](july/cli.py)

**New method on `ProjectConversationService`**:

```python
def project_action(
    self,
    *,
    action: str,  # "analyze_now" | "resume_context" | "refresh_context" | "continue_without_context"
    repo_path: str | None = None,
    project_key: str | None = None,
    agent_name: str = "july",
    goal: str | None = None,
) -> dict[str, Any]
```

**Behavior per action**:

| Action | What it does | Returns |
|--------|-------------|---------|
| `analyze_now` | Calls `self.project_onboard(...)` internally. Full read-only onboarding. | Onboarding result with snapshot, session, and analysis. |
| `resume_context` | Calls `self.database.session_context(project_key=...)` + `self.database.project_context(...)` + starts a new session. Returns consolidated context. | `{"session": ..., "context_summary": ..., "latest_session": ..., "ready_memories": [...], "pending_tasks": [...], "suggested_next_step": ...}` |
| `refresh_context` | Calls `analyze_repository()` read-only to get current repo state. Compares against stored memory snapshot. Returns delta. Does NOT re-onboard fully — just identifies what changed. Starts a new session. | `{"session": ..., "changes_detected": [...], "current_analysis": ..., "previous_summary": ...}` |
| `continue_without_context` | Starts a session but skips context recovery. Returns minimal ack. | `{"session": ..., "message": "Session started without context recovery."}` |

**All actions start a session automatically** with a generated session key like `entry-{project_key}-{timestamp}`. This is where auto-session management lives — scoped only to `project_action`, not as a global behavior. This avoids session garbage because:
- Sessions are only created when the user explicitly responds to the entry prompt.
- The session key includes the project and timestamp, so duplicates are impossible.
- If the previous session was never closed, `project_entry` already shows the `active_session` warning (added in Block D).

**Tests needed**:
- `test_project_action_analyze_now_runs_onboarding` — verify it produces the same result as calling `project_onboard` directly.
- `test_project_action_resume_context_returns_consolidated_context` — verify it returns sessions, memories, tasks, and a suggested next step.
- `test_project_action_refresh_context_detects_changes` — verify it identifies when the repo has changed since the last snapshot.
- `test_project_action_continue_without_context_starts_session_only` — verify minimal response.
- `test_project_action_auto_starts_session` — verify all actions create a new session automatically.

---

### Block D: Detect unclosed sessions in `project_entry`

**Objective**: Warn when there's an active session that was never closed.

**Files to modify**:
- [`july/db.py`](july/db.py)
- [`july/project_conversation.py`](july/project_conversation.py)

**New method on `JulyDatabase`**:

```python
def find_active_sessions(
    self, project_key: str
) -> list[dict]
```

Query: `SELECT ... FROM sessions WHERE project_key = ? AND status = 'active' ORDER BY id DESC`.

**Changes to `project_entry`**:

After getting sessions, check for active (unclosed) sessions. If found, add to the response:

```python
"active_sessions": [{"session_key": ..., "started_at": ..., "goal": ...}],
"active_session_warning": "Hay una sesion anterior sin cerrar. Quieres que la cierre y abra una nueva?"
```

Also add a new option to `build_entry_prompt` when active sessions exist:

```python
{"id": "close_stale_and_continue", "label": "Cierra la sesion anterior y abre una nueva"}
```

And handle `close_stale_and_continue` in `project_action` — close the stale session with a generated summary, then proceed as `resume_context`.

**Tests needed**:
- `test_project_entry_warns_about_unclosed_sessions` — create an active session, call `project_entry`, verify the warning appears.
- `test_project_action_close_stale_closes_and_resumes` — verify it closes the old session and starts a new one.

---

### Block E: Fix `conversation_checkpoint` confirmation flow

**Objective**: Allow agents to persist a checkpoint after getting user confirmation for `ask_user` results.

**Files to modify**:
- [`july/project_conversation.py`](july/project_conversation.py)

**Change**:

In [`conversation_checkpoint()`](july/project_conversation.py:261), change the persist condition from:

```python
if persist and checkpoint["action"] == "store_directly":
```

to:

```python
if persist and checkpoint["action"] in ("store_directly", "ask_user"):
```

This means: if the agent passes `persist=True`, it overrides `ask_user` because the agent has already asked and received confirmation. The `ignore` action (sensitive data) is still never persisted — it stays blocked.

Add `checkpoint["persisted_via_confirmation"] = True` when this override fires, so the agent knows it was a confirmed persist.

**Tests needed**:
- `test_checkpoint_ask_user_can_be_persisted_with_confirm` — send a tentative note with `persist=True`, verify it gets stored.
- `test_checkpoint_ignore_cannot_be_persisted_even_with_confirm` — send a sensitive note with `persist=True`, verify it is NOT stored.
- Existing test `test_conversation_checkpoint_asks_for_tentative_note` must still pass (without `persist=True`).

---

### Block F: Improve `classify_checkpoint` heuristic

**Objective**: Recognize high-confidence findings that don't match all four keyword conditions.

**Files to modify**:
- [`july/project_conversation.py`](july/project_conversation.py)

**Change to [`classify_checkpoint()`](july/project_conversation.py:645)**:

After the sensitive check, before the current four-condition `store_directly` block, add a secondary path:

```python
kind = detect_checkpoint_kind(lowered)
is_high_confidence_kind = kind in ("resolved_error", "decision")
is_substantial = len(text.strip()) >= 60
has_connector = any(t in lowered for t in (" porque ", " para ", " con ", " sin ", " ya que ", " debido "))

if is_high_confidence_kind and is_substantial and has_connector and not tentative:
    action = "store_directly"
    reason = "Hallazgo de alta confianza: tipo reconocido, sustancial y conectado."
```

This catches findings like: `"Error: el MCP de Claude falla con SSE, la causa era que July usaba stdio incorrecto. Solucion: configurar stdio explicitamente en el transport."` — which would match `resolved_error` kind, has 100+ chars, has ` la causa ` connector, and no tentative keywords.

**Tests needed**:
- `test_checkpoint_resolved_error_stores_directly_even_without_all_keywords` — verify a clearly resolved error gets `store_directly`.
- `test_checkpoint_decision_stores_directly_with_connector` — verify a clear decision gets `store_directly`.
- Existing tests must still pass.

---

## 3. MCP and CLI Contract

### New MCP tool: `project_action`

**Why it can't be done with existing tools**: Currently, after `project_entry`, the agent must manually decide whether to call `project_onboard`, `session_context`, or `session_start` and in what combination. This is the exact "agent must figure out the plumbing" problem that makes July feel like infrastructure instead of a collaborator. `project_action` closes the loop in one call.

```python
ToolSpec(
    name="project_action",
    title="Project Action",
    description="Execute the action chosen from project_entry options. Handles onboarding, context recovery, refresh, or session start.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["analyze_now", "resume_context", "refresh_context",
                         "continue_without_context", "close_stale_and_continue"],
                "description": "Action chosen from project_entry options."
            },
            "repo_path": {"type": "string"},
            "project_key": {"type": "string"},
            "agent_name": {"type": "string"},
            "goal": {"type": "string"},
        },
        "required": ["action"],
    },
    handler=self.tool_project_action,
)
```

### New CLI command: `project-action`

```
july project-action <action> [--repo-path PATH] [--project-key KEY] [--agent NAME] [--goal GOAL]
```

### No changes to existing tools

All existing 20 MCP tools and 30 CLI commands remain unchanged. `project_entry`, `project_onboard`, and `conversation_checkpoint` keep working as before — `project_action` is additive, not a replacement.

### Updated counts after this block

- **21 MCP tools** (was 20).
- **31 CLI commands** (was 30).

---

## 4. Acceptance Criteria

### AC1: New project entry with cross-project recall

1. Create a fresh repo with "MCP" in the README.
2. Populate July's memory with a resolved MCP error from another project.
3. Call `project_entry` on the new repo.
4. Verify `related_context.suggestions` contains a `cross_project` suggestion referencing the MCP memory.

### AC2: Stale known project downgrades to partial

1. Run `project_onboard` on a repo.
2. Manually set the session `started_at` to 45 days ago in the DB.
3. Call `project_entry`.
4. Verify `project_state` is `"partial"`, not `"known"`.
5. Verify context summary mentions staleness.

### AC3: project_action analyze_now runs full onboarding

1. Call `project_entry` on a new repo. Get state `"new"`.
2. Call `project_action` with `action="analyze_now"`.
3. Verify a snapshot memory was created, a session was started and closed, and the analysis matches what `project_onboard` would produce.
4. Call `project_entry` again. Verify state is now `"known"`.

### AC4: project_action resume_context recovers context

1. Run `project_onboard` on a repo.
2. Call `project_action` with `action="resume_context"`.
3. Verify the response includes the previous session summary, ready memories, pending tasks, and a suggested next step.
4. Verify a new session was started automatically.

### AC5: project_action refresh_context detects changes

1. Run `project_onboard` on a repo.
2. Add a new file (e.g. `package.json`) to the repo.
3. Call `project_action` with `action="refresh_context"`.
4. Verify `changes_detected` includes the new stack element.

### AC6: Unclosed session detection

1. Start a session for a project. Do not close it.
2. Call `project_entry`.
3. Verify `active_sessions` is non-empty and `active_session_warning` is present.
4. Call `project_action` with `action="close_stale_and_continue"`.
5. Verify the old session is closed and a new one is active.

### AC7: conversation_checkpoint confirmation flow

1. Submit a tentative note via `conversation_checkpoint` without `persist`. Get `action: ask_user`.
2. Submit the same note with `persist=True`. Verify it gets stored.
3. Submit a note with `api_key=sk-test` and `persist=True`. Verify it is NOT stored (`action: ignore`).

### AC8: Improved checkpoint heuristic

1. Submit: `"Error resuelto: el MCP de Claude falla con SSE porque July usaba el transport incorrecto. Solucion: usar stdio."` without `persist`.
2. Verify `action` is `"store_directly"`.

### AC9: All existing tests pass

Run `python -m pytest tests/` and verify zero regressions.

---

## 5. What NOT to Do Yet

| Item | Reason |
|------|--------|
| Embeddings / vector search | FTS5 is sufficient for this step. Cross-project recall improves dramatically just by searching on better input text. |
| Roo Code integration | MCP already works with any agent. No special connector needed. |
| Visual panel / TUI | Not needed for conversational UX. |
| SQLite schema changes | Everything works on the current 12 tables. `find_active_sessions` is just a query on the existing `sessions` table. |
| Writing files in external repos | July stores internally. No `JULY_CONTEXT.md` creation. |
| New dependencies | All changes use Python stdlib + existing July code. |
| Auto-session on every MCP call | Too noisy, creates garbage sessions. Sessions are only auto-created inside `project_action`, scoped to explicit user choices. |
| LLM-based checkpoint validation | The heuristic improvement in Block F is sufficient for now. LLM refinement can come later. |
| `project_entry` auto-calling on MCP initialize | The agent decides when to call it. July shouldn't force it. |
| Contradiction detection (memory says Flask, repo now has package.json) | Nice to have but requires diffing stored snapshots against live repo state. Defer to v0.5 after `refresh_context` proves useful. |

---

## 6. Execution Order

```
Block E (checkpoint confirmation) — smallest, no new API surface
Block F (checkpoint heuristic) — small, isolated change
Block B (staleness detection) — small, feeds into Block C
Block D (unclosed session detection) — small, feeds into Block C
Block A (enrich project_entry recall) — medium, improves existing tool
Block C (project_action) — largest, depends on A+B+D, adds new tool
```

After Block C is done: update `README.md`, `ROADMAP.md`, and `AGENTS.md` per the documental update rule.
