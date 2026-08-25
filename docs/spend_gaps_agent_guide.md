# Spend Data Quality Agent — Architecture Guide

## What it is

A conversational, tool-calling AI agent that answers questions about spend data quality — specifically, spend transactions whose Oracle account number, department code, or activity ID has no matching row in the corresponding reference table.

It's exposed in the app at **Reports → Data Quality Agent** (`/reports/spend-gaps`).

## Why it exists

Three MySQL views already existed in the database, built for exactly this kind of investigation:

- `v_spend_account_gaps`
- `v_spend_department_gaps`
- `v_spend_activity_gaps`

(All three defined in `server/src/db/init_db.py:333-409`.) They were only queryable by hand via a MySQL client — no API endpoint or UI surfaced them, so finding a data quality gap meant knowing these views existed and writing SQL yourself. This feature makes that investigation available to anyone in the app, conversationally.

## Design decisions

| Decision | Choice | Why |
|---|---|---|
| LLM | **Local, via Ollama** (`qwen2.5:14b`) | No cloud API, no API key/secret management, no spend/reference data ever leaves the machine. Qwen2.5 has the most reliable tool-calling of the locally-runnable models at a size that fits a 32GB dev machine. |
| Tool scope | **Exactly 3 read-only tools**, one per gap view | Keeps the agent focused and auditable. No write/mutate tools, no broader spend-query tools. |
| Conversation state | **Stateless per-request** | The frontend holds message history in React state and resends the full array each turn. No new DB table, no session management. |
| Streaming | **None (v1)** | Neither this backend nor frontend had any streaming precedent before this feature — the only `StreamingResponse` usage anywhere was a CSV export that buffers a full string. Introducing token-by-token streaming is a separable, larger lift, deferred as a fast-follow. |

## Architecture

```
┌─────────────────────┐        ┌──────────────────────────────────────────┐
│  Browser (React)    │        │  FastAPI backend (server/)                │
│                      │        │                                          │
│  SpendGapsAgentPage  │  POST  │  POST /api/spend/reports/gaps-agent/chat  │
│  - message[] state   │───────>│  (require_any auth)                      │
│  - textarea input    │  JSON  │        │                                  │
│  - mutation hook      │        │        ▼                                  │
│  (axios, stateless —  │<───────│  gap_agent_service.run_agent_chat()      │
│   full history sent   │  JSON  │    │                                     │
│   every turn)         │        │    │  1. seed system prompt + history    │
└─────────────────────┘        │    │  2. call Ollama (async) w/ tools     │
                                 │    │  3. if tool_calls: run local Python  │
                                 │    │     fn against the 3 gap views,      │
                                 │    │     append tool result, loop (≤5x)   │
                                 │    │  4. else: return final message       │
                                 │    ▼                                      │
                                 │  ┌─────────────────────────────┐          │
                                 │  │ ollama.AsyncClient           │          │
                                 │  └───────────┬───────────────────┘          │
                                 └──────────────┼───────────────────────────────┘
                                                │  HTTP, localhost:11434
                                                ▼
                                 ┌─────────────────────────────────┐
                                 │  Ollama server (local process)   │
                                 │  model: qwen2.5:14b               │
                                 └─────────────────────────────────┘

                                 ┌─────────────────────────────────┐
                                 │  MySQL (existing)                 │
                                 │  v_spend_account_gaps             │
                                 │  v_spend_department_gaps          │
                                 │  v_spend_activity_gaps            │
                                 │  (queried directly by the 3 tool  │
                                 │   functions via the existing      │
                                 │   SQLAlchemy session — same DB    │
                                 │   the rest of the app already     │
                                 │   uses, no new connection)         │
                                 └─────────────────────────────────┘
```

## Request lifecycle, one user turn

