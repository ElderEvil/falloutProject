# Bobbleheads and map collectibles

Status: **plan for review**. Owner: maintainer. Related: `docs/features/EXPEDITION_SITES_GAPS.md`,
`docs/features/LOCATION_KINDS_AUDIT.md`, `docs/features/EXPLORATION_SYSTEM.md`,
`backend/app/data/places/place_groups.json`.

## Goal

Give the world map a collectible layer: seven Vault-Tec SPECIAL bobbleheads placed at named
places, found by a dweller through an existing action, and carried permanently by that dweller.
Two of the seven sit in places that currently have no action at all, so this also introduces the
first salvage interaction for non-clearable places.

Decisions fixed by the maintainer:

- **Finder keeps it.** The bonus belongs to one dweller and dies with them.
- **No duplicate rolls.** A bobblehead is never offered twice to a dweller.
- **Male Vault Boy art only.** The Vault Girl set was generated and discarded.

## Player loop

1. A place shows an action: **Clear** for clearable groups, **Search** for an inert place that
   holds a bound bobblehead.
2. Dispatch one dweller (clearable places still accept a party).
3. Combat or salvage resolves; the bobblehead is awarded to one member and revealed in a modal.
4. The bobblehead appears in the exploration inventory card during the run and in the dweller's
   **Collectibles** tab afterwards.
5. The dweller's SPECIAL rises by 1 wherever `effective_stat` is consumed: production, quest
   gates, combat, relationships, storage.

Each bobblehead exists **once per vault-world**. The unique constraint is per vault, not per
dweller, so the player chooses which dweller to send to each site — that choice is the gameplay.

## Placements and lore

All seven places exist in `backend/app/data/places/seed_places.json`.

| Bobblehead | Place | Group | Action | Lore (item description shown in UI) |
|---|---|---|---|---|
| Strength | Poseidon Energy | power (clearable) | Clear | "Hefted a turbine rotor alone the night the grid went dark. Grip first, questions later." |
| Perception | Museum of Freedom | landmark (inert) | Search | "A lookout's award, left in the curator's desk. The one exhibit the raiders never found." |
| Endurance | The Slog | settlement (inert) | Search | "Passed around the tarberry rows every harvest. The wasteland wears out; it didn't." |
| Charisma | Galaxy News Radio | entertainment (clearable) | Clear | "The station's on-air trophy. The voice on the tape still says the line better than anyone alive." |
| Intelligence | The Institute | research (clearable) | Clear | "A lab mascot from before the walls went up. Its notes are better than its smile." |
| Agility | Mass Pike Tunnel | metro (clearable) | Clear | "A courier's charm, carried the length of the tunnel at a dead run and never dropped." |
| Luck | Red Rocket - Springvale | gas_station (clearable) | Clear | "Pried out of a vending machine that paid out one time too many. The coin landed your way." |

Five clearable sites ship first; the two inert sites are the salvage proof. Later content
(magazines/comics) can fill the remaining inert settlements, cities and regions with the same
mechanism.

## Data and storage

### Catalog (data, no migration)

`backend/app/data/collectibles/bobbleheads.json`:

```json
[
  {
    "key": "strength",
    "name": "Strength Bobblehead",
    "stat": "strength",
    "amount": 1,
    "image": "bobblehead_images/strength.png",
    "location": "Poseidon Energy",
    "action": "clear",
    "description": "Hefted a turbine rotor alone the night the grid went dark. Grip first, questions later."
  }
]
```

`backend/app/utils/collectibles.py` loads and validates it (cached, layer-safe, no DB): unique
keys, `stat` in `SPECIAL_STATS`, `location` resolves through the seeded roster, `action` in
`{"clear", "salvage"}`, image file exists. Art already sits in
`backend/app/static/bobblehead_images/` (7 PNG + manifest).

### Rows

