# Multiplayer Backlog — Features & Ideas to Verify

> **Purpose:** a menu to review **before** any design is chosen or code is written. This is an
> inventory with effort/risk/reuse notes and explicit questions to settle — not a plan. Nothing here
> is committed to.

Effort: **S** ≈ days, **M** ≈ a focused slice, **L** ≈ a system with its own migration/balance pass.

## Baseline — what already exists (corrected)

| Capability | Where | Reality check |
|---|---|---|
| Anonymous cross-vault market | `services/trading_post_service.py` | Soft-deleted dwellers, caps only, lists *other* vaults' listings |
| Local duel (dweller vs dweller) | `services/combat/arena_service.py` | Experimental, room-based, one vault |
| Shared world **geography** | `models/world_location.py` | `WorldLocation` is a global registry with stable, name-derived coords. **Discovery and visibility stay vault-specific** (`VaultLocationState`) — everyone draws the same map, but each vault knows only its own fog. |
| Realtime transport | `services/websocket_manager.py` (Redis pub/sub) vs `services/stream_manager.py` (SSE) | **WebSockets are multi-instance capable.** SSE is **in-memory per process** (`_queue_maxsize = 256`), **drops events when a queue fills**, and has **no implemented replay**. |
| Notifications + surfacing | `notification_service`, toast/modal stack | Progression red line enforced in `GAME_MECHANICS.md` |
| Game event bus | `core/event_bus.py` | `GameEvent` + async handlers |
| Feature flags | `game_config.FeatureConfig` → `/system/features` | Ship dark pattern |
| Rate limiting | `middleware/security.py` | Global per-IP |
| Message model | `models/chat_message.py` | Has `from_user_id`/`to_user_id`, **but `vault_id` is a required FK** |
| Player discovery | `api/v1/endpoints/user.py` | `GET /user/{id}` exists; `GET /users/` is **`CurrentSuperuser`-only**. There is no public listing today — a discovery policy is needed, not a fix. |

## Corrections applied from review

- **No public user enumeration.** The earlier privacy concern was wrong: listing is superuser-gated.
  The real open question is *how players find each other* for any directed feature.
- **Realtime is not uniformly multi-instance.** Only WebSockets are Redis-backed. SSE drops and does
  not replay — no "live community progress" may assume SSE is reliable.
- **The message model does not settle DM ownership.** `vault_id` is required, so *account-owned* vs
  *vault-owned* conversations is a decision, not a detail.
- **The faction flag is not guild reuse.** It gates dweller faction bonuses; player organizations need
  their own rules and data.

## A. Foundations

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| A1 | **Connection / friend primitive** | Mutual invite → accept → revoke | discovery policy; notifications | M | consent/privacy |
| A2 | **Public profile / identity** | Display name + block (minimal) | visibility scope | S | privacy |
| A3 | **Mailbox / offline messages** | *Deferred.* Persist messages/offers in their own domains and let notifications point at them; add an inbox model only when **claiming or expiry** needs one | — | — | spam |
| A4 | **Moderation & reporting** | Report + block on the first UGC surface | rate limiting | M | **none exists today** |
| A5 | **Anti-abuse** | *Per-feature guarantees, not a framework.* For each transfer feature define: atomic transfer, duplicate-request handling (idempotency), settlement history | DomainError, transactions | per feature | duping/scams |

## B. Social

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| B1 | **User-to-user DM** | Send + list a thread; **recipient acceptance (message request) and blocking included in the slice** | A1 (connection) or a discovery policy; ownership decision | M | moderation, privacy |
| B2 | **Global channel** | *Not small.* Needs fan-out + moderation + history | A4 | M | moderation (estimate revised up) |
| B3 | **Vault visiting** | **Strictly read-only** view of a connection's vault; no interactions in v1 | A1 | M | griefing, privacy |
| B4 | **Guilds / factions-as-orgs** | — | org model, roles, A4; **not** the faction flag | L | big surface |
| B5 | **Dweller pen-pals** | — | dweller agents, LLM budget | M | cost, lore |

## C. Economy / trade (evolve the trading post)

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| C1a | **Market filters** | Category/rarity filters on the existing market | trading post | S | — |
| C1b | **Buy orders** | *Separate from filters.* Reservations, cancellation, settlement | C1a; A5 guarantees | M | settlement |
| C2 | **Directed barter** | Offer/accept one bundle between connections | A1; **transfer-survival decision** (below); escrow | M | duping |
| C3 | **Trade routes / caravans** | — | C2; `WorldLocation` settlements; scheduler | M–L | balance, griefing |
| C4 | **Auctions** | *Estimate revised up:* timers, sniping rules, settlement | C1b, A5 | L | sniping |
| C5 | **Gifting** | *Estimate revised up:* limits + audit trail to resist alt-farming | A1, A5 | M | alt-farming |
| C6 | **Contracts / commissions** | — | trading post | M | — |
| C7 | **Contested nodes** | — | shared map, PvP balance | L | PvP balance |

