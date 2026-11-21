# Multiplayer Backlog — decisions and verified baseline

> **Status:** archived inventory. Multiplayer is an explicit later milestone tracked in
> [issue #1057](https://github.com/ElderEvil/falloutProject/issues/1057); this file preserves the verified
> baseline facts and the decisions to settle before choosing a slice. It is not a plan and commits to
> nothing.

## What already exists (corrected)

| Capability | Where | Reality check |
|---|---|---|
| Anonymous cross-vault market | `services/trading_post_service.py` | Soft-deleted dwellers, caps only, lists *other* vaults' listings |
| Local duel (dweller vs dweller) | `services/combat/arena_service.py` | Experimental, room-based, one vault |
| Shared world **geography** | `models/world_location.py` | `WorldLocation` is a global registry with stable, name-derived coords. **Discovery and visibility stay vault-specific** (`VaultLocationState`) — everyone draws the same map, but each vault knows only its own fog. |
| Realtime transport | `core/websocket_manager.py` (Redis pub/sub) vs `core/stream_manager.py` (SSE) | **WebSockets are multi-instance capable.** SSE is **in-memory per process** (`_queue_maxsize = 256`), **drops events when a queue fills**, and has **no implemented replay**. |
| Notifications + surfacing | `notification_service`, toast/modal stack | Progression red line enforced in `GAME_MECHANICS.md` |
| Game event bus | `core/event_bus.py` | `GameEvent` + async handlers |
| Feature flags | `game_config.FeatureConfig` → `/system/features` | Ship dark pattern |
| Rate limiting | `middleware/security.py` | Global per-IP |
| Message model | `models/chat_message.py` | Has `from_user_id`/`to_user_id`, **but `vault_id` is a required FK** |
| Player discovery | `api/v1/endpoints/user.py` | `GET /user/{id}` exists; `GET /users/` is **`CurrentSuperuser`-only**. There is no public listing today — a discovery policy is needed, not a fix. |

## Corrections from review

- **No public user enumeration.** Listing is superuser-gated; the real question is how players find each
  other for any directed feature.
- **Realtime is not uniformly multi-instance.** Only WebSockets are Redis-backed. SSE drops and does not
  replay — no live community progress may assume SSE is reliable.
- **The message model does not settle DM ownership.** `vault_id` is required, so account-owned vs
  vault-owned conversations is a decision, not a detail.
- **The faction flag is not guild reuse.** It gates dweller faction bonuses; player organizations need
  their own rules and data.
- **There is no personal push channel.** The only WebSocket route is dweller chat, so
  `ConnectionManager.send_personal_message` reaches no client; the messages UI polls instead.

## Shipped since this inventory

- **F3 server co-op goal** shipped in #1464: one `ACTIVE` server-wide event, per-vault participation,
  contributions from ordinary play, one-time reward claim. As-built contract:
  `docs/backend/GAME_MECHANICS.md` (World events); original design: `WORLD_EVENTS.md`.
  Reuse this pattern before adding a new multiplayer system.

## Decide before choosing a slice

1. **Population.** Enough players for leaderboards/matchmaking? A small server makes global goals far
   safer than PvP or thin markets.
2. **Account vs vault ownership.** `User.vaults` is one-to-many; this decides whether conversations and
   trades belong to accounts or vaults (also the `ChatMessage.vault_id` question).
3. **Consent model.** Opt-in visibility everywhere; no vault contents exposed without it.
4. **Retention goal.** Async loops for return visits, or session play?
5. **Player discovery policy.** How do players find each other for DMs, barter or visiting?
6. **Moderation does not exist.** Any UGC needs report/block.
7. **World registry leak.** Confirm what a viewer can infer about another vault's location.
8. **Anti-cheat.** PvP must run on server-side snapshots.
9. **SSE is unreliable for live community state.** Use a DB-backed read or the Redis-backed WS path.
10. **Enum/migration cost.** Every new notification type is a hand-written PG enum migration + snapshot.
11. **LLM cost.** Dweller pen-pals cost tokens per interaction.
12. **Cosmetic surface.** Seasonal rewards have nowhere to hang a badge yet.

## Candidate directions (not commitments)

- **Gameplay-first:** the server co-op goal shipped; learn from it before the next cross-vault system.
- **Conversation-first:** connections, a minimal identity (display name + block), and DMs, with blocking
  and recipient acceptance included in that slice.
- **Not yet:** raids, bounties, guilds and contested nodes. Raids must ship consent + protection together.

Build foundations only as the chosen slice requires them — not upfront.
