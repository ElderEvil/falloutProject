# Contamination Team — Fire & Radiation Responders

> Status: **foundation shipped** — team forming, the participation ledger, outfit hazard resistance, and the
> two fixes this depended on are in. The team is a record, not yet a mechanic: membership has no gameplay
> effect and a join is not yet surfaced. Next steps tracked in `docs/ROADMAP.md`.
> Roadmap stub: `docs/ROADMAP.md` ("Contamination Team"). Inspiration: UA "DUDES OF HAZMAT – Toxic Waste
> Chase" (music video) — hazmat-suit energy, sirens, toxic chase vibes.

## Idea

A dedicated hazard-response outfit for the vault — **earned, not assigned**:

- **Fire team** — dwellers who have repeatedly fought fires and are asked to be ready for the next
  one. Thematically wants **fire-resistant suits** — new outfit(s) to add (catalog entry, stats, art)
  plus whatever resistance mechanic they hook into.
- **Radiation team** — the same shape for radiation incidents.

## Team forming — decided

A dweller **earns** a place; the player never assigns one.

- **Qualify by service.** Every incident a dweller actually fights is counted against that incident's
  type. Three incidents of a *team-eligible* hazard makes the dweller eligible.
- **Teams of three.** The first three eligible dwellers form the team. Later qualifiers go to a
  **bench** and step up when a slot frees — a member dies, leaves permanently, or is away long enough.
- **The dweller raises it.** When a slot opens, the candidate asks through chat, in their own voice,
  reusing the existing `ActionSuggestion` accept/dismiss card (`schemas/chat.py`, rendered by
  `ChatMessageList.vue`). Ignoring the ask simply leaves them on the bench; nothing is forced.
- **Service is recorded in the bio.** Qualifying and stepping up append `bio_entries`, so the dossier
  shows the record — and because `Dweller.bio` is what prompt context and chat read, the dweller
  talks about the team from real memory rather than a scripted line.

### What counts as fighting

A dweller earns credit for an incident the first time they stand in it as a defender — the same set
the round itself used (`get_healthy_adults_in_room`), so children and the already-wounded do not
count. Credit is recorded **once per incident**, not per round: that dedupes the tick's per-round
re-selection and makes a count impossible to farm by drifting in and out.

Outcome does not matter — a dweller earns the incident whether the vault contained it or lost it.
Veterans are made by the fires that got away as much as by the ones that did not, and gating
qualification on victory would tie the team to the vault's power curve instead of to who was
actually there. A fatality still earns the incident: moot for membership, but the bio should carry it.

### Hazard mapping

Two teams, each keyed to the incident types that are genuinely contamination:

- **Fire team** ← `IncidentType.FIRE`
- **Radiation team** ← `IncidentType.RADSCORPION_ATTACK` (the only `radiation`-risk type)

The other five types are intruder and infestation combat, not contamination, and feed no team.
Keying on `IncidentType` (seven values) is deliberate: `IncidentFamily` would merge fire into `HAZARD`
but also merge the three infestations into one bucket, which is not the split we want.

### Two records, deliberately separate

- **Mechanical** — the per-type participation counts and the team/bench membership. This is the
  source of truth for the rule.
- **Narrative** — `bio_entries`. `BIO_ENTRY_CAP = 12` and `compile_bio` drop the oldest non-origin
  entries, so the bio records **milestones** (qualified, took a place, stepped up) and never
  per-incident entries. It can never be the source of truth for the count, and shouldn't try to be.

### Prerequisite — fires do not currently happen

The runtime spawner hardcodes `RADSCORPION_ATTACK` (`incident_spawning.py:126-129`), and
`game_config.incident.get_spawn_weights()` is consumed by nothing at runtime — only the balance CLI
(`cli/simulate_incidents.py`) and the read-only settings endpoint read it. `FIRE` is fully built
(containment objective, `fire_damage` / `fire_suppression`, its own reward tier) and **nothing spawns
it**: only the debug endpoint and tests can. Until the live spawner picks types, only the radiation
team can ever form and the fire team is unreachable content. This is also a latent balance bug — the
weights the settings screen displays are not the weights the game uses.

The fix ships in the same pull request as the rest of the feature, not as a separate change: the
whole thing lands as one PR.

## Slices

Slices 1, 2 and 4 **shipped** together; slice 3 is the first follow-up.

1. ~~**Participation tracking + team forming**~~ — **shipped**: the ledger credits each defender once per
   incident inside the round's commit; qualification at three; three active places plus a bench; a fallen
   member's place passes to the senior bench member; milestones in the bio.
2. ~~**Make fires real**~~ — **shipped**: the runtime spawner rolls from `get_spawn_weights()`, so `FIRE`
   actually occurs. Before this the taxonomy was half-dead content.
3. **The ask** — *next*: the dweller raises their own bench promotion through chat, extending
   `ActionSuggestion` with a variant (Confirm/Dismiss reuse as accept/decline), paired with a
   `notification_service` entry so it reaches the bell under the modal/toast red line. Semantics still
   open: announcement, consent gate, or teammate suggestion.