**Dweller-transfer decision (blocker for C2/C3).** The existing market **resets stats and clears
relationships** (recycling path). For *player barter* that likely conflicts with expectations — the
dweller you receive should be the one that was offered. Decide explicitly **what survives transfer**
(level, XP, relationships, equipment, name, bio), and treat a faithful transfer as a **new path**, not
the recycling path.

## D. Map / world

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| D1 | **Map sharing** | Allies see the discovered locations you expose | connection; visibility toggle | S–M | privacy |
| D2 | **Discovery race** | First-to-discover ledger | world registry | M | — |
| D3 | **Shared expeditions** | — | exploration sync | L | sync |
| D4 | **World bosses** | — | global HP + contribution | L | balance |

## E. Async PvP

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| E1a | **Snapshot challenges** | Challenge a *connection's* champion; no queue, no ladder | A1 | S | whale brackets |
| E1b | **Matchmaking / ladders / seasons** | *Separate from E1a and later.* Needs population | E1a, G2 | M–L | population |
| E2 | **Vault raid** | *Estimate revised up.* Attack a layout snapshot; defense log | E1a, **consent + protection** | L | griefing |
| E3 | **Bounty / revenge** | — | E2 | M | harassment |
| E4 | **Raid shields / protection** | **Must ship *with* raids, not after.** Consent + protection are part of E2 | — | M | — |

## F. Cooperative (non-adversarial)

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| F1 | **Weather events** | One global condition modifying spawn weights | global condition + `get_spawn_weights` hook | S–M | balance |
| F2 | **HOMM-style weeks** | Timed global modifier, one kind | same hooks | S–M | balance |
| F3 | **Server co-op goal** | **One objective**, visible community progress, personal contribution, **one reward claim per participant** | global event entity + periodic actor; progress read endpoint; one contribution hook | M | catch-up |
| F4 | **Community milestones** | Server-wide threshold | counters, notifications | S | — |

## G. Meta / seasonal

| # | Feature | Smallest playable version | Prerequisites | Effort | Risk |
|---|---|---|---|---|---|
| G1 | **Leaderboards** | Read-only ranking by category | queries | S | thin population |
| G2 | **Seasons / ladder** | — | G1 | M | population |
| G3 | **Seasonal rewards / cosmetics** | — | **a cosmetic surface that does not exist yet** | M | — |
| G4 | **Cross-vault achievements** | — | progression | S | — |

## Verify-first — settle before choosing

**Product / population**

1. **Population.** Enough players for leaderboards/matchmaking? A small server makes global goals (F)
   far safer than PvP (E) or thin markets.
2. **Does a user own multiple vaults?** `User.vaults` is one-to-many — this decides whether
   conversations and trades belong to **accounts or vaults** (also the `ChatMessage.vault_id` question).
3. **Consent model.** Opt-in visibility everywhere; no vault contents exposed without it.
4. **Retention goal.** Async loops for return visits, or session play? It decides the whole shape.

**Privacy / safety**

5. **Player discovery policy.** Listing is superuser-only today — how do players *find* each other for
   DMs, barter, visiting? Decide before any directed feature.
6. **Moderation does not exist.** Any UGC (chat, shared profiles, visiting) needs report/block.
7. **World registry leak.** `WorldLocation` has `kind=VAULT` rows with `vault_number`; confirm what a
   viewer can infer about another vault's *location* (geography is shared; visibility is not).

**Technical**

8. **Anti-cheat.** PvP must run on server-side **snapshots** (simulation is already server-authoritative).
9. **SSE is unreliable for live community state.** In-memory, drops, no replay — F3's progress should be
   a **DB-backed read** (polled, or via the Redis-backed WS path), not SSE fan-out. Spike before F3.
10. **Enum/migration cost.** Every new notification type is a hand-written PG enum migration + snapshot.
11. **LLM cost.** B5 (pen-pals) costs tokens per interaction.
12. **Cosmetic surface.** G3 has nowhere to hang a badge yet.

## What to choose first

**Gameplay-first: F3 — one small server co-op goal.**
One objective, community progress visible, individual contributions, one claim per participant. Defer
contribution rankings and seasons. It creates interaction without simultaneous play or a large
population, and it is the cheapest way to learn whether players *enjoy interacting at all*.

**Conversation-first: A1 + minimal A2 + B1** — connections, a minimal identity (display name + block),
and DMs, **with blocking and recipient acceptance included in that slice**.

**Not yet:** weather and themed weeks are useful additions but do **not** establish whether players
enjoy interacting; raids, bounties, guilds and contested nodes come later, and **raids must ship
consent + protection at the same time**.

Build foundations (A1, A5-style guarantees) only as the chosen slices require them — not upfront.
