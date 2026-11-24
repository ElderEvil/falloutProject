# Collectible sets: comics and completion bonuses

Status: **approved plan, backend slice**. Owner: maintainer. Related:
`docs/plans/2026-11-21-bobbleheads-and-map-collectibles.md`,
`docs/features/EXPLORATION_SYSTEM.md`, `backend/app/data/collectibles/`.

## Goal

Comics reuse the bobblehead claim table, award path and salvage branch. Three comics sit in inert
places; each gives its finder a permanent +1 SPECIAL, and holding all three pays a vault-wide
expedition-loot bonus. The same mechanism retroactively groups the seven bobbleheads into a
production set, so the set layer is content, not a new subsystem.

Decisions fixed by the maintainer:

- A claim is durable and once per vault; a comic is found by salvage at an inert site.
- Set bonuses are **read, never stored**: no column, no cached counter.
- `effective_stat` stays session-free; set bonuses are read in the production and loot paths.

## Player loop

1. Map offers **Search** at Megaton, Diamond City and Goodneighbor while the collectibles flag is on.
2. A solo dispatch salvages the site and awards its comic to the dweller.
3. The finder gains `+1` of the comic's SPECIAL immediately (`collectible_bonus`, shared with
   bobbleheads).
4. Holding all three comics multiplies expedition caps at settlement; holding all seven bobbleheads
   multiplies room production.
5. The map payload reports per-set progress so the client can show `2/3` without guessing.

## Data

`backend/app/data/collectibles/comics.json` — 3 entries with the bobblehead fields plus
`kind: "comic"` and `set: "comics"`:

| key | stat | place | action |
|---|---|---|---|
| `grognak_barbarian` | strength | Megaton | salvage |
| `astounding_tales` | luck | Diamond City | salvage |
| `silver_shroud` | charisma | Goodneighbor | salvage |

`backend/app/data/collectibles/sets.json`:

```json
[{ "set": "comics", "name": "The Full Run", "required": 3,
   "bonus": { "type": "expedition_loot_pct", "value": 10 } },
 { "set": "bobbleheads", "name": "Full Cabinet", "required": 7,
   "bonus": { "type": "production_pct", "value": 5 } }]
```

`bobbleheads.json` gains explicit `kind: "bobblehead"` / `set: "bobbleheads"`; its seven entries are
otherwise untouched. No migration: `vaultcollectible` already holds any key it can name.

## Validation (`app/utils/collectibles.py`)

One validator for both catalogs, run at load (cached, layer-safe):

- key/stat/amount/action/description/image/place rules stay as they are;
- `kind` must match the file it was loaded from, `set` must exist in `sets.json`;
- keys are unique across *both* files (they share one claim namespace);
- `sets.json` rejects duplicate ids, a non-positive `required`, an unknown bonus type, and a
  `required` no catalog can satisfy.

## Semantics

- A set pays when the vault holds at least `required` claims of that set **and**
  `game_config.features.collectibles` is on. Nothing is written when a set completes.
- `CollectibleService.bonus_multiplier(db_session, vault_id=…, bonus_type=…)` reads the vault's claim
  keys once and returns `1.0` while the flag is off or the set is incomplete.
- **Production:** read once per tick in `process_vault_resources` and applied in
  `calculate_room_production` — the one place a room's output is split across resources (per-resource
  rates land later, in `_apply_room_production`). Rush payouts pass the same multiplier so a room does
  not produce two different rates.
- **Loot:** applied once in `rewards_service.apply_rewards`, the one place an exploration's caps are
  credited. Multiplying at loot-find time would bake the bonus into the run and pay it twice.
- A claim whose finder was deleted still counts: progress reads claims, never the dweller join.

## API

`VaultMapResponse.collectible_sets: list[CollectibleSetProgressRead]` — `set`, `name`, `held`,
`required`, `active` per defined set. Existing fields keep their names.

## Tests

- Catalog: comics load; unknown set / unknown stat / missing image / non-inert place rejected; sets
  reject duplicate id, non-positive `required`, unknown bonus type.
- Award: a comic grants its own stat once per vault; the second award returns False and does not
  double the bonus.
- Sets: 2/3 pays nothing, 3/3 pays, flag off pays nothing at 3/3, a claim with no finder still counts.
- Production: 7/7 multiplies a real tick by exactly 1.05, not 1.1025.
- Loot: 3/3 credits exactly 1.10× the run's caps at settlement; below it, 1.0×.
- Map read: progress reports held/required/active.

## Feature intake

1. **Extends:** dispatching to inert map points and reading vault progression — existing code owns it.
2. **Catalog:** three JSON entries plus one sets file; code adds a validator, one read helper and one
   multiplication per path.
3. **Replaces:** nothing; it gives the two inert salvage archetypes a reason to exist beyond a
   single bobblehead.
4. **Cost:** no migration, no endpoint, no flag; ~150 production lines and the tests above.
5. **Playtest signal:** find two comics, see 2/3 and no caps change; find the third and confirm a
   100-cap run pays 110 and a 7/7 cabinet raises production by 5%.
6. **Flag owner:** existing `game_config.features.collectibles`; the maintainer enables it.

## Risks and open decisions

- The comic bonus multiplies **caps** at settlement, not item counts: scaling item quantities would
  fight the storage slot budget. Items still roll exactly as the loot tables say.
- Set completion is derived per request (one indexed claim-key query). If the read ever shows up in
  tick profiling, the fix is one aggregate query, not a stored counter.