4. ~~**Resistance & outfits**~~ — **shipped**: `fire_resist` / `radiation_resist` columns, fire resistance
   applied beside `incident_response_pct`, a declared radiation share overriding the legacy type/name
   table, plus the firefighter suit, the hazmat suit, and the legendary both-hazard outfit. Shown on item
   cards. This also fixed equip never invalidating the wearer's cached relationship, which had silently
   zeroed *all* outfit radiation protection.

## Reuse map (reach for it first)

- **Dispatch:** `incident_service.assign_responders`, `incident_spawning` / `incident_tick`,
  `IncidentType` / `IncidentFamily` in `models/incident.py`.
- **Record:** `services/bio_service.py` — `append_entry` / `BIO_SECTIONS` are the single authority for
  entry sources; a new source needs a section here, a frontend label (`DwellerBio.vue`), and a test.
- **The ask:** `schemas/chat.py` `ActionSuggestion`, `agents/chat_schemas.py` action maps,
  `notification_service.create_and_send` (the exit-request precedent, `from_dweller_id`).
- **Damage math:** `services/combat/incident_math.py` + `utils/combat.py` — resistance hooks belong
  here, not scattered conditionals. `docs/backend/RADIATION.md` already scopes how
  resistance-vs-ingestion questions get answered; fire resistance needs the same treatment.
- **Outfits:** item catalogs + shared builders (`utils/item_factory.py`); rad-suit stacking against
  existing radiation resistance must be defined, not discovered.
- **Surfacing:** `notification_service` + SSE incident topics under the modal/toast red line.
- **Architecture:** queries in `crud/`, services named `*_service.py`, enums once in
  `app/core/enums.py` with manual `ALTER TYPE` migrations + `PG_ENUM_LABELS_SNAPSHOT` updates, thin
  endpoints with `verify_dweller_access` / `get_user_vault_or_403`.

## Still open

1. **Persistence shape** — per-type counts as a JSON dict on `Dweller` (mirrors
   `apprentice_stat_gains`) vs a participation table; membership as a table vs derived.
2. **Bench semantics** — does a member away on an expedition vacate the slot, and does the bench step
   up automatically or only when asked?
3. **Resistance semantics** — what fire resistance changes numerically, and how rad-suit protection
   stacks with existing radiation resistance (slice 4).
4. **Dispatch** — deferred by design: the team is a designation and a record until the Jev classifier
   is wired to route threats.

## Future — real-time movement and positioning

Movement is instant today: `assign_responders` teleports dwellers into the incident room and the tick
re-reads occupancy each round, so room is the only positional anchor a dweller has
(`Dweller.room_id`) — there is no position or path state. The spatial substrate already exists
though: rooms carry grid coordinates, elevators link floors, and `utils/room_rules.py` enforces
stacking, access, and adjacency.

When movement becomes real-time, three things change for this feature:

- **Response gains latency.** A team stationed far away arrives after the fire has spread, so *where
  the team is* becomes as important as *who is on it*. That finally gives the team a home — the
  Fire Station / Hazmat Bay idea — a real job: not the roster, but the **muster point**.
- **Coordination becomes possible.** A team that assembles and moves together is the natural unit for
  cooperation; the roster built here is exactly the "who" such a system would move.
- **Dispatch must be travel, not teleport.** A second reason dispatch belongs with Jev rather than
  here.

Two constraints this places on the current work:

- **Membership must stay an identity, never a position.** Today "responder" means "happens to be in
  the room", conflating the two. Team membership and participation counts must record *who you are*;
  presence stays a derived, per-round fact. Store it the other way and a movement system invalidates
  the roster.
- **Participation stays presence-based.** Earning credit by actually standing in the room during a
  round survives the change untouched — it simply gets harder, because getting there takes time.

## Relation to other plans

- **Quest parties share this shape.** `QuestParty` + `crud/quest_party.assign_party` and
  `HazardTeamMember` + `contamination_team_service` both answer "which dwellers are on this thing", built
  separately. The common parts should be extracted so they do not drift — one availability/eligibility
  policy, and ideally one roster primitive both consume. Three TODOs already ask for it
  (`crud/quest_party.py:54`, `services/exploration_service.py:130`, and the `is_in_vault_and_active` note
  in the roadmap simplification backlog). The policy cannot live in `app/services/` (the architecture
  guard allows CRUD to import only `room_assignment_policy`); `app/utils/` is the home, per AGENTS.md
  rule 11. Tracked in `docs/ROADMAP.md`.
- The Jev classifier (`docs/backend/JEV_CLASSIFIER.md`) is where **dispatch** lands: the team is
  deliberately a designation-and-record feature until Jev triages threats and decides who gets sent.
  Formation must work deterministically first — Jev consumes the team, it does not gate it.
- Race/faction mechanics (`options/identity_modifiers.py`) already shape damage taken — team
  bonuses compose with those at the same choke points, not around them.
