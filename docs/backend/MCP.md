# Model Context Protocol (MCP) Integration

> **Status:** Deferred — design doc stands; scheduled for a future themed release (was S5 / v2.42 scope-out).
> **Scope:** External "Overseer assistant" surface — NOT a replacement for the in-game dweller chat agent.

## 1. What is MCP (in this context)

[Model Context Protocol](https://modelcontextprotocol.io) is an open standard that lets AI
applications (Claude Desktop, Cursor, custom agents, …) connect to external capabilities through
three primitives:

| Primitive | Purpose | Example |
|---|---|---|
| **Tools** | Actions the model can invoke (user-approvable) | `assign_dweller_to_room(...)` |
| **Resources** | Read-only data the model can fetch on demand | `vault://{id}/state` |
| **Prompts** | Reusable prompt templates | `overseer_daily_briefing(vault_id)` |

This project already uses **PydanticAI** for the in-game dweller chat agent (with tools like room
listing and activity briefing). MCP is complementary: it exposes the same game capabilities through
a **standard protocol** so any MCP-capable client can act as an "AI Overseer" without bespoke glue
code.

## 2. Why (and why not)

### Makes sense

- **External AI assistant / companion.** Users ask Claude Desktop, Cursor, or a bot things like
  *"Who should I send to the wasteland today?"* — the model reads vault state, then issues actions.
- **Dev/admin AI surface.** Ask *"Why is vault 42 low on power?"* — the model pulls rooms, dweller
  assignments, and resource warnings without a new endpoint being written.
- **Discoverability + reusability.** One MCP server feeds any MCP-capable client. Schemas and
  descriptions are self-documenting.
- **User-controlled permissions.** MCP clients surface tool calls for approval — fits a game where
  actions cost resources.

### Does NOT make sense

- **Replacing the dweller chat path.** The in-game agent already has a tight PydanticAI loop with
  structured output (`DwellerChatOutput`), sentiment scoring, and happiness side effects. Wrapping
  that in MCP adds latency and complexity for no gain.
- **Real-time game control from the frontend.** The Vue app talks to the REST API / WebSocket /
  SSE directly — that stays.

## 3. Proposed architecture

Two viable shapes; **Option A is recommended**.

### Option A — MCP server inside the backend (`backend/app/mcp/`)

A new module that imports existing services and registers them as MCP tools/resources/prompts.
Runs over `stdio` (local clients) or **Streamable HTTP** over HTTP (web clients). SSE transport
is retained only as a legacy compatibility option for older clients; new remote integrations
should use Streamable HTTP.

```text
backend/app/mcp/
├── server.py          # FastMCP instance + registration
├── auth.py            # Bearer-token auth for Streamable HTTP transport
├── tools/
│   ├── vault.py       # get_vault_summary, build_room, pause/resume
│   ├── dweller.py     # list_dwellers, assign_to_room, start_training
│   └── exploration.py # send_to_wasteland, recall_from_wasteland
├── resources.py       # vault://, dweller://, map://, notifications://
└── prompts.py         # overseer_daily_briefing, vault_triage
```

- Every tool **delegates to the existing service layer** (`vault_service`, `dweller_service`,
  `training_service`, `exploration_service`, `game_loop_service`) — never CRUD directly.
- Auth reuses the existing JWT flow (bearer token → `get_current_user`-style dependency) and
  `get_user_vault_or_403` ownership checks.
- Quota/credits: action tools should respect the same quota service used by chat, to avoid
  unlimited AI-driven resource spending.

### Option B — standalone MCP bridge

A thin Python process that calls the running FastAPI backend over its existing REST API. Keeps the
game server decoupled and allows versioning the MCP surface independently, but adds a moving part,
double validation, and a second failure domain. Only worth it if the MCP surface must be deployed
separately (e.g., a public sandbox).

## 4. Concrete MCP surface

### Tools (actions)

| Tool | Maps to |
|---|---|
| `get_vault_summary(vault_id)` | `vault_service.get_vault_summary` (new service method wrapping `crud.vault.get_vault_with_room_and_dweller_count`) |
| `list_dwellers(vault_id, status?)` | `dweller_service.list_dwellers` (new service method wrapping the existing dweller CRUD queries) |
| `assign_dweller_to_room(dweller_id, room_id)` | `dweller_service.assign_to_room` |
| `start_training(dweller_id, stat, hours)` | `training_service.start_training` |
| `send_to_wasteland(dweller_id, hours, stimpaks, radaways)` | `exploration_service` |
| `recall_from_wasteland(exploration_id)` | `exploration_service` |
| `build_room(vault_id, room_type, floor, position)` | `room_service.build_room` |
| `pause_game(vault_id)` / `resume_game(vault_id)` | `game_loop_service` |

### Resources (read-only)

Every resource is authorized against the authenticated user before content is returned:

| Resource | Content | Authorization |
|---|---|---|
| `vault://{vault_id}/state` | Caps, power/food/water (+max), happiness, population | Resolve vault and check ownership via `get_user_vault_or_403`; reject access to other users' vaults |
| `dweller://{dweller_id}/bio` | Dweller full info + SPECIAL + status | Resolve the dweller, then authorize its vault via `get_user_vault_or_403` / `verify_dweller_access` before loading |
| `map://{vault_id}/places` | Wasteland map places | Same vault ownership check as `vault://` |
| `notifications://{user_id}` | Recent unread notifications | `user_id` must match the authenticated user; reject mismatches |

### Prompts

| Prompt | Purpose |
|---|---|
| `overseer_daily_briefing(vault_id)` | Pull vault state and ask the model to prioritize actions |
| `vault_triage(vault_id)` | Identify low-resource / at-risk dwellers and propose fixes |

## 5. What it gives us

- One canonical, self-describing tool surface reused by any MCP client.
- Natural-language vault management without frontend changes.
- AI-assisted ops during development (diagnostics, game-loop debugging).
- A foundation if the in-game agent ever needs to expose the same tools externally.

## 6. Risks / guardrails

- **Cost & abuse:** gate action tools behind quota + rate limiting; treat MCP calls like AI usage.
- **Auth:** never expose tools without the existing user/vault ownership checks.
- **Consistency:** tools must go through services so events (notifications, happiness, game loop)
  fire exactly as they do for REST calls.
- **Retry safety (idempotency):** every state-changing tool (`build_room`, `start_training`,
  `send_dweller`, …) accepts an idempotency key scoped to the authenticated user, vault, tool, and
  arguments. The service layer deduplicates atomically (unique constraint on the key hash) and
  returns the previously committed result for repeated keys, including concurrent retries — a
  client retry can never double-apply an action. If durable deduplication storage is required
  (beyond a per-process cache), a small `mcp_idempotency_keys` table is needed — see the migration
  note in §8.
- **Scope creep:** start read-only + a few safe actions; expand only when proven useful.

## 7. Recommended rollout

1. **P0 — Read-only resources** (`vault://`, `dweller://`, `notifications://`) behind JWT.
2. **P1 — Safe action tools** (`assign_dweller_to_room`, `start_training`, `pause_game`,
   `resume_game`) — all through services + quota.
3. **P2 — Curated prompts** (`overseer_daily_briefing`) and exploration/room-building tools.
4. **P3 — Evaluate** usage; only then consider a standalone bridge or wider exposure.

## 8. Dependencies

- Backend: `mcp` (FastMCP) package — add to `backend/pyproject.toml` via `uv add mcp`.
- No frontend changes required.
- **No DB migrations for the P0 read-only phase** (no new tables).
- **Migration note (idempotency):** when state-changing tools ship with durable deduplication
  (see §6), add an `mcp_idempotency_keys` table via Alembic — columns for the key hash (unique),
  user id, vault id, tool name, request hash, and the committed result payload.
