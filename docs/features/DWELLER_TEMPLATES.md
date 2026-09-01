# Dweller Templates — Rare & Legendary System (Lore-Accurate)

> **Status:** Design doc — `rare.json` / `legendary.json` enrichment + curated origin/visited system. Branch intent: make rare/legendary non-procedural (fixed lore templates, not sampled stats). Names normalization deferred per owner request.
> Related: `BIO_MAP_UNCOVERING.md`, `WORLD_MAP.md`, `EXPLORATION_SYSTEM.md`, `FAMILY_SYSTEM.md`

## 1. Goal

Replace the current random rare/legendary generation with a **template system** backed by real Fallout lore:

- Every `RARE` and `LEGENDARY` dweller comes from a **JSON template** (`backend/app/data/dwellers/{rare,legendary,quest_rewards}.json`) that ships `bio`, `visual_attributes`, canonical `origin_place` + `visited_places`, and fixed `SPECIAL`.
- Common dwellers stay **procedural/random** (Faker + `_PLACE_POOL` + `_roll_identity`). Rare/legendary become **curated roster picks**: selection may be random, but the selected dweller's identity, SPECIAL, bio, visuals, origin, and visits are fixed.
- Map uncovering (`map_service.register_bio_places`) uses each selected template's fixed lore locations (Rivet City, Tenpenny Tower, Megaton, Goodneighbor, Diamond City, Vault 101, etc.), not a sampled 12-place pool.
- `quest_rewards.json` is the reference shape — it already has `bio` per entry; `rare.json`/`legendary.json` gain the same fields.

## 2. Current State (why this is needed)

### 2.1 What exists today

| Path | Rarity | Count | Fields today | Lore? |
|---|---|---|---|---|
| `dwellers/rare.json` | `Rare` | 24 | `gender, rarity, outfit, SPECIAL, first/last_name` | **No** — fictional Shelter-original names (Akira Katana, Carlos the Great, Laurel Divinitus…) |
| `dwellers/legendary.json` | `Legendary` | 24 | `gender, rarity, weapon, outfit, SPECIAL, first/last_name` | **Yes** — FO3/FO4 canon but **no bio/visuals** |
| `dwellers/quest_rewards.json` | `Legendary` | 7 | `first/last_name, gender, rarity, SPECIAL, bio` | **Yes** — TV show, and the only file with `bio` today |
| `data/vault/legendary_dwellers.json` | — | 23 | wiki-scraped `name, image_title, special, gear` | Source for `LEGENDARY_DWELLER_IMAGE_FILES` / portrait URLs |

`game_data_store.dwellers` merges all three (`rare + legendary + quest_rewards`) and assigns `image_url/thumbnail_url` via `get_legendary_dweller_image_url()`. `DwellerCreateWithoutVaultID` already inherits `bio` (≤1024ch) + `visual_attributes` (JSONB) from `DwellerBase` — no database migration is needed. It does **not** contain `origin_place` or `visited_places`, so templates need a separate loader schema that preserves this creation-only metadata.

### 2.2 How creation works today (random)

- `create_random_common_dweller(seed, rarity)` in `backend/app/utils/dwellers.py`:
  - `rare/common` cases **still roll random SPECIAL** via `get_stats_by_rarity()` (rare 3–6, legendary 6–10 ranges) — templates are **not consulted**.
  - Bio/places come from `_procedural_bio_places(rng, rarity)` → `rng.choice(_PLACE_POOL)` (14 names) + `rng.sample(remaining, max_visited)` where `max_visited = game_config.bio.visited_by_rarity[rarity]` (`{common:2, rare:4, legendary:5}`) → `_render_template_bio()`.
  - Identity (`race/faction/state_of_being`) from `_roll_identity(rng)` using `game_config.dweller.race_weights` / `human_faction_weights`.
- Callers that need rarity:
  - `vault_service._roll_initial_rarity()` — `COMMON` vs `RARE` at `standard_rare_chance=0.04 / boosted=0.12`, then `create_random(..., rarity=RARE)` still generates a random dweller.
  - `radio_service.recruit_dweller()` — `RARE if random() < radio.rare_chance (0.04) else COMMON` → same random path; legendary **never** from radio (correct).
  - `reward_service.grant_lunchbox()` — random name + `rarity=choice(COMMON,RARE,LEGENDARY)` + random level, ignoring templates entirely.
  - `vault_service._create_boosted_legendary_dwellers()` — **only place that uses templates directly**: `Dweller(**template.model_dump(exclude={"weapon","outfit"}), vault_id=...)` for 3 hard-coded names (Abraham, Allistair, Bittercup).
  - `pregen_service` — creates `COMMON` random dwellers then overwrites `bio` with discovery-name prefixes/suffixes (different pool than `_PLACE_POOL`), registering its own places.

