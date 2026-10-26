# Combat surface matrix: Arena, incidents, wasteland sites

Recorded 2026-10-26 while reviewing PR #1199 (`feat/wasteland-scenes`). Purpose: show which combat
parts the three playable surfaces already share, which are deliberately separate, and where further
reuse is cheap versus where it would fight the domain model.

Legend: **yes** = uses the unit directly · **indirect** = through a shared helper or another
component · **no** = not used · **equivalent** = same behaviour implemented separately

Re-derive the tables with `grep` over `backend/app/services/combat`, `backend/app/services/exploration`,
`backend/app/schemas`, and `frontend/src/modules/{combat,rooms,exploration}`. Prefer symbol names over
line numbers when checking: paths move, function names do not.

## Surfaces

| Surface | Entry point | Owns turns |
| --- | --- | --- |
| Arena | `ArenaService.process_arena_ticks` → `_resolve_round` → `_resolve_attacks` | game tick, alternating teams |
| Incident | `incident_tick.process_vault_incidents` → `incident_round.process_incident` | game tick, both sides each round |
| Wasteland site | `ExpeditionService.resolve_node` → `_resolve_scene_combat_transaction` → `site_combat_service.resolve_turn` | player request (`POST /site/resolve`), alternating teams |

The legacy stat-check room engine (`combat_calculator`, `_fight_enemy`) still runs saved/legacy runs and
random exploration events; it is not part of the single-scene encounter and is excluded below.

## 1. Power and enemy stats

| Unit | Arena | Incident | Wasteland site |
| --- | --- | --- | --- |
| `utils/combat.combat_power` | yes (`arena_participants.participant_from_dweller`) | yes (`incident_round.process_incident`) | yes (via `participant_from_dweller`) |
| `utils/combat.total_combat_power` | no (sums participant power) | yes (`incident_math.dweller_combat_power`) | no |
| `incident_math.raider_power` | indirect (creature power/HP in `list_arena_creatures`) | yes (threat power) | indirect (enemy power/HP in `list_site_enemies`) |
| `catalog_service.list_arena_creatures` | yes | no | indirect (same table, extended) |
| `catalog_service.list_site_enemies` | no | no | yes |
| `utils/damage_reductions` | no | yes | no |
| `hazard_team_service` (`TEAM_*`, participation, outfit equip) | no | yes | no |

## 2. Combat kernel

| Unit | Arena | Incident | Wasteland site |
| --- | --- | --- | --- |
| `attack_service.resolve_attacks` | yes | no | yes |
| `attack_service._apply_damage` (5% max-HP cap, fractional carry) | yes | no | yes |
| "attacker deals power / 5 × seconds" | equivalent (inline in `resolve_attacks`) | yes (`incident_math.damage_to_raiders`) | equivalent (via `resolve_attacks`) |
| "threat deals power / divisor × seconds" | no | yes (`incident_math.damage_to_dwellers`) | no |
| `incident_math.split_damage` / `split_proportional` | no | yes | no |
| Team alternation (`next_attack_team`) | yes | no (both sides act) | yes |
| Time quantum | tick `seconds_passed` | tick `seconds_passed` | fixed `TURN_SECONDS = 2` |

## 3. Skills and participants

| Unit | Arena | Incident | Wasteland site |
| --- | --- | --- | --- |
| `weapon_skill_service.weapon_skill` | yes | no | yes (via `attack_service`) |
| `weapon_skill_service.attack_effect` | yes | yes | yes |
| `weapon_skill_service.combat_body` | yes | yes | yes |
| `MAX_CHARGE` / `arena_participants.charge_per_second` | yes | no | yes |
| `arena_participants.participant_from_dweller` | yes | no | yes |
| `arena_participants.catalog_participants` | yes | no | yes |
| Stable duplicate-enemy numbering | yes (`catalog_participants`) | no individual enemies | yes (`catalog_participants`) |
| `fighter_view` / `participant_out` | yes (`participant_out`) | no | yes (`fighter_view`) |
| `schemas.arena.ArenaFighter` + `ArenaActiveSkill` | yes | no | yes (`SiteCombatView.fighters`) |
| `schemas.combat.CombatAction` / `CombatImpact` | yes | yes | yes |
| `schemas.combat.CombatBody` / `CombatEffect` | yes | yes | yes |

