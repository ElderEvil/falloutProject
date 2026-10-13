# Internal Unrest — Design Contract

> Status: **proposed, not implemented.** Feature-flagged off by default. This document decides the
> mechanic before any code, mirroring `RESOURCE_ECONOMY_BALANCE.md`: the numbers below are a **playtest
> baseline, not a final specification**.

## Goal

Give `state_of_being` a gameplay consequence. Today a ghoul's `sane/wild/feral`, a super mutant's
`mild/average/behemoth`, and a synth's `gen_1/2/3` are cosmetic: they change the portrait and the
dialogue, never the simulation. Internal unrest makes the severe end of each ladder dangerous to the
dwellers standing next to it, and turns the synth's existing concealment (`passes_as_human`) into a
live threat.

## Current state

- **Races and stages already exist.** `RaceEnum` (human/ghoul/super_mutant/synth) and the
  `state_of_being` union (`GhoulFeralnessEnum`, `SuperMutantMutationEnum`, `SynthTypeEnum`) live in
  `app/core/enums.py`; race/state resolve through `app/options/races.py`.
- **Every incident is external.** `IncidentType` holds only outsider/event types (raider, radroach,
  mole rat, deathclaw, feral ghoul, radscorpion, fire). There is no dweller-vs-dweller path, so this
  is a new **incident family**, not a new entry in an existing one.
- **Synths are already infiltrators.** `passes_as_human()` treats gen 3 (and unknown) as concealed and
  gen 1/2 as visibly synthetic. Concealment is currently narrative-only.
- **JEV is a typed probability model**, not a text LLM: callers ask a Pydantic field as a question and
  get a confidence. It is the right tool for a *decision*, not for damage.

## What this is not

- **Not an external spawn.** It must not ride the incident spawn cadence (`spawn_chance_per_hour`,
  `max_active_incidents`, spawn cooldown, spread) that the balance pass just tuned. It has its own
  trigger and its own cap.
- **Not a chaos roll the player cannot influence.** Every involuntary death needs a lever the player
  can pull (assignment, happiness, a stabilize action). A pure dice roll is out of scope.
- **Not JEV-gated.** No damage, death, or victory outcome may depend on a remote model. JEV may only
  choose a narrative branch, with a deterministic fallback.

## Contract — incident family

Add a fourth family, `IncidentFamily.INTERNAL = "internal"`, presented truthfully as **vault-internal**,
never as an intrusion.

| Proposed `IncidentType` | Aggressor | Objective | Surface |
|---|---|---|---|
| `GHOUL_TURN` | ghoul in the room | `DEFEAT` (subdue/kill the aggressor) | the room's occupants fight back |
| `SUPER_MUTANT_RAMPAGE` | super mutant in the room | `DEFEAT` | the room's occupants fight back |
| `SYNTH_DEFECTION` | concealed gen-3 synth | `CONTAIN` (resolve without a massacre) | reveal / flee / fight branch |

Design rules:

- **Target is a dweller, not a threat pool.** The aggressor is an existing dweller in the room; the
  "enemy power" is that dweller's `combat_power`, and the "defenders" are the roommates. This inverts
  the current external model (fixed threat vs responding dwellers) and reuses the same pure helpers —
  `incident_math`, `combat_power`, `damage_reductions` — so no second combat formula is introduced.
- **Roommates only, ≥ 1.** A dweller alone in a room cannot turn (nothing to attack); the room must
  have at least one other living adult, or the incident does not start.
- **No hazard team.** `hazard_team_for()` returns `None` for these types: they train no team and get no
  `TEAM_HAZARD_RESIST` / `TEAM_RESPONSE_BONUS`.
- **No spread.** `spread_count` stays 0; an unresolved unrest ends the fight, it does not walk the
  vault. Panic consequences (happiness) apply on resolution, not by adjacency.
- **Death cause.** Add `DeathCauseEnum.MUTINY` so unrest deaths are separable in stats and the bio log,
  rather than folded into `INCIDENT`.
- **Own cap.** At most one active internal incident per vault, independent of `max_active_incidents`.

## Contract — trigger probabilities (provisional, per assigned dweller-hour)

Gated to dwellers who are **assigned to a room with at least one other living adult**. Base chance by
stage; multiplied by the modifiers below; clamped to a ceiling.

| Stage | Base / dweller-hour | Rationale |
|---|---:|---|
| ghoul `sane` | 0 | full self-control |
| ghoul `wild` | 0.5% | irritable, mostly stable |
| ghoul `feral` | 3.0% | the dangerous end |
| super mutant `mild` | 0 | |
| super mutant `average` | 1.0% | |
| super mutant `behemoth` | 4.0% | |
| synth gen 1/2 | 0 | visibly synthetic, no cover to break |
| synth gen 3 | 0.2% | rare; see the JEV boundary |

Modifiers (multiplicative, then clamp):