Result: radio/vault/lunchbox rare/legendary dwellers are **statistically rare but content-random** — no fixed lore, no stable bio, no curated visuals, no canonical origin.

## 3. Design — Curated Template System

### 3.1 Principle: system, not randomness

> *Common = procedural. Rare/legendary = curated.*

- `COMMON` stays procedural (Faker names, rolled SPECIAL 1–3, random `_PLACE_POOL` origin, `_roll_identity`).
- `RARE` and `LEGENDARY` become **roster picks**. No Faker or stat roll: a selected template's SPECIAL, identity, bio, visuals, origin, and visits are used unchanged. Selection is reproducible when an RNG/seed is supplied; otherwise it is intentionally random among eligible templates.
- `origin_place` + `visited_places` are **template metadata**, not `Dweller` columns and not sampled. After the dweller has been persisted, the shared creation flow passes this metadata directly to `map_service.register_bio_places()`.
- The hand-authored bio mentions the same place names verbatim for `DwellerBio.vue` linkification. The regex backfill service is not the runtime source of truth; its known-place registry must be expanded for any template locations that must be recoverable from existing free-text bios.
- Lunchbox and quest grants also draw from the roster (see §3.5).

This satisfies the requirement: *"rare/legendary ones not random — same goes for places visited/origin — it must be a system."*

### 3.2 JSON schema and transport (additive, no migration)

Extend each entry in `rare.json` / `legendary.json` to match `quest_rewards.json` plus visuals:

```json
{
  "template_id": "allistair-tenpenny",
  "first_name": "Allistair",
  "last_name": "Tenpenny",
  "gender": "Male",
  "rarity": "Legendary",
  "bio": "Founder and recluse owner of Tenpenny Tower. The 80-year-old pre-War British expatriate who paid Mister Burke to erase Megaton for the view — Very Evil, and very particular about his suite.",
  "visual_attributes": {
    "race": "human",
    "faction": "none",
    "age": 80,
    "height": "tall",
    "build": "average",
    "skin_tone": "light",
    "eye_color": "blue",
    "hair_style": "wavy",
    "hair_color": "light gray",
    "appearance": "average",
    "expression": "smug",
    "distinguishing_features": ["mole"],
    "clothing_style": "formal",
    "background": "luxury tower",
    "voice_line_text": "What a grand display of fireworks!"
  },
  "origin_place": "Tenpenny Tower",
  "visited_places": ["Megaton", "Rivet City"],
  "weapon": "Victory rifle",
  "outfit": "Tenpenny's suit",
  "strength": 2, "perception": 9, "endurance": 2, "charisma": 9, "intelligence": 7, "agility": 2, "luck": 9
}
```

The loader uses a dedicated `DwellerTemplate` schema rather than `DwellerCreateWithoutVaultID`. It contains the persistable dweller fields plus `origin_place` and `visited_places`, with `visual_attributes: DwellerVisualAttributes | None` so identity validation runs while loading JSON. It provides a method that produces `(DwellerCreateWithoutVaultID, origin_place, visited_places)` for the shared creation flow. This prevents Pydantic from silently discarding the map metadata.

Field notes:

- `bio` ≤1024ch (model constraint). Keep 600–900ch as in `DwellerBackstory` (AI prompt contract) so manual + AI bios stay comparable.
- `visual_attributes` must pass `DwellerVisualAttributes.validate_identity_combination`: `race` ∈ `RaceEnum {human, ghoul, super_mutant, synth}`, `faction` ∈ `FactionEnum`, `state_of_being` when `race != human` (`GhoulFeralnessEnum | SuperMutantMutationEnum | SynthTypeEnum` in `STATE_OF_BEING_TYPE`). Use canonical `FactionOption` / `RaceOption` values.
- `origin_place` + `visited_places` are explicit template fields (len ≤64, `visited_places` ≤ `game_config.bio.max_visited(rarity)`), de-duplicated after normalization, and must be mentioned verbatim in `bio`. Avoid `GENERIC_ORIGIN_SKIP = {"", "wasteland", "the wasteland", "unknown"}`.
- CX404 (dog) and Snip Snip (robot) cannot receive valid `DwellerVisualAttributes` under the current race model. Their treatment is a product decision in §7; do not invent an invalid race value in JSON.
- `weapon`/`outfit` remain nullable (`Lincoln's Repeater`, `null` for Amata etc.). Image URL stays derived via `legendary_dweller_assets.get_legendary_dweller_image_url(name)` — no JSON change needed.