## 4. Persistence, journal, outcomes

| Concern | Arena | Incident | Wasteland site |
| --- | --- | --- | --- |
| Combat state | `ArenaState` row (`queued_skill_ids`, `skill_charge`, `next_attack_team`) | `Incident` row (`combat_progress`, `enemies_defeated`, `damage_dealt`) | `ExpeditionRun.flags["combat"]` (`opponents`, `charge`, `carry`, `events`) |
| Enemy model | individual participants with HP | one aggregate threat scalar | individual participants with HP |
| Journal storage | `ArenaMatchEvent` (`kind`, `actor_id`, `message`, `action` JSON) | `IncidentEvent` (`kind`, `message`, `data` JSON incl. `data.action`) | `flags.combat.events[]` with `action`, capped at 60 |
| Journal writer | `_resolve_attacks` → `ArenaMatchEvent` | `incident_publishing.record_event(s)` | `resolve_turn` builds the event list |
| XP | `_award_combat_xp` | `award_combat_xp` (own) | none |
| Loot / rewards | arena stats and morale | `incident_math.generate_loot` + `reward_service` | `_pay_reward_vault` + `loot_calculator` |
| Delivery | arena result | `incident_publishing.notify_resolution` + `publish_sse` | `notification_service` + deferred delivery |

## 5. Frontend components and composables

| Unit | Arena | Incident | Wasteland site |
| --- | --- | --- | --- |
| `ArenaRing.vue` | yes (via `ArenaPreview`) | no | yes (`SiteCombatScene`) |
| `CombatPet.vue` / `ArenaFighter.pet` | yes (equipped companion appearance) | no | yes (via `fighter_view` and `ArenaRing`) |
| `ArenaPreview.vue` / `ArenaSupportPanel.vue` | yes | no | no |
| `CombatantMeters.vue` | yes (`ArenaRing`, `ArenaPreview`) | no (own HP rows + `Progress`) | yes (via `ArenaRing`) |
| `CombatantMotion.vue` | yes | yes | yes (via `ArenaRing`) |
| `CombatDamageNumbers.vue` | yes | yes | yes (via `ArenaRing`) |
| `CombatEffect.vue` | yes (via motion) | yes (via motion) | yes (via motion) |
| `CombatSkillIcon.vue` | yes (ring, meters, log) | no (no skill data) | yes (ring, log) |
| `useCombatPlayback` | yes (`useArenaRoom`) | yes (`IncidentScene` owns) | yes (`SiteCombatScene` owns) |
| `CombatPlaybackSnapshot` / `PlayingCombatAction` | yes | yes | yes |
| `BattleLog.vue` | yes (`ArenaSupportPanel`) | yes (via `IncidentBattleLog`) | yes (`ExpeditionSiteModal`) |
| `IncidentBattleLog.vue` | no | yes (adapter → `BattleLog`) | no |
| `IncidentScene.vue` | no | yes | no |
| `SiteCombatScene.vue` | no | no | yes |
| `WastelandScene.vue` (artwork frame) | no (ring background) | no (own backdrop) | yes |
| `useFallbackImage` | yes | yes (×2) | yes |
| `DwellerPortrait` | yes | yes | yes |
| `getCreatureImagePath` / `getCreatureModelSizeClass` | yes | yes | yes (via `ArenaRing`) |
| Impact sound policy (`skill ? arenaSkill : incidentHit`) | `useArenaRoom` | `incidentHit` only | `SiteCombatScene` |
| Impact audio bus | `sfx` | `sfx` | `sfx` |

## 6. Reading the matrix

### Already one engine

Arena and wasteland sites share the per-participant kernel end to end: `resolve_attacks`,
`_apply_damage`, `ArenaParticipant` construction, `ArenaFighter` DTO, charge rates/caps, `ArenaRing`,
`useCombatPlayback`, `BattleLog`, and `CombatantMotion`/`CombatDamageNumbers`. Wasteland owns its
state container (`expedition_run.flags`), HTTP trigger, travel pause/resume, encounter outcomes and
rewards. Arena owns its tick lifecycle and match settlement. Charge reset/advancement policies stay
with each surface: Arena resets queued charge and advances surviving dwellers during ongoing fights;
sites reset on skill use and currently advance charge even on terminal turns.

### The outlier is deliberate

