# Multiplayer Backlog — Features & Ideas to Verify

> **Purpose:** a menu to review **before** any design is chosen or code is written. This is an
> inventory with effort/risk/reuse notes and explicit questions to settle — not a plan. Nothing here
> is committed to.

Effort: **S** ≈ days, **M** ≈ a focused slice, **L** ≈ a system with its own migration/balance pass.

## Baseline — what already exists (do not rebuild)

| Capability | Where | Notes |
|---|---|---|
| Anonymous cross-vault market | `services/trading_post_service.py` | Soft-deleted dwellers, caps only, lists *other* vaults' listings |
| Local duel (dweller vs dweller) | `services/combat/arena_service.py` | Experimental, room-based, one vault |
| Shared world registry | `models/world_location.py` (`WorldLocation` global; `VaultLocationState` per vault) | Stable, name-derived coords; same map for every viewer |
| Realtime transport | `services/websocket_manager.py` (Redis pub/sub) + `services/stream_manager.py` (SSE) | Multi-instance capable |
| Notifications + surfacing | `notification_service`, toast/modal stack | Progression red line enforced in `GAME_MECHANICS.md` |
| Game event bus | `core/event_bus.py` | `GameEvent` + async handlers |
| Feature flags | `game_config.FeatureConfig` → `/system/features` | Ship dark pattern |
| Rate limiting | `middleware/security.py` | Global per-IP |
| Message model | `models/chat_message.py` | **Already has `from_user_id`/`to_user_id`** (only dweller path wired) |

## A. Foundations (needed by many features)

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| A1 | **Connection / friend primitive** | Mutual invite→accept link between two users | user lookup, notifications | `Connection` model + invite/accept/revoke | M | consent/privacy |
| A2 | **Public profile / identity** | Opt-in display name, vault banner, stats card | profile endpoints | visibility scope | S | privacy |
| A3 | **Mailbox / offline messages** | Async inbox for gifts, offers, notices | notifications | inbox model | S | spam |
| A4 | **Moderation & reporting** | Report/block/rate-limit UGC (chat, bios) | rate limiting | report model, review flow | M | **none exists today** |
| A5 | **Anti-abuse kit** | Escrow, idempotent settlement, audit log, per-user caps | DomainError, transactions | audit table | M | duping/scams |

## B. Social

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| B1 | **User-to-user DM** | Direct messages by open lookup | `ChatMessage` (user fields), WS manager | endpoints + service + UI | S | moderation, privacy |
| B2 | **Global channel** | One community chat room | WS/SSE | channel + fan-out + moderation | S | moderation |
| B3 | **Vault visiting** | Visit a connected user's vault (read-only + a few interactions) | room grid, dwellers | visit scope, permissions | M | griefing, privacy |
| B4 | **Guilds / factions-as-orgs** | Shared org, goals, chat, roster | faction flag (off) | org model + roles | L | big surface |
| B5 | **Dweller pen-pals** | AI dwellers correspond across vaults | dweller agents, LLM | cross-vault messaging, token cost | M | cost, lore |

## C. Economy / trade (evolve the trading post)

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| C1 | **Market upgrade** | Categories/filters, buy orders on the existing market | trading post | query shapes | S | — |
| C2 | **Directed barter** | Offer/accept bundles (dweller/items/caps) between connections | trade value math, recycling | offer model + escrow | M | duping |
| C3 | **Trade routes / caravans** | Persistent link → timed deliveries; interceptable | `WorldLocation` settlements, periodic actor | route model + scheduler | M–L | balance, griefing |
| C4 | **Auctions** | Timed bidding | market, scheduler | bid model | M | sniping |
| C5 | **Gifting** | Send items/caps to a connection | item transfer | — | S | alt-farming |
| C6 | **Contracts / commissions** | Post and fulfil orders for caps | trading post | contract model | M | — |
| C7 | **Contested nodes** | Shared map nodes players fight over | `WorldLocation` | contention windows | L | PvP balance |

## D. Map / world

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| D1 | **Map sharing** | Allies see the subset of your discovered locations you expose | shared `WorldLocation` + `VaultLocationState` | per-connection visibility toggle | S–M | privacy |
| D2 | **Discovery race** | First-to-discover a place is recorded | world registry | discovery ledger | M | — |
| D3 | **Shared expeditions** | Co-op journey with another vault | exploration system | session model | L | sync |
| D4 | **World bosses** | A map-level threat multiple vaults damage | incident kernel | global HP + contribution | L | balance |

