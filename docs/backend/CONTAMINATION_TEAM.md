# Contamination Team — Fire & Radiation Responders

> Status: idea, not scheduled. Roadmap stub: `docs/ROADMAP.md` ("Contamination Team").
> Inspiration: UA "DUDES OF HAZMAT – Toxic Waste Chase" (music video) — hazmat-suit energy,
> sirens, toxic chase vibes. Recorded so the idea is not lost; nothing below is committed.

## Idea

A dedicated hazard-response outfit for the vault:

- **Fire team** — dwellers designated as firefighters, dispatched to fire-hazard incidents ahead
  of (or instead of) whoever happens to be in the room. Needs **fire-resistant suits** — new
  outfit(s) to add (catalog entry, stats, art) plus whatever resistance mechanic they hook into.
- **Radiation response team** — the same shape for radiation incidents: designated responders
  with rad protection, distinct from the fire team.

## Roster concept (undecided — the core design question)

Is this a **standing squad** (assignment panel, on-call rotation, team rooms) or a **priority
list** consulted at spawn time? The current system takes whoever is healthy in the room
(`incident_service.assign_responders`), so any roster is new machinery. Standing squads are more
visible and game-like; priority lists are cheaper and closer to the existing dispatch. Decide
before anything else — it determines whether this is mostly UI or mostly tick work.

## Reuse map (reach for it first)

- **Dispatch:** `incident_service.assign_responders`, `incident_spawning` / `incident_tick`,
  `IncidentType` / `IncidentFamily` in `models/incident.py`.
- **Damage math:** `services/combat/incident_math.py` + `utils/combat.py` — resistance hooks
  belong here, not scattered conditionals. The radiation doc (`docs/backend/RADIATION.md`)
  already scopes how resistance-vs-ingestion questions get answered; fire resistance needs the
  same treatment (damage taken? suppression rate?).
- **Outfits:** item catalogs + shared builders (`utils/item_factory.py`); rad-suit stacking
  against existing radiation resistance must be defined, not discovered.
- **Surfacing:** `notification_service` + SSE incident topics under the modal/toast red line
  (`docs/backend/GAME_MECHANICS.md`, AGENTS.md rule 9).
- **Architecture:** queries in `crud/`, services named `*_service.py`, enums once in
  `app/core/enums.py` with manual `ALTER TYPE` migrations + `PG_ENUM_LABELS_SNAPSHOT` updates,
  thin endpoints with `verify_dweller_access` / `get_user_vault_or_403`.

## Gaps to settle before building

1. What "fire-resistant" modifies numerically, and what a rad-suit stacks with.
2. Roster UX and tick integration (standing squad vs priority list — see above).
3. Training/eligibility requirements for team membership (a new gate, or SPECIAL thresholds?).
4. Whether dispatch is automatic, player-confirmed, or mixed — and what happens when the team
   is away, dead, or under-staffed.

## Relation to other plans

- The Jev classifier (`docs/backend/JEV_CLASSIFIER.md`) could one day feed team dispatch
  (threat triage → who gets sent), but the team must work deterministically first; Jev is a
  later augmentation, not a dependency.
- Race/faction mechanics (`options/identity_modifiers.py`) already shape damage taken — team
  bonuses compose with those at the same choke points, not around them.
