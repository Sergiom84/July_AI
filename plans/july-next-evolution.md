# July: Next Evolution — Conversational Project Intelligence

## What This Document Is

A product and behavior proposal for July's next step. Not a technical spec. Not a list of commands. A definition of how July should feel, act, and think when it enters a project.

---

## Core Identity

July is a **conversational architect and collaborator** that lives alongside the developer. When it enters a project — through VS Code, through a terminal, through any MCP client — it behaves like a colleague who:

- Remembers what happened before.
- Knows when it's entering unfamiliar territory.
- Proposes the right next step instead of waiting for instructions.
- Stores what matters without being asked.
- Asks before storing what's ambiguous.
- Never pollutes the project with files it wasn't invited to create.

July is not a CLI. July is not a search engine. July is memory that thinks.

---

## The Entry Conversation

Every time July connects to a project, the first thing it does is **understand where it is**. This is not a command the user runs. This is behavior that happens automatically when an agent with July's MCP tools starts working.

### New Project

> "Hola, soy July. Veo que este proyecto es nuevo para mi. Puedo analizarlo ahora para tener una primera foto util, o esperar a que me digas que necesitas. Que prefieres?"

If the user says yes:

1. July reads the repo in a non-invasive, read-only pass: README, manifests, entrypoints, visible structure.
2. Builds an internal snapshot: objective, stack, integrations, open questions, suggested next step.
3. Stores that snapshot in its own database as project memory + a session summary.
4. Checks cross-project memory for related knowledge: "In another project we solved JWT with refresh tokens in httpOnly cookies. Want me to pull that context here?"
5. Does **not** write any file in the external repo.

### Known Project

> "Hola, soy July. Ya tenemos contexto de este proyecto. La ultima vez: [summary]. El siguiente paso pendiente era: [next step]. Quieres que retomemos desde ahi?"

If context is still valid, July skips the onboarding. If the repo has changed significantly since the last session, July proposes a selective refresh: only what changed, not a full re-read.

### Partial Context

> "Hay contexto parcial de este proyecto: se que [what July knows], pero falta una foto completa. Quieres que refresque lo que falta?"

This is the trickiest state. July has some data but not enough to be useful. The response should be surgical: fill the gaps, not redo everything.

---

## How July Distinguishes Project States

Current implementation in [`assess_project_state()`](july/project_conversation.py:341) uses heuristic signals. The refined criteria should be:

### New

All of these are true:
- No ready memory linked to the project.
- No session with a non-empty summary.
- No tasks linked to the project.
- No inbox items with useful context.

Signal: July has nothing reusable. Full onboarding is appropriate.

### Partial

At least one of these is true, but not all three:
- There is some inbox or memory linked to the project.
- There are sessions, but none with a useful summary or next steps.
- There is context, but it does not explain what the project is, where it stands, or what to do next.

Signal: July knows something, but not enough to resume without asking. A selective refresh makes sense.

### Known

All three of these are true:
- Ready memory exists that explains what the project is.
- At least one session has a summary with next steps.
- The context is sufficient to resume work without re-reading the repo from scratch.

Signal: July can recover context and propose a continuation directly.

### Refinement over current implementation

The current [`assess_project_state()`](july/project_conversation.py:341) already checks `has_ready_memory`, `has_summary`, and `has_next_step`. The main improvements needed are:

1. **Staleness check**: If the last session is older than N days, treat "known" as "partial" and suggest a selective refresh.
2. **Contradiction check**: If ready memory says "stack is Python + Flask" but the repo now has a `package.json`, flag it as "partial with drift."
3. **Utility threshold**: A single inbox item that says "look at this project later" should not make the project "partial." The context must be actionable.

---

## Initial Questions July Should Ask

The goal: maximum useful context with minimum friction. July should not feel like a form. It should feel like a colleague who asks the right question at the right time.

### On first entry to a new project

1. **"Quieres que lo analice ahora, prefieres esperar o no haga nada?"**
   This is the gatekeeper. If the user says no, July stays silent until asked.

2. **After onboarding, only if needed:**
   - "He detectado [stack/integration]. Cual es tu objetivo principal ahora mismo?" — Only if the objective is not clear from the README.
   - "Hay algo especifico donde quieras que te ayude primero?" — Open-ended, one question, not five.

### During iteration

July should **not** interrupt with questions unless it has something to offer. The rule is:

- If July detects a **reusable finding** (error resolved, decision made, workflow improvement): persist it silently if the signal is strong, or ask once: "Esto parece reutilizable. Lo guardo?"
- If July detects **cross-project relevance** (the same pattern was solved in another project): surface it naturally: "Ya resolvimos algo parecido en [project]. Quieres que traiga ese contexto?"
- If July detects **ambiguity** (tentative idea, unverified approach): ask once: "Esto todavia es tentativo. Quieres que quede como referencia o prefieres que lo ignore?"

### At session close

July should propose the summary, not demand it:

- "Hemos avanzado en [summary]. Quieres que guarde un resumen antes de cerrar?"
- If the user says no or leaves, July should still try to auto-save a minimal session note with what was accomplished.

### Questions July should NEVER ask

- "What is your project about?" — when the README already answers that.
- "What technologies are you using?" — when the manifest files already answer that.
- "Do you want me to save this?" — for clearly durable, reusable, non-sensitive findings. Just save it.
- Multiple questions in sequence. One question at a time, maximum.

---

## What July Should Save, Ask About, or Ignore

### Save automatically (no confirmation needed)

| Signal | Example |
|--------|---------|
| Resolved error with cause and fix | "The MCP connection failed because July was using stdio and Claude expected SSE. Fix: switch to stdio transport explicitly." |
| Architectural decision with rationale | "We chose Supabase over Firebase because of Row Level Security and PostgREST compatibility." |
| Workflow improvement that saves time | "Running bootstrap.ps1 before july.ps1 avoids Python version conflicts." |
| Project snapshot from onboarding | Initial read-only repo analysis. |
| Session summary at close | What was done, discoveries, next steps. |
| Cross-project reusable knowledge | If a solution was already used in another project and is being applied here. |

### Ask before saving

| Signal | Example |
|--------|---------|
| Tentative idea not yet validated | "Maybe we should try a different auth flow." |
| Observation that needs more context | "The API seems slow, but I haven't profiled it yet." |
| External proposal not yet adopted | A model suggested something, but the user hasn't decided. |
| Information that might be private | User mentions a client name, an internal URL, or a personal preference. |

### Never save automatically

| Signal | Example |
|--------|---------|
| Secrets, tokens, API keys | Anything matching `sk-`, `api_key=`, `password`, `secret`, `bearer`. |
| Ephemeral logs without conclusion | Raw error output without diagnosis. |
| Redundant information already in the repo | Re-storing what the README already says. |
| Very short-lived tasks | "Run npm install" — it doesn't survive the session. |
| Opinions without decision or utility | "I think React is better than Vue" without project context. |

The current [`classify_checkpoint()`](july/project_conversation.py:645) already implements a version of this with pattern matching. The refinement needed is:

1. **Raise the bar for `store_directly`**: Currently requires `durable AND reusable AND specific AND NOT tentative`. This is good but misses findings that are clearly a resolved error or a confirmed decision even without matching all keyword patterns.
2. **Add a `high_confidence_store` path**: If July's LLM layer is active, use it to validate whether a finding is truly durable before auto-storing.
3. **Make `ask_user` actually conversational**: The current implementation sets a `question` field, but no mechanism delivers that question to the user conversationally. This is the key gap.

---

## Cross-Project Intelligence

This is where July becomes genuinely valuable. The scenario the user described:

> If July detects that this project doesn't have MCP configured yet, and in another project there were problems configuring Claude's MCP, July should say: "We already solved something similar in another project. Want me to help you configure it like we did there?"

The mechanism for this already exists in [`proactive_recall`](july/mcp.py:672). What's missing is:

1. **Triggering it at the right moment**: Currently proactive recall only fires on `capture_input`. It should also fire on `project_entry` and `project_onboard` — when July is assessing the project for the first time.
2. **Surfacing it conversationally**: The recall result includes `cross_project` suggestions, but the agent needs instructions to present them naturally instead of dumping JSON.
3. **Topic key bridging**: If "mcp/integration" is a topic key with linked knowledge from project A, and project B mentions MCP in its README, July should connect the dots automatically.

---

## The Delivery Mechanism

July does not have a UI. July does not need a UI. July speaks through whatever agent is running.

### Via MCP (primary channel)

When an agent like Roo Code, Claude, or Codex connects to July's MCP server, the agent should:

1. Call `project_entry` at the start of every conversation to get the opening state.
2. Use the returned `greeting`, `question`, and `options` to present a natural opening.
3. During the conversation, call `conversation_checkpoint` when it detects something worth persisting.
4. At the end, call `session_summary` and `session_end`.

The agent is the delivery layer. July is the intelligence layer. This separation is fundamental.

### Via terminal

For users working directly in a terminal, July's CLI already exposes the same tools. The experience is less conversational but still useful for debugging and manual inspection.

### What makes it feel conversational

The conversational quality does not come from July having a chat window. It comes from:

- **The opening state being context-aware**: Not "What do you want to do?" but "Last time we were working on X. The next step was Y."
- **Findings being offered, not demanded**: Not "Do you want to save this?" for everything, but silent storage for clear signals and gentle offers for ambiguous ones.
- **Cross-project connections surfacing naturally**: Not "Here are 12 related memories" but "We solved this exact problem in Vocabulario. Want that context?"
- **Session closure being automatic**: Not "Please run session-end" but the agent closing the session naturally when the conversation ends.

---

## Minimum Viable Next Step

The question: what is the smallest change that makes July noticeably better without adding unnecessary complexity?

### Step 1: Enrich project_entry with cross-project intelligence

**What exists**: [`project_entry()`](july/project_conversation.py:118) already calls `proactive_recall` and returns `related_context`. But the recall is done against the project key as text, which is too generic.

**What to change**: Run proactive recall against the project's detected objective, stack, and open questions. If the project mentions "MCP" and July has memories about MCP problems in another project, those should appear in `related_context` with a clear cross-project label.

### Step 2: Add staleness detection to project state

**What exists**: [`assess_project_state()`](july/project_conversation.py:341) checks for ready memory, summaries, and next steps.

**What to change**: Add a timestamp check. If the newest session summary is older than a configurable threshold, downgrade "known" to "partial" and suggest a selective refresh.

### Step 3: Make conversation_checkpoint deliver its question

**What exists**: [`conversation_checkpoint()`](july/project_conversation.py:233) returns `action: ask_user` with a `question` field, but there is no mechanism to actually present this to the user.

**What to change**: When the MCP tool returns `ask_user`, the response should include a `pending_confirmation` structure that the agent can use to ask the user directly. If the user confirms, a follow-up call with `persist=True` stores it.

### Step 4: Auto-session management in project_entry

**What exists**: Sessions require explicit `session_start` and `session_end` calls.

**What to change**: When `project_entry` is called and no active session exists for this project, automatically start one. When the agent conversation ends without an explicit `session_end`, leave the session open but mark it as `inactive` so the next `project_entry` can detect it and ask: "Hay una sesion anterior sin cerrar. Quieres que la cierre y abra una nueva?"

---

## What This Proposal Does NOT Include

- Embeddings or vector search. FTS5 is sufficient for this step.
- Roo Code integration. The MCP channel already works with any agent.
- Visual panel or TUI. Not needed yet.
- Schema changes to SQLite. Everything proposed works on the current 12-table schema.
- Writing files in external repos. July stores everything internally.
- New dependencies. Everything proposed uses existing Python stdlib + July's current stack.

---

## Alignment with July's Vision

This proposal reinforces the core principles from [README.md](README.md) and [ROADMAP.md](ROADMAP.md):

- **Local-first**: All intelligence runs on the user's machine.
- **Conversational UX**: CLI and MCP are infrastructure; the user experience is natural language.
- **Anti-regression**: July prevents repeating work by remembering what was done and what was decided.
- **Non-invasive**: July never modifies the external project unless explicitly asked.
- **Multi-agent**: Any agent can use July's MCP tools. July is the memory, the agent is the voice.
- **Incremental**: Each step makes July better without requiring a rewrite.

---

## Summary of Actionable Steps

1. Enrich `project_entry` proactive recall with objective/stack/questions, not just project key.
2. Add staleness detection to `assess_project_state`.
3. Add `pending_confirmation` flow to `conversation_checkpoint` for `ask_user` results.
4. Add auto-session management in `project_entry`: start session if none active, detect stale sessions.
5. Improve `classify_checkpoint` to recognize high-confidence patterns beyond keyword matching.
6. Document the agent contract: what an MCP client should call and when, so any agent can implement the conversational flow correctly.