Incidents aggregate a threat group into one power scalar and split damage across responders. They cannot
use `resolve_attacks` without inventing per-enemy HP, and `docs/features/WASTELAND_COMBAT_EXPANSION.md`
("Share the smallest useful presentation layer") already records that decision. What incidents do share
is the right layer: the action vocabulary (`CombatAction`/`CombatImpact`), `combat_body`, `attack_effect`,
`combat_power`, `useCombatPlayback`, and `BattleLog`.

### Improvements applied in this PR

1. **Impact audio routing**: Arena and incident impacts now use the site's explicit `sfx` bus so
   the SFX volume setting controls combat impacts across all three surfaces. Keep sound selection at
   the existing impact callbacks; extracting a two-branch ternary adds little value.
2. **Duplicate-enemy numbering**: site numbering now lives in the existing `catalog_participants`
   constructor so Arena also distinguishes identical opponents. Preserve actor IDs and count the
   full roster, including knocked-out enemies, so labels do not change after a knockout.

Equipped pets now travel through the shared `fighter_view` response and render at
their owner's feet in `ArenaRing`. Appearance uses the equipped pet's image URL,
with the existing catalog asset lookup as a fallback. A missing/broken image shows
a paw symbol. Companions share their owner's facing and ground plane; they add no
fighter, HP/charge meters, target, or mechanical attack/damage calculation. Existing pet bonuses
remain with `pet_modifiers_for` and the combat kernel. Incident companion visuals
remain a separate follow-up because incidents use their own scene actor projection.

Pet attacks are presentation only: `CombatantMotion`'s companion mode follows the
owner's prepare/impact playback as a lunge, including when the owner uses a ranged
weapon. It ignores incoming impacts and suppresses weapon effects, damage reactions
and skill flashes. The pet remains outside the action/target/HP roster.

`actor-ground-shadow` provides a soft contact ellipse for fighters and pets in
arena setup, encounter briefings and live combat. It scales inside the actor frame
and stays on the floor while the sprite lunges; it cannot intercept input.

### Further extraction has limited value

- **Base damage**: `incident_math.damage_to_raiders` and `resolve_attacks` share `power / 5 × seconds`,
  but only the attack engine clamps negative elapsed time, scales skills and applies training caps.
  Keep the one-line arithmetic unless common balancing becomes an explicit requirement.
- **Journal projection**: Arena sorts timestamps and recovers area-skill icons; incidents compute
  threat/containment deltas and unavailable responders; sites derive kind/turn labels from actions
  and IDs. Keep these adapters separate, sharing `BattleLogEntry`, `BattleLog` and the playback types.
- **Journal storage**: Arena stores `action` separately alongside `round_seq` and `actor_id`; incidents
  store lifecycle-specific `data` containing the action. They have different persistence/read contracts.
  `CombatAction` already supplies the common action DTO; a unified storage model is out of scope.
- **Charge advancement**: a pure cap/rate helper is optional. Shared rates and `MAX_CHARGE` already
  centralize the tuning; survivor checks, skill resets and terminal-turn behavior belong to callers.

### Do not converge

Incident round math, hazard-team mitigation, aggregate victory conditions, and aggregate progress are
domain-specific. Scene layouts should stay separate as well: `ArenaRing`, `IncidentScene`, and
`WastelandScene` own different framing and information density. The shared seam is the
action/journal/playback layer, not the layout.

## Reviewed decisions to preserve

Recorded from the 2026-10-26 review so they are not re-proposed:

- **Keep `combatExpanded`.** Deriving it only from `expandedCombat` would collapse the battlefield back
  into the briefing after a failed first request (fighting becomes false, persisted round stays 0).
  `frontend/tests/unit/components/exploration/ExpeditionSiteModal.test.ts` protects this.
- **Keep discovery's lock acquisition.** `exploration_service.advance()` commits movement, which releases
  the tick's earlier locks, so `discover_sites` must take fresh locks before reading eligibility and
  writing reports. It costs one ordinary read and two `FOR UPDATE` queries.
- **Map markers report 1 for a single-scene encounter.** Fixed in `55e487db`: `map/reads.py::_site_marker`
  uses the same `uses_single_scene` predicate as the picker and entry. Tests assert explicit expected
  counts for spatial and legacy journeys rather than repeating the implementation's predicate.