For `rare.json` (currently fictional) enrich in place first (keep names; owner will test and advise on replacement with lore side-cast later). Each rare entry gets a wasteland archetype (`Ninja outfit`, `Surgeon outfit` etc. already hint at it) turned into a short lore bio + plausible origin (`Little Lamplight`, `Canterbury Commons`, `Arefu`…).

### 3.3 Lore sources (so bios/visuals are not invented)

Legendary canon (FO3 base 20 + FO4/FO76/TV — fallout.wiki):

- **FO3:** Abraham Washington (Rivet City, 45, curator), Allistair Tenpenny (Tenpenny Tower, 80, Very Evil), Amata Almodovar (Vault 101), Bittercup (Big Town), Butch DeLoria (Tunnel Snakes, Vault 101), Colonel Augustus Autumn (Enclave), Confessor Cromwell (Children of Atom), Eulogy Jones (Paradise Falls), Harkness (Rivet City — synth reveal), James (Vault 101), Jericho (Megaton), Lucas Simms (Megaton sheriff), Madison Li (Project Purity), Owyn Lyons (Brotherhood Elder), Sarah Lyons, Scribe Rothchild, Star Paladin Cross, Three Dog (Galaxy News Radio), Moira Brown (Megaton), Mister Burke, Old Longfellow (Far Harbor — FO4).
- **FO4:** Piper Wright, Preston Garvey (Minutemen), plus FO3-origin dwellers already covered.
- **Shelter-original:** Ed the Ghoul.

Per-character fields to capture: affiliation, role, age, voice actor note, `SPECIAL` (keep current Shelter values — they intentionally differ from FO3 GECK stats), signature outfit/weapon. Visuals derive from wiki infoboxes (hair, eye color, race, faction).

**Do not fix names in this iteration** per owner request (`Abraham Washington` etc. stay split as-is; normalization deferred).

### 3.4 Origin & visited — lore place registry

Instead of sampling `_PLACE_POOL` (14 names) or discovery `prefixes/suffixes`, templates carry **curated Fallout locations**:

- Canonical origins per dweller: e.g. `Rivet City` for Abraham Washington, `Tenpenny Tower` for Tenpenny, `Vault 101` for Amata/Butch/James, `Megaton` for Moira/Lucas/Jericho/Mister Burke, `Paradise Falls` for Eulogy Jones, `Galaxy News Radio` for Three Dog, `The Institute` / `Rivet City Lab` for Madison Li, `Goodneighbor` / `Diamond City` for FO4 cast, `Little Lamplight` / `Big Town` / `Canterbury Commons` / `Arefu` / `Republic of Dave` etc. for rares.
- `visited_places` = 0–5 lore places the character canonically passed through (quest locations, faction hubs). Keep `visited_by_rarity` caps (`common 2, rare 4, legendary 5`) as the budget — rare/legendary templates simply fill that budget with lore names instead of random draws.
- All names normalize via `normalize_place_name()` and resolve to deterministic `schematic_coords()` / `WastelandLocation` markers. No coordinate change is needed. Add every new canonical template place to the backfill known-place registry if free-text recovery is required for it.

### 3.5 Integration points (where randomness becomes roster picks)

| Caller today | Current | After |
|---|---|---|
| `utils/dwellers.create_random_common_dweller(rarity=RARE/LEGENDARY)` | rolls random stats/name/places | Rename or delegate to a template-aware factory. `COMMON` retains the current procedural path; rare/legendary returns a persistable payload plus explicit map metadata. |
| `crud/dweller.create_random(..., rarity)` | calls above + registers `_bio_places` | Become the single template-instantiation path: persist the template payload, then register its explicit lore places. |
| `vault_service._roll_initial_rarity` + `_create_initial_dwellers` | random `COMMON/RARE` dwellers | Same rarity roll, but `RARE` uses an eligible template. `special_boost` must not overwrite template SPECIAL; see §7. |
| `radio_service.recruit_dweller` | `RARE if random()<rare_chance else COMMON` | same roll; `RARE` path returns a template dweller |
| `reward_service.grant_lunchbox` | random rarity + random name | Select a rarity by the approved lunchbox weights, then use the same template-aware creation flow for rare/legendary. Commons remain procedural. |
| `reward_service.grant_dweller` (quest `dweller` rewards) | resolves `template_id`, but only persists a subset of template fields | Route template rewards through the shared flow so visual attributes and map places are retained and registered. |
| `vault_service._create_boosted_legendary_dwellers` | directly constructs three template dwellers and skips map registration | Use the shared flow for its explicit smoke-test names, retaining its equipment setup. |
| `pregen_service` / `utils/dwellers._PLACE_POOL` | common-only dev seeding with separate pools | Keep unchanged unless the CLI gains an explicit rarity option; it currently seeds only commons. |