- **Happiness** below `internal_unrest_happiness_threshold` (propose 30) → **×2**.
- **Low endurance** of the aggressor (wounded/fed state) → ×1.5 — a struggling dweller lashes out.
- **A stabilizer is active** on the aggressor → ×0 (see counterplay).

These are start-of-unrest chances only; they are intentionally low because the cost is a death. Expect
to move them after playtest, exactly as the resource rate moved.

## Contract — counterplay (must ship with the mechanic)

1. **Assignment is the primary lever.** The UI must make the risk legible: the dweller roster and the
   room assignment picker flag a `wild`/`feral`/`behemoth` dweller, so the player can choose not to
   room them with fragile humans. (The picker already ranks by the room's SPECIAL; a risk badge is an
   additive hint, not a reorder.)
2. **A `stabilize` action.** A medbay-gated action on a flagged dweller that suppresses the roll for a
   window (`internal_unrest_stabilize_hours`, propose 6). This is the "act before it happens" verb.
3. **Happiness management** already exists and directly halves or doubles the roll.

No counterplay, no ship: if we cannot offer at least `stabilize` + assignment, the mechanic is just a
random death and should stay unshipped.

## Contract — synth boundary (JEV)

`SYNTH_DEFECTION` is a reveal, not a rampage, and it is the **only** place JEV appears:

- Gen 3 only (a concealed synth — gen 1/2 are already known, so there is nothing to reveal).
- On trigger, JEV answers one typed question — the branch: **confess / defect-and-leave / turn
  hostile** — with a pinned model and a tuned confidence threshold.
- **Fallback:** when JEV is disabled or unconfigured, the branch is decided by the deterministic default
  (propose: confess), so the feature degrades to a fixed narrative instead of failing.
- JEV never decides damage, death, or whether the incident resolves. Those stay in the pure combat
  kernel.

If JEV proves noisy, the whole synth branch can ship as a deterministic "cover blown" incident and drop
the model entirely — that is why it is isolated behind the flag.

## Surfacing (progression red line)

Per `GAME_MECHANICS.md`, every player-facing progression event surfaces **in addition to** the bell:

- New notification types (`INTERNAL_UNREST_STARTED`, `INTERNAL_UNREST_RESOLVED`, and for the synth
  branch a reveal type), always-on categories (never opt-out-able).
- A toast on start and resolution, and a modal when a dweller dies to unrest, so the death is never
  bell-only.
- Bio-log entry on the aggressor and on any victim.

## Phasing

| Phase | Deliverable | Gate |
|---|---|---|
| 0 | This document | — |
| 1 | `GHOUL_TURN` + `SUPER_MUTANT_RAMPAGE`, deterministic probabilities, reuse the combat kernel, sim coverage in `simulate_incidents` | flag off |
| 2 | `stabilize` action + risk badges + full surfacing | flag off |
| 3 | `SYNTH_DEFECTION` with the JEV branch and deterministic fallback | flag off |

Enablement is per-deployment via the feature flag for playtest, then a balance pass before any default
flip — the same path the resource rate took.

## Guardrails

- **Feature flag.** Add `FeatureConfig.internal_unrest` (default `False`), surfaced through
  `/system/features` next to `race_mechanics`/`faction_mechanics`.
- **Layering.** Endpoint → service → CRUD, unchanged. New logic in `services/`, no business logic in
  routers. The combat kernel stays pure and shared.
- **Enums in one place.** `IncidentType`, `IncidentFamily`, `DeathCauseEnum`, `NotificationType`
  additions live in `app/core/enums.py`; the PG enum migration is written by hand and
  `PG_ENUM_LABELS_SNAPSHOT` is updated in the same commit (autogenerate does not detect enum values).
- **No pacing coupling.** Does not read or write `spawn_chance_per_hour`, `max_active_incidents`,
  `spawn_cooldown_seconds`, or spread config.
- **One source of truth for balance.** Chances live in `game_config` (env-overridable), not inline
  literals, so the simulator and production share them.

## Open questions (decide before Phase 1 code)

1. Should an unrest be able to **kill** roommates, or only wound? (Proposed: it can kill — otherwise it
   is not a threat — but only the aggressor's roommates, and only after the stabilize lever exists.)
2. Does the aggressor ever **die** in the fight (subdued/killed by roommates), and does that carry a
   happiness cost? (Proposed: yes, and a vault-wide happiness hit on any unrest death.)
3. Difficulty mapping: is aggressor power `combat_power` directly, or scaled by stage (behemoth ×N)?
4. Does unrest require the vault to be **online** like incidents do, or can it only fire while the
   player is present (so the player can respond)?
5. Synth reveal: should the player ever be able to **prevent** it (Institute ties, loyalty), or is it
   always a surprise?
6. Which stats feed the reveal branch — faction, `passes_as_human`, happiness, or a hidden loyalty
   counter?
