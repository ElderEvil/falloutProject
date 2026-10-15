# Game Mechanics - Agent Rules

Game-domain invariants for the Fallout Shelter simulation. These constrain *what the game must do*,
unlike `AGENTS.md`, which constrains *how code must be structured*. Follow both.

## Progression visibility (red line)

Every player-facing progression event — level-up, loot, training completion, quest/objective completion —
must surface via modal/pop-up or toast **in addition to** the notification bell entry, never
notification-only. A new progression flow without visible surfacing is incomplete; keep existing surfacing
intact when touching these flows.

## Objectives: guidance, earned progress and explicit claims

- Objective progress advances automatically from game events; **rewards do not**. Reaching the target creates
  a ready-to-claim outcome. `is_completed` means the reward was claimed, including historical automatically paid
  rows; `progress >= total` with `is_completed == false` means earned and unclaimed. Never repay historical rows.
- Owners claim through `POST /objectives/{vault_id}/{objective_id}/claim`. Claims require an assigned, earned
  objective and serialize reward settlement with the completion flag; incomplete, foreign and repeat claims fail.
  The administrative `/complete` operation stays separate from ordinary player claims.
- The authored `starter` category is the ordered **vault guide**, including post-Office chapters. The lowest
  unclaimed sequence is current and advances only after a claim. The guide is visible across vault screens;
  everyday objectives become visible alongside it after the Office chapter.
- Already-achieved state (rooms, staffing, population, levels, completed training and quests) may satisfy the
  current guided milestone. Derive this on reads without writing; validate again during the claim. Event counters
  such as resource earnings and scrapping keep their recorded progress. Later steps cannot be claimed early.
- Earned daily/weekly rewards survive reset until claimed; resets may replace unfinished objectives and remove
  already-claimed links. Objective rewards never count toward another resource-collection objective.
- Ready rewards keep their routine bell/toast event; successful claims show a modal or toast. Notification opt-outs
  affect notification delivery, not reward settlement or the player-opened guide.

## Notification preferences

Players may explicitly opt out of routine notification categories. The preference is persisted at
`UserProfile.preferences.notifications` as `{"version": 1, "disabled_categories": [...]}` and is enforced
server-side before persistence or real-time delivery. An opt-out intentionally overrides the progression
visibility rule for that routine category: no bell entry, toast/modal, or SSE payload is created for future
events. Historical notifications and game/reward settlement are unchanged.

Deaths, injuries, critical resource/power alerts, exit requests, combat events, achievements, map failures,
and hazard-team confirmations are always enabled. Every `NotificationType` must be deliberately mapped in
`app.core.notification_preferences`; unknown future types default to enabled.

## Exit requests (Someone Wants Out)

A dweller in despair eventually asks to leave. The rules are deliberately slow and costly so the decision
is real, not a rerollable button:

- **Grace period** — a dweller must stay at or below `EXIT_DESPAIR_HAPPINESS` (15) for
  `EXIT_DESPAIR_GRACE_HOURS` (6) before they will ask. `dweller.despair_since` records the first tick of
  despair and is cleared on recovery, so a transient dip never raises a request.
- **One ask per day** — the vault raises at most `EXIT_MAX_EXIT_REQUESTS_PER_DAY` (1) per rolling 24h
  (`vault.last_exit_request_at`), and never while a request is pending. The chat-driven ask
  (`request_exit`) enforces the same cap, so it cannot slip a second ask in. **Answering** a request
  (grant or refuse) restarts the same window, so a dweller still in despair cannot re-ask immediately.
- **Refusal is final for that ask and costs the vault** — refusing answers the request
  (`exit_requested_at` cleared) and takes `EXIT_VAULT_REFUSAL_HAPPINESS_PENALTY` (10) from every living
  dweller (the refused dweller included). It must never leave the request standing, or the action becomes
  repeatable for free.
- **Granting** stays one-way: permanent death by `EXILE` — the entry point for the wasteland-pool idea in
  issue #831.

The UI states the cost before the click (modal copy + button label) and surfaces the outcome as a toast;
the ask keeps its always-on bell notification.

## Arena morale (The Crowd Goes Wild)