Add one helper to `StaticGameData`:

```python
def get_dwellers_by_rarity(self, rarity: RarityEnum) -> list[DwellerTemplate]: ...
def pick_template(self, rarity: RarityEnum, rng: Random | None = None) -> DwellerTemplate: ...
```

Template selection excludes a template already active in the target vault. Cross-vault uniqueness is deliberately deferred for later investigation. If no eligible template remains, fall back to a common dweller. No event-bus changes are needed. Trading post, breeding, death, exploration, and chat agents continue to consume `Dweller.bio` / `visual_attributes` / `WastelandLocation`.

### 3.6 What is NOT changing

- No name normalization in this iteration (owner deferred).
- No new `RarityEnum` value (`unique` stays modeled as named `LEGENDARY` templates).
- No changes to `WastelandLocation` schema, `WORLD_SCALE`, or `collision_nudge`.
- No new AI bio generation path — AI (`backstory`, `extend_bio` prompts) remains a manual, quota-gated enrichment that appends to `bio` and registers extra `visited_places`.

## 4. Affected Files

| Area | File | Change |
|---|---|---|
| Data | `backend/app/data/dwellers/rare.json` | add `bio`, `visual_attributes`, `origin_place`, `visited_places` per entry (fictional archetype bios) |
| Data | `backend/app/data/dwellers/legendary.json` | same — one lore bio + visuals + canonical places per legendary |
| Data | `backend/app/data/dwellers/quest_rewards.json` | add the same metadata where supported; resolve robot/animal visual policy before changing CX404/Snip Snip |
| Schema + loader | `backend/app/schemas/dweller.py`, `backend/app/utils/static_data.py` | add `DwellerTemplate`, template selection, and validated metadata preservation; keep image-url post-processing |
| Generator + CRUD | `backend/app/utils/dwellers.py`, `backend/app/crud/dweller.py` | keep the common generator; add one shared template-instantiation path that persists data and registers explicit map places |
| Services | `backend/app/services/reward_service.py`, `backend/app/services/vault_service.py` | route lunchbox, quest template rewards, and boosted templates through the shared flow |
| Config | `backend/app/core/game_config.py` | no change (caps already correct) |
| Map | `backend/app/services/map_service.py` | no change (already rarity-scaled cap) |
| Tests | `backend/app/tests/test_crud/test_dweller.py`, `test_reward_service_*`, `test_places.py`, new static-template validation test | add: common stays random; seeded selection is reproducible; templates keep fixed fields; maps register explicit lore places; duplicate/exhaustion policy; every JSON template validates |

## 5. Validation

- `uv run pytest app/tests/test_crud/test_dweller.py -v` — common remains procedural; a seeded roster selection is reproducible; template SPECIAL and visuals are unchanged.
- `uv run pytest app/tests/test_services/test_reward_service*.py app/tests/test_services/test_map_service.py -v` — lunchbox, quest, and boosted-template paths preserve metadata and register lore places, capped by `visited_by_rarity`.
- Static-template test — validates every JSON entry: required metadata, bio length, SPECIAL bounds/invariants, legal visual identity, normalized unique places, valid rarity cap, and unique template names/IDs.
- `uv run ruff check . && uv run ruff format .` — JSON-adjacent Python only.
- Manual: force a rare and a legendary selection through the shared factory; their details show the curated bio/visuals and `/vault/{id}/map` shows their lore markers (Rivet City, Tenpenny Tower…).

## 6. Non-Goals

- No quest-chain redesign, chain lifecycle, or reward-contract changes (see ROADMAP P1).
- No item-reward or quest-economy rebalancing; the dweller rarity weights are the explicit decision in §7.
- No frontend changes — `DwellerBio.vue` linkify + `WorldMap.vue` already render bio places.

## 7. Settled Decisions

1. **Template uniqueness:** unique per active vault. Soft-deleted and traded dwellers do not reserve the template. If the per-vault roster is exhausted, create a common dweller. Cross-vault uniqueness is deferred.
2. **Initial-vault boost:** do not apply `special_boost` to a selected template; its curated SPECIAL is authoritative.
3. **CX404 and Snip Snip:** treat them as non-human companion templates (dog and robot respectively), with `visual_attributes: null`. No race/identity-domain expansion in this iteration.
4. **Lunchbox dweller rarity:** use `70% common / 20% rare / 10% legendary`.
5. **Rare roster:** retain the current fictional Shelter names and enrich them with internally consistent wasteland bios.

Name normalization (`Colonel Autumn` → `Augustus Autumn`, `Dr. Li` → `Madison Li`, etc.) and cross-vault template uniqueness remain intentionally deferred.