- `VaultCollectible` (`vaultcollectible`): `vault_id` FK CASCADE, `collectible_key` str(32),
  `finder_dweller_id` FK SET NULL, `location_id` FK SET NULL, `found_at` UTCDateTime.
  `UNIQUE(vault_id, collectible_key)` is the durable once-per-vault claim. The claim is never
  deleted with the finder: deleting a dweller nulls `finder_dweller_id` but the place stays
  claimed, so neither deletion, revival nor recycling can reopen it.
- `Dweller.collectible_bonus` JSONB, nullable: the per-stat bonus applied by `effective_stat`.
  `NULL` means no collectibles (correct for every existing row, so the migration needs no
  backfill). The award service writes the join row and this column in one transaction, and a
  consistency test proves they cannot diverge.

The bonus lives only on the dweller row and is cleared everywhere a dweller stops being the
same dweller: `death_service.mark_as_dead` clears it, `revive_dweller` leaves it cleared, and
`dweller_recycling_service.recycle_dweller_for_vault` resets it with the other stats. A revived
or recycled dweller therefore never carries a bonus from a previous life or vault, while the
`VaultCollectible` claim stays intact.

Why the denormalized column: `effective_stat` is deliberately session-free (its docstring and
every game-loop caller rely on that). Reading a relationship there would need `selectinload` on
roughly twenty call paths, and a missed one would silently drop the bonus in one surface only.
The claim table stays the audit/history source; the column is a derived cache owned by one write
path.

### Salvage state

`VaultLocationState.searched_at` (nullable UTCDateTime): set when a salvage resolves. A second
dispatch to the same place is rejected with "nothing left to salvage". Clearable places keep
using `cleared_at`/`reclear_available_at`.

## Award rules

- **Clearable:** only inside the survivor-confirmed branch (`if victory:` and `if deaths <
  party_size:`), after `apply_exploration_damage` has run and living members are re-read, still
  inside the `lock_exploration_with_vault_claim` section. The finder is the living member with the
  highest `luck` (tie: lowest id); solo uses the run's dweller. A wipe awards nothing, matching
  the existing "clear only when someone is left" rule.
- **Salvage:** routed in `dispatch_resolution` *before* the current non-clearable early return.
  Solo means the resolved party has one member, not `team_id IS NULL`: dispatch creates a Team
  even for a single dweller. Under the existing vault lock it re-checks `searched_at IS NULL` and
  the absence of the `VaultCollectible` claim, then awards the bobblehead plus a small caps find
  and sets `searched_at`. A dispatch whose party has more than one member is rejected, and the
  solo test drives the real dispatch-to-arrival path rather than constructing a bare run.
- Award writes the claim and bumps `collectible_bonus`. The `collectible` game event and the
  progression notification are both deferred and published only after `start_return` commits;
  nothing commits inside the branch.

## API and frontend

- Map read (`services/map/reads.py`): derive `action` = `clear` | `salvage` | `none` per location,
  plus `bobblehead_found` for the vault.
- Dispatch validation (`exploration_service.py`): allow a non-clearable target only when the
  catalog binds a `salvage` collectible to it and `searched_at` is null.
- **Storage exclusion:** the find is a `collectible` event and never a `loot_collected` item, so
  the return settlement (`rewards_service._transfer_loot_to_storage`) never considers it for
  storage or overflow. A full vault keeps the finder's bonus with no overflow row.
- `GET /v1/dwellers/{id}/collectibles`: the dweller's found bobbleheads (key, name, stat, image,
  place, found date). Ownership is enforced with `get_user_vault_or_403` plus
  `verify_dweller_access`, and the query is scoped to *both* the dweller's current vault and
  `finder_dweller_id = dweller.id`: recycling keeps the dweller UUID, so an unscoped read would
  expose a previous vault's claim. Recycling clears the bonus on every cross-vault recycle,
  including `reset_stats=False`.
- **Access:** salvage dispatch requires the same visible/unlocked location state rule as normal
  dispatch; a locked location is rejected before any claim is touched.
- Exploration inventory: render the collectible with its image and a "Permanent +1 X" line in the
  existing loot feed; reveal modal on award.
- Dweller detail: a **Collectibles** tab beside `DwellerEquipment`.
- Map detail: the action button reads **Search** for salvage sites, **Clear** otherwise.