Finishing any arena match (duel, brawl, or hunt) lifts the whole vault: every living dweller — fighters
included, on top of their existing ±10 participant swing — gains `COMBAT_ARENA_MORALE_BONUS` (1), clamped to
the 10..100 dweller contract. A per-vault rolling window (`vault.arena_morale_awarded_at`,
`COMBAT_ARENA_MORALE_COOLDOWN_SECONDS` (3600)) keeps multiple arenas from stacking the bonus: the arena that
finishes first sets the window and later completions inside it grant nothing (the participant swing still
applies). The grant serializes on a vault-scoped advisory lock, lands in the match's own transaction, and
surfaces as an always-on `arena_morale_boost` bell entry plus toast — the arena's first progression surface.

Assigning dwellers to the arena or selecting fighters for a new match preserves their current health and
radiation. Match resets preserve injuries; healing uses the existing medical and recovery
systems. Catalog opponents and training bots still reset to full match HP.

## Race and faction switches

Race mechanics are **on** (`FEATURE_RACE_MECHANICS`) and faction mechanics are **off**
(`FEATURE_FACTION_MECHANICS`) until the world is deep enough for factions to mean something. Race stays on and
evolves gradually.

"Off" means faction is unavailable, not hidden from the data model: stored factions are preserved untouched, so
flipping the switch back on restores them. While it is off the roster filter rejects `faction` with 422,
`identity-options` returns no factions (races still offered), and `GET /system/features` tells clients the state
so nothing rejected is ever offered. Non-human radiation immunity survives both switches. Ghouls,
super mutants and synths cannot accumulate radiation or use RadAway; all races can use Stimpaks
(including Gen 1/2 synths until a repair system exists).

**Do not gate faction on the shared identity schema.** `DwellerVisualAttributes` validates curated
`DwellerTemplate` seeds, AI generation and partial updates, which legitimately carry a faction; a schema-level
gate rejects system content and breaks vault initiation, boosted seeding and rewards. Rejection belongs on the
user-edit path.

## AI prompt registry

AI instructions are append-only registry entries. Never edit `Prompt` rows directly:
create and activate a replacement with `uv run fo-cli version-prompt <name> --template-file <path>`.
The command retires the active row, clears the process cache, and rejects format placeholders.

## Background task session compatibility

Dramatiq game-tick actors create raw SQLAlchemy `AsyncSession` instances via
`sqlalchemy.ext.asyncio.async_sessionmaker`. These sessions do not provide
SQLModel's `.exec()` method. CRUD/services used by `game_tick`,
`process_vault_tick`, or other `task_session()` actors must `await
session.execute(...)` (never `.exec()`) unless the session factory explicitly
sets `class_=sqlmodel.ext.asyncio.session.AsyncSession`, and pick the result
accessor by statement shape: `.all()` for multi-column queries,
`scalar_one_or_none()` for aggregates, `.scalars()` only for single-column
entity results. Any session-factory or CRUD refactor in this path requires a
regression test using the raw SQLAlchemy session type.

## Radiation sources and outfit resistance

Radiation is either **ingested** or **external**, and outfits only resist the external kind.

- **Ingested** — irradiated water drunk while the vault has no water. It bypasses outfit
  resistance (`apply_radiation_gain(..., resisted_by_outfit=False)`): a hazmat suit or power
armor does not help, because the radiation enters through drinking. Non-humans stay immune and
RadAway is the only cure for humans.
- **External** — radscorpion incidents and wasteland danger events. Outfit resistance applies
  (see `OUTFIT_RADIATION_RESIST_BY_TYPE` / `OUTFIT_RADIATION_RESIST_BY_NAME` in
  `services/radiation_service.py`): hazmat suits block it fully, power armor blocks most.

Drought radiation accrues at 1% of max health per tick after `dehydration_grace_ticks` of zero
water, counting only the ticks past the grace boundary. Radiation saturates at the dweller's own
`max_health` — never a flat cap — so the health ceiling bottoms out at 1 HP and radiation alone
never kills. Recovery is the one-shot **Treat Irradiated Dwellers** action: RadAway first (raises
the ceiling), then a Stimpack heals into it. Wasteland auto-use mirrors that order: RadAway fires
first once radiation has cut the ceiling by 25% of max health, then a Stimpak heals into it (gate:
health below 50% of full max health, so radiation never hides a wound); expedition-site damage is
recorded in the journey log.

## Damage and radiation reductions

Every reduction a dweller applies to incoming damage or radiation is resolved by one pure resolver
(`app/utils/damage_reductions.py`) and applied at one point per effect. The sources per channel:

| Channel | Identity (`identity_modifiers_for`) | Outfit | Team |
|---|---|---|---|
| PHYSICAL | `incident_response_pct` (faction perk) | — | `TEAM_HAZARD_RESIST` when active |
| FIRE | `incident_response_pct` (faction perk) | `outfit_fire_resist` | `TEAM_HAZARD_RESIST` when active |
| RADIATION | `radiation_resist_pct` (+ `radiation_immune` → immune) | `outfit_radiation_resist` (external only) | `TEAM_HAZARD_RESIST` when active |

**Stacking rule:** shares combine multiplicatively as complements — `combined = 1 - product(1 - r)` —
so the result is order-independent, and the amount is truncated exactly once, at the end
(`int(amount * (1 - combined))`). Immunity (Ghoul) short-circuits to zero. This replaces the old
per-source sequential truncation, so small hits can shift by 1 (e.g. 3 damage with 0.15 + 0.20:
`int(int(3*0.85)*0.8) = 1` before, `int(3*0.85*0.8) = 2` now). The team share is owned by
`contamination_team_service` (`TEAM_HAZARD_RESIST`) and passed into the resolver by the service
callers; `app/utils/` never imports `app.services.*`.

Incident types map to channels via `effects_for_incident_type` in `app/models/incident.py`:
FIRE deals fire damage, RADSCORPION_ATTACK deals physical damage and also irradiates, everything
else deals physical damage without radiation.

### Wave 2 resource reserves

Primary production remains 0.0012 per SPECIAL point per output unit per second.
Power draw is 0.40 per weighted room size/tier per minute; food and water draw
are 0.30 per adult in the vault per minute. Dead/deleted dwellers and dwellers
on exploration or quests do not draw vault food/water; children and teens use
the existing 70% youth multiplier.

Catch-up uses steps of at most 60 seconds so restored power enables other
production on the following step. Fractional stock persists on GameState;
capacity and reserve clamps discard unusable excess/debt. After the existing
10-minute activity timeout, net-negative changes stop at 25% capacity, or at
the current amount if already below that floor. This never grants resources.
Active vaults retain full drain; returning resumes it. There is no Survival
mode selector yet. Production and medical storage limits remain in force.

### Wave 2 objective economy

Primary-resource objectives say **Collect** and count gross production, including
output at full storage. Fractional output persists until it produces a whole
objective unit; resource gifts and refunds do not advance these tasks. Medical
objectives count supplies actually retained in storage. Weapon/outfit/junk
objectives accept item events only. **Build** requires a new room, and quest
completion objectives say **Quests** rather than Expeditions. Training to a
stat threshold requires the resulting stat value, not merely a training event.

Non-starter assignment, correct-assignment, training and level-up templates
count distinct dwellers. Previously recorded progress remains intact; identities
are recorded for future events. A refreshed task starts a new counting window.
Templates have stable category-qualified keys, so labels may change without
duplicating templates or colliding with another category. Catalog migrations
preserve objective IDs, custom templates, historical links and ready claims.

Rewards freeze when earned. Pending earned rewards retain their previous payout
after the balance migration, and the UI displays that saved payout. Objective
rewards continue to suppress collection events to avoid reward feedback loops.
Starter grants remain unchanged. The uniform-selection caps-only expectation
for a fully completed batch is now 216.14 daily and 589.62 weekly (previously
1,034.09 and 2,959.62). The achievement caps pool is 43,765 (previously 95,250).
These are catalog expectations, not measured income: item/lunchbox value and
actual completion rates are excluded. Prices are unchanged pending income data.

## Arena training bot partners

Hunt allows one or two dwellers, or one dweller with a training bot. Brawl requires
one lead dweller per side and a second dweller or training bot in each partner slot.
Duel stays dweller-only. Each team has at most two participants; bots never replace
the required lead dweller and do not occupy vault population or room worker slots.

Both sides use the same arena catalog: Training Eyebot 30 power/20 HP, Training
Mr. Handy 20/30, Training Protectron 10/60. These are free arena training partners,
not owned dwellers. Their HP persists across combat ticks and resets on a new match
selection. Destroyed bots stay at 0 HP and deal no damage. Only real dwellers get
the existing participant XP/happiness rewards; bot support adds no reward multiplier.
Existing match-completion morale rules, when enabled, remain vault-scoped.

Arena bots face right beside allied dwellers and mirror left on the enemy side,
including picker previews. Creature artwork retains its native enemy-facing direction.
Incomplete partner edits stay local and disable Start until selection is complete;
polling must not overwrite an open bot selection.
