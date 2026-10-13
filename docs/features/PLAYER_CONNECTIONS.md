# Player Connections & Chat — Smallest Playable Slice (A1 + A2 + B1)

> Status: **plan + as-built notes.** First multiplayer slice chosen from `MULTIPLAYER_BACKLOG.md`.
> Feature-flagged `player_connections`, **enabled by default** (backend PR #967 still ships it off;
> the test branch #973 flips it on). This is the smallest version that is actually playable and safe —
> not the full social system.

## As built (2026-10-13)

Shipped on `feat/player-connections` (backend, #967) and the UI on `feat/messages-ui` (#969); combined
for testing on `feat/messages-full` (#973). Beyond the plan below, the implementation added:

- **Pair serialization** — every pair-mutating operation takes a transaction-scoped advisory lock on
  the sorted user pair (`db_locks.advisory_xact_lock`), so concurrent invite/accept/send/block cannot
  race the unique constraints; races that slip through are caught (`IntegrityError` → re-fetch).
- **Bounded conversation listing** — a DB-side aggregation (≤50 conversations) instead of loading the
  user's whole history; thread reads mark **only the returned page** read.
- **Shared send limit** — a Redis fixed-window counter with an in-process fallback.
- **Reciprocal blocking** is one row and idempotent in either direction.

**Live delivery is polling, not push.** There is **no personal WebSocket endpoint** in the backend
(the only WS route is dweller chat), so `ConnectionManager.send_personal_message` reaches no client;
the UI polls the open thread (~5s). A real push channel (a personal WS endpoint, or routing DM events
through the existing SSE stream) is a backend follow-up. See "Delivery" below.


## Goal

Let two players find each other, connect, and talk — with consent and blocking from day one, and
**no** dependency on population size, realtime liveness, or device notifications.

Scope of this slice: **A1** connections, **A2** minimal identity (public handle + block), **B1** direct
messages including **recipient acceptance** and **blocking**.

Explicitly **not** in this slice: groups, global channel, attachments, read receipts, typing
indicators, vault visiting, trade/barter, notifications bells, moderation review UI.

## Decisions taken (from the backlog review)

| Decision | Choice | Why |
|---|---|---|
| **Discovery** | Invite by **exact `username`** | `User.username` is unique + indexed (`models/user.py:16`); no listing, so no enumeration surface. `GET /users/` stays superuser-only. |
| **Ownership** | Conversations are **account-owned**, not vault-owned | `ChatMessage.vault_id` is a required FK and dweller-chat carries LLM/audio fields — overloading it would blur semantics and force a nullable migration anyway. |
| **Message model** | **New `DirectMessage` table** | Clean account↔account domain, no `vault_id`, no LLM columns. Dweller chat is untouched. |
| **Consent** | First message to a non-connection is a **message request** | Matches B1's review requirement ("recipient acceptance … included in that slice"). |
| **Delivery** | Persist; the UI **polls** the open thread (~5s) | There is **no personal WebSocket endpoint** (the only WS route is dweller chat), so `send_personal_message` reaches no client. SSE is in-memory, drops on a full queue, and has no replay (`stream_manager.py`). Live push (a personal WS endpoint or SSE routing) is a follow-up. |
| **Notifications** | **No bell**; a UI badge/count only | DMs are not progression events (the red line in `GAME_MECHANICS.md` is progression-only). |
| **Identity store** | Reuse `UserProfile` (`bio`, `avatar_url`, `preferences` JSONB) | A visibility toggle lives in `preferences` — no migration for identity. |

## Entities

- **`Connection`** — `requester_id`, `addressee_id`, `status` (`PENDING` / `ACCEPTED`), `created_at`,
  `responded_at`. Unique constraint on the unordered pair `(min(user_a), max(user_b))`.
- **`UserBlock`** — `blocker_id`, `blocked_id`, `created_at`. Unique on the ordered pair. Blocks
  invites and messages **both directions**.
- **`DirectMessage`** — `sender_user_id`, `recipient_user_id`, `body` (≤ 2000), `created_at`,
  `read_at`, `is_request` (true while the recipient has not accepted). No `vault_id`.
- **Flag** — `FeatureConfig.player_connections` (default `False`), exposed via `/system/features`.

`ConnectionStatus` is a `StrEnum`; per repo convention it is declared in `app/core/enums.py` with a
hand-written PG enum migration and a `PG_ENUM_LABELS_SNAPSHOT` update in the same commit.

## Lifecycle

1. **Invite**: `POST /connections` by `username` → `PENDING` (idempotent; re-invite to an existing
   pending row is a no-op, not a duplicate).
2. **Accept / decline / revoke**: `POST /connections/{id}/accept`, `.../decline`, `DELETE /connections/{id}`.
   Accept is idempotent.
3. **DM to a connection**: stored; the client picks it up on the next poll (no live push yet).
4. **DM to a non-connection**: stored with `is_request=true`; the recipient sees it in the request
   folder of their conversations list. Accepting promotes the sender to a connection; declining or
   blocking discards it. **One open request per sender/recipient pair** until answered.
5. **Block**: `POST /blocks/{user_id}` prevents future invites and messages both ways and makes any
   existing thread read-only. Unblock restores the ability to invite (not the connection).

## API (thin endpoints, service-owned logic)

| Method | Path | Purpose |
|---|---|---|
| POST | `/connections` | Invite by `username` |
| POST | `/connections/{id}/accept` · `/decline` | Respond |
| DELETE | `/connections/{id}` | Revoke / unfriend |
| GET | `/connections` | Accepted + pending (as requester and addressee) |
| POST | `/blocks/{user_id}` · DELETE | Block / unblock |
| GET | `/blocks` | Blocker's list |
| POST | `/messages/{user_id}` | Send a message or request |
| GET | `/messages/{user_id}` | Thread with one user (paginated) |
| GET | `/messages` | Conversation list w/ last message + unread + request flag |

Service: `player_connection_service.py` and `direct_message_service.py` (both end `_service.py`);
queries live in `crud/`; routers only parse → call → let `DomainError` map to HTTP. Each service raises
`FeatureDisabledException` when the flag is off, and validates the username/pair rules.

## Anti-abuse (per-feature guarantees, not a framework)

- **Rate limit** sends per user (reuse the middleware's spirit; add a per-user cap in the service).
- **Body** ≤ 2000 chars, non-empty after strip (Pydantic).
- **One open request** per non-connection pair; **blocking** is immediate and bilateral.
- **Idempotency**: accept/decline/block are safe to retry; a duplicate send is not silently dropped but
  is bounded by the rate limit.
- **Report** is a minimal record (`POST /reports` writing a row for later review) — included only if
  cheap; the admin review UI is out of scope.

## Smallest playable slice — build order

| Step | Deliverable | Status |
|---|---|---|
| 1 | `Connection` + block + A2 identity (handle, visibility toggle in `preferences`) | **done** (#967) |
| 2 | `DirectMessage` + requests + blocking enforcement (delivery: client polling; see note above) | **done** (#967) |
| 3 | A frontend connections/DM surface | **built, being rethought** (#969, draft) |

Foundations are built **only as these steps require them** — no general framework ahead of the first
feature.

## Tests & validation

- Failing-test-first for: flag-off → 422; invite/accept/revoke; block blocks both directions; request
  gating (second message becomes a request only after acceptance); thread isolation between accounts;
  self-invite/self-message rejected.
- Architecture guards: new services are `*_service.py`; no raw `select()` in services; baselines
  unchanged.
- Full backend suite green; ruff + format + `ty` on touched files.

## Open questions (small, decide during build)

1. **Handle stability** — is `username` changeable, and does changing it break pending invites?
2. **Requests folder** — accept/decline per request, or an "accept all from this sender" shortcut?
3. **Report** — include the minimal report endpoint in this slice, or defer to the first UGC surface?
4. **Read receipts** — `read_at` is stored; do we expose it in v1 or keep it internal?