## Tests

- Catalog: rejects unknown stat, unknown place, unknown action, missing image.
- `effective_stat`: adds the bonus; `NULL` adds zero; a dead/removed dweller leaves no bonus
  behind elsewhere.
- Award: once per vault (second clear/salvage adds nothing); finder is highest-Luck member;
  party wipe awards nothing; claim row and bonus column stay consistent.
- Death/revival/deletion: death clears the bonus, revival leaves it cleared, deleting the dweller
  keeps the claim with a NULL finder, recycling resets the bonus, and none of them permits
  rediscovery. After a cross-vault recycle the new vault's collectibles endpoint returns no old
  claims.
- Salvage: solo only; second search rejected; unbound inert place not dispatchable; no combat
  damage path; locked location rejected.
- Storage: a full vault keeps the bonus and creates no overflow entry for the find.
- Postgres integration: two concurrent arrivals at one claim produce exactly one award; a late
  write failure rolls back the claim, the bonus and `searched_at`, and delivers neither the
  collectible event nor the notification.
- UTC contract: the pinned inventory in `test_db/test_utc_migration_contract.py` moves from 137
  timestamp columns / 43 tables to 139 / 44 (`found_at`, `searched_at`, `vaultcollectible`), in
  the same PR as the migration.
- API: collectibles read (including a foreign dweller rejection), salvage dispatch, clear dispatch
  award.
- Frontend: inventory card renders image + stat line; Collectibles tab lists and hides correctly.

## Phases

1. **Foundation (backend, no UI):** catalog + loader, `VaultCollectible` and
   `VaultLocationState.searched_at` in one revision under `app/alembic/baseline_versions/`
   (`down_revision = "e5a1b7c9d2f3"`), model registered in `app/models/__init__.py`,
   `Dweller.collectible_bonus` in the same or a second revision, `effective_stat` hook, death and
   recycling clearing, award service with the consistency test. Timestamp columns use
   `UTCDateTime` (timestamptz), the UTC contract pins are updated (139 columns / 44 tables) and
   `alembic heads` stays a single head.
2. **Clearable awards:** wire the victory branch, notification/modal payload, map `action`
   derivation, API read.
3. **Salvage:** `searched_at`, dispatch validation, dispatch branch, tests.
4. **Frontend:** inventory card, reveal modal, Collectibles tab, action labels.
5. **Later:** magazines (temporary buff) and comics (set bonus) reuse the catalog, award service
   and salvage branch; no new interaction needed.

## Feature intake

1. **Player action it extends:** dispatching to map points and reading dweller SPECIAL.
2. **Catalog or config:** seven JSON entries; code adds one model, one loader, one award service,
   one salvage branch.
3. **Work it replaces:** none; it makes the existing 89-place world atlas actionable instead of
   inert, and the salvage branch is the first use of non-clearable places.
4. **Integration cost:** two small migrations, one model, one service, two endpoints, three
   frontend surfaces, tests per section above.
5. **Playtest signal:** find two different bobbleheads with two different dwellers; verify the
   stat change in production math and a quest gate; verify a second search is refused and a
   party wipe awards nothing.
6. **Flag owner:** `game_config.features.collectibles`, default off; maintainer enables after the
   playtest.

## Risks and open decisions

- **Denormalized bonus drift** is the main risk; mitigated by one write path plus a consistency
  test. Alternative (eager-loaded relationship) is documented and rejected above.
- **Once per vault vs once per dweller** is stricter than the maintainer's "no duplicate rolls"
  wording; chosen because a site holds a physical object. Reversible via the unique constraint.
- **Salvage abuse:** no combat rewards, small caps, one-time per place, solo only.
- **Spoilers:** map shows "Search", not the bobblehead's identity, until found.
- **Death/revival/recycling** is the claim's weak point: the claim must survive while the bonus
  must not. Covered by the death-service hook, the recycling reset and the tests above; no
  `ondelete=CASCADE` from dweller to claim.
- Out of scope: magazines/comics mechanics, Vault Girl variants, bobblehead stands/display rooms.