## E. Async PvP (no both-online)

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| E1 | **Arena PvP** | Your champion vs another's snapshot | arena experiment, combat kernel | snapshot + queue + ladder | S–M | whale brackets |
| E2 | **Vault raid** | Attack a layout snapshot; dwellers defend | incident kernel | snapshot + defense log | M | griefing |
| E3 | **Bounty / revenge** | Post or claim a bounty on a raider | PvP systems | bounty model | M | harassment |
| E4 | **Raid shields / defense history** | Opt-out windows + logs | — | shield windows | S | — |

## F. Cooperative (non-adversarial)

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| F1 | **Weather events** | Radstorm, raider activity modify incident conditions | `get_spawn_weights`/`get_difficulty_range` hooks | global condition + modifiers | S–M | balance |
| F2 | **HOMM-style weeks** | Timed global modifier (e.g. "week of the deathclaw") | same hooks | condition rotation | S–M | balance |
| F3 | **Server co-op goal** | Migration: everyone contributes to one goal | event_bus, notifications, SSE | global event + participation | M | catch-up |
| F4 | **Community milestones** | Server-wide thresholds | counters, notifications | — | S | — |

## G. Meta / seasonal

| # | Feature | What | Reuses | New | Effort | Risk |
|---|---|---|---|---|---|---|
| G1 | **Leaderboards** | Rank by category (power, incidents, exploration) | queries | leaderboard views | S | small population |
| G2 | **Seasons / ranked ladder** | Reset windows + placement | leaderboards | season model | M | population |
| G3 | **Seasonal rewards / cosmetics** | Badges, banners | reward service | cosmetic surface (**does not exist yet**) | M | — |
| G4 | **Cross-vault achievements** | Social achievements | progression | — | S | — |

## Verify-first — settle these before choosing anything

**Product / population**

1. **Server population.** Is there a player base large enough for leaderboards, matchmaking, or auctions? A small server makes **async global goals (F)** far safer than **PvP (E)** or markets with thin liquidity.
2. **Can a user own multiple vaults?** `User.vaults` is one-to-many. Does "other users" mean *other accounts* or *other vaults*? This changes every addressing/consent model.
3. **Consent model.** Opt-in visibility is assumed everywhere; confirm that no vault's contents are ever exposed without it.
4. **Retention goal.** Is multiplayer meant to drive return visits (async loops) or session play (live)? It decides the whole shape.

**Privacy / safety (blockers, not nice-to-haves)**

5. **`GET /user/` lists all users.** Open-lookup DMs on top of an enumerable user list is a privacy and harassment surface — decide the enumeration policy before B1.
6. **Moderation does not exist.** Any UGC (chat, shared profiles) needs report/block at minimum; is there an appetite to build A4?
7. **Does the shared world registry leak vault locations?** `WorldLocation` has `kind=VAULT` rows with `vault_number`; confirm what a viewer can infer about another user's vault from the map.

**Technical spikes**

8. **Anti-cheat / trust.** All simulation is server-authoritative already — confirm PvP can rely on *snapshots* rather than live client state (it can, and should).
9. **Notification / SSE fan-out.** A server-wide broadcast to every vault is untested at scale; spike it before F3.
10. **Enum/migration cost.** Every new notification type is a hand-written PG enum migration + snapshot update. Budget it per feature.
11. **LLM cost.** B5 (pen-pals) and AI-mediated social features cost tokens per interaction — is that acceptable?
12. **Cosmetic surface.** G3 has nowhere to hang a badge yet; confirm the reward shape before promising seasonal rewards.

## Suggested first candidates (only after the above)

- **Lowest risk / highest signal:** F1 weather conditions (reuses spawn hooks, no social surface) or G1 leaderboards (read-only).
- **Highest multiplayer *feeling* per unit infra:** E1 async arena PvP — but only if population (verify #1) supports it.
- **The keystone that unlocks the most:** **A1 connections** — barter, routes, map sharing, and contacts-gated chat all depend on it.