1. Browser sends the *entire* conversation so far (`messages: [{role, content}, ...]`) — the backend is stateless and has no memory between requests.
2. Backend prepends a fixed system prompt, calls Ollama with the conversation plus the 3 tool schemas.
3. If the model responds with `tool_calls`, the backend executes the matching Python function directly against MySQL (no network hop beyond the existing DB connection), serializes the result as JSON, appends it as a `role: "tool"` message, and calls Ollama again — repeating up to `MAX_ITERATIONS` (5) times as a runaway-loop guard.
4. Once the model responds with plain text (no more tool calls), that becomes the final answer, returned to the browser along with a log of which tools were called (rendered as small chips under the assistant's message for transparency).
5. Browser appends the assistant's reply to its local `messages` state. Nothing is persisted server-side — refreshing the page loses the conversation.

## Trust / data-flow boundary

The LLM never gets raw database credentials or arbitrary query access. It can only invoke the 3 named, hardcoded tool functions, each of which runs a fixed, parameterized SQL statement — only `limit` is model-controlled, and it's bound as a SQL parameter, never string-interpolated. The model cannot read, write, or touch any table/view beyond the 3 gap views. Everything runs locally on the developer's machine (Ollama + FastAPI backend both on localhost).

## Key files

| File | Role |
|---|---|
| `server/src/services/gap_agent_service.py` | Tool implementations, tool JSON schemas, the agent loop (`run_agent_chat`) |
| `server/src/api/spend.py` | `POST /reports/gaps-agent/chat` endpoint (thin — delegates to the service) |
| `server/src/schemas/spend.py` | `SpendAccountGapRow` / `SpendDepartmentGapRow` / `SpendActivityGapRow`, `ChatMessage`, `GapAgentChatRequest`, `GapAgentChatResponse`, `ToolCallLog` |
| `server/src/core/config.py` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` settings (both have sensible defaults — no `.env` changes required to run locally) |
| `server/tests/test_gap_agent_service.py` | Tool-function tests (real SQLite queries against the gap views) + chat-endpoint tests (Ollama fully mocked — no live model call ever runs in CI) |
| `client/src/pages/Reports/SpendGapsAgentPage.jsx` | Chat UI |
| `client/src/data/spend/api.js`, `hooks.js` | `chatWithGapsAgent()` / `useGapsAgentChat()` |

## Running it locally

1. Install Ollama and confirm it's reachable:
   ```bash
   ollama --version
   curl http://localhost:11434/api/tags   # should return 200, not connection-refused
   ```
   If it's not running: `ollama serve`.
2. Pull the model (one-time, ~9GB):
   ```bash
   ollama pull qwen2.5:14b
   ollama list   # confirm qwen2.5:14b appears
   ```
3. Start the app as usual: `make dev-db && make dev-api && make dev-client`.
4. Go to **Reports → Data Quality Agent**, ask a question. If Ollama isn't running, the page shows an inline "local model unavailable" error rather than hanging.

## Extending it

- **Add a new tool**: write a function following the pattern of `get_account_gaps`/`get_department_gaps`/`get_activity_gaps` in `gap_agent_service.py`, add its JSON schema to `TOOLS`, and register it in `TOOL_IMPL`. The agent loop needs no changes.
- **Different local model**: change `OLLAMA_MODEL` in `.env` (or the default in `config.py`). Any Ollama model with tool-calling support should work; smaller models will be faster but less reliable at correctly formatting tool calls.

## Deliberately out of scope for v1

- **Streaming** responses (SSE/token-by-token).
- **Conversation persistence** across page refreshes (no DB table for chat history).
- **Broader tool set** — no general spend-query tools, no write/mutate tools.
- **Retry/backoff** on the Ollama call beyond a single try/except — this is the first outbound network call anywhere in this backend, so a generic resilience framework wasn't built prematurely.
- **Markdown rendering** of the agent's responses (plain text only).

See the implementation plan this was built from for the full reasoning behind each of these: `~/.claude/plans/spend-gap-detection-agent-valiant-scone.md` (local to the machine this was planned on, not checked into the repo).
