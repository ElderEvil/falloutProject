# Location kinds — source audit

**Date:** 2026-10-03. **Scope:** `feat/wasteland-atlas`, HEAD `4be3c0792ebc78f756cd33aaf76a3c3fd8e09c63` (`feat(world): backend-owned world generation core, snapshot, and dev reset`), current working-tree source. At entry, `PROTOTYPE_TO_PRODUCTION_PORT.md` was modified and `WORLD_EVOLUTION_ISSUES.md` untracked; neither was changed by this audit.

Read-only code/catalog inspection, plus JSON inventory using Python stdlib. No tests, lint, typecheck, database inspection, AI calls, servers, commits, or runtime/UI validation. “Implemented” below means present in source, not proven deployed. References are repository-relative `file:line`; line numbers describe this audit snapshot.

## Executive findings

1. **There is no single location-kind enum.** Registry identity (`place`/`vault`), per-vault presentation (`origin`/`visited`/`discovery`/`home_vault`), gameplay archetype (`group_key`), prototype `LocationKind`, and expedition-site IDs are separate contracts. Renaming or merging them would lose information.
2. **Gameplay archetypes already exist and have icons.** The 16-entry backend catalog owns clearability, difficulty, loot table and reclear hours. Production legend/list/detail consume it, but SVG map markers do not use its icons.
3. **Backstories create or reuse real registry places, not prototype locations.** Matching is by normalized name. AI output contains names, not archetypes; novel names default to canonical `place`, `source=emergent`, `group_key=None`. No semantic inference from “Factory”, “Vault”, etc. occurs.
4. **Discovery has the same classification gap.** Random prefix/suffix names may sound like a clearable site but remain ungrouped unless their exact normalized name appears in the seed roster. Ungrouped locations cannot be dispatched to clear.
5. **Same-name content is not necessarily the same site.** Registry `Super Duper Mart`, hand-authored expedition site `super_duper_mart`, and generated `super_duper_mart` prototype markers have different identities, coordinates, progression and rendering. No inspected bridge merges them.
6. **Visibility is not marker provenance.** Bio links start locked; chat unlocks links after three user messages; exploration discovery unlocks immediately. State type is first-write-wins except home promotion, so a discovered origin may retain its flag rather than become a compass.

## 1. Vocabulary and ownership matrix

| Axis / actual vocabulary | Authority and consumers | Effects / defaults | Backstory and UI relationship |
|---|---|---|---|
| Canonical kind: `place`, `vault` | `backend/app/core/enums.py:233`; `backend/app/models/world_location.py:46`; CRUD and seed service | PG `placekind`; vault number required only for VAULT; unique vault number among VAULT rows. Determines seeded NPC signal query. Not a loot/difficulty taxonomy. | Bio/discovery creation explicitly uses PLACE. Existing VAULT can be reused. Canonical kind is **not exposed** on ordinary location responses. |
| Per-vault type: `origin`, `visited`, `discovery`, `home_vault` | `backend/app/core/enums.py:240`; `VaultLocationState` at `backend/app/models/world_location.py:66`; map projection | One state per vault/location. First-write-wins; HOME_VAULT is explicitly promoted. HOME_VAULT retained under unlocked-only filtering. | Origin/visited registration sets these types. Production main marker icon and list grouping use this axis. |
| Dweller relation: `origin`, `visited` | `backend/app/core/enums.py:249`; `DwellerLocation` at `backend/app/models/world_location.py:112` | Unique `(dweller, location, relation)`; `is_unlocked=False` initially. Multiple relations can coexist for one place. | Drives dweller references, bio links, chat unlocking; does not assign archetype. |
| Archetype: 16 catalog keys below | `backend/app/data/places/place_groups.json:1`; `backend/app/utils/place_groups.py:24`; nullable `WorldLocation.group_key` | Data-defined string, not PG enum. Exact normalized seed-name lookup; unknown name → NULL. Clearable groups control dispatch/combat/rewards/cooldown. | Known bio names inherit the roster group. Catalog icons appear as legend entries and list/modal chips, not base SVG marker icons. |
| Presentation extras: `vault`, `expedition_site`, `explorer` | `frontend/src/modules/map/models/markerTypeMeta.ts:3`; `backend/app/schemas/wasteland_location.py:77` | NPC signals, site overlays and explorer tracking, not additional `LocationTypeEnum` values | Radioactive/star/walk icons; player vaults rendered as home/vault according to ownership. |
| Generated prototype kind: eight keys below | `frontend/src/modules/map/utils/atlasWorldgen.ts:155` | TS placement/road/scavenge algorithms; generated numeric IDs, tile positions, not registry UUIDs | Prototype canvas silhouettes. No AI schema/registry classification bridge. Production uses generated terrain/roads, not these generated location markers. |
| Expedition site: `red_rocket`, `super_duper_mart` | `backend/app/data/exploration/expedition_sites.json`; `backend/app/schemas/expedition.py:102` | String site IDs; authored rooms/reward vault; per-vault run/anti-farm gate | No canonical kind/group field. Uniform production star icon. `combat`, `choice`, `trap`, `finale` are **room node kinds**, not location kinds (`schemas/expedition.py:51`). |
| Terrain: `wasteland`, `forest`, `ruins`, `hills`, `water` | `backend/app/services/world_generation.py:31`; TS `atlasWorldgen.ts:107` | Geography/traversability vocabulary, not place classification | Terrain “ruins” does not imply registry `ruin` group. |

Canonical constraints: `backend/app/models/world_location.py:50–62`. API ordinary location shape exposes `type`, `group_key`, clear state and dweller links, not `kind`, `source` or `vault_number`: `backend/app/schemas/wasteland_location.py:29–74`. Frontend aliases generated OpenAPI schemas: `frontend/src/modules/map/models/map.ts:1–10`.

## 2. Actual gameplay archetypes and icons

Catalog inventory: **72 seed entries = 67 PLACE + 5 VAULT**. All 67 PLACE entries have a group; the five NPC VAULT entries are ungrouped. Counts below are static roster counts, not database populations. Source: `backend/app/data/places/seed_places.json`; definitions/icons/parameters: `backend/app/data/places/place_groups.json:2–177`.

For every grouped ordinary location, the actual main-map icon remains its per-vault type icon (or locked hint icon). The icon column below describes the catalog icon displayed by legend/list/detail, **not an asserted SVG marker mapping**.

| `group_key` | Seeds / example | Catalog icon | Risk | Clear / reclear hours / loot / base difficulty |
|---|---|---|---|---|
| `settlement` | 23 / Arefu, Big Town | `mdi:home-group` | low | No |
| `city` | 3 / Cambridge, Diamond City | `mdi:city` | medium | No |
| `gas_station` | 3 / Red Rocket, Red Rocket - Springvale | `mdi:gas-station` | low | Yes / 48 / low / 2 |
| `supermarket` | 2 / Super Duper Mart, Super Duper Mart - Quincy | `mdi:cart` | low | Yes / 48 / low / 2 |
| `factory` | 1 / Nuka-Cola Plant | `mdi:factory` | medium | Yes / 72 / medium / 3 |
| `metro` | 1 / Mass Pike Tunnel | `mdi:subway-variant` | medium | Yes / 72 / medium / 3 |
| `military` | 3 / Adams Air Force Base, Raven Rock | `mdi:shield-sword` | high | Yes / 96 / high / 4 |
| `brotherhood_outpost` | 1 / The Citadel | `mdi:shield` | high | Yes / 96 / high / 4 |
| `research` | 2 / The Institute, Big MT | `mdi:flask` | high | Yes / 96 / high / 4 |
| `power` | 1 / Poseidon Energy | `mdi:lightning-bolt` | medium | Yes / 72 / medium / 3 |
| `entertainment` | 3 / Galaxy News Radio, Nuka-World | `mdi:ferris-wheel` | low | Yes / 48 / low / 2 |
| `landmark` | 3 / Jefferson Memorial, National Archives | `mdi:bank` | medium | No |
| `vault_tec` | 5 / Vault 32, Vault 33 | `mdi:radioactive` | medium | Yes / 72 / medium / 3 |
| `ruin` | 4 / Concord, Jamaica Plain | `mdi:wall` | medium | Yes / 72 / medium / 3 |
| `region` | 11 / The Boneyard, Appalachia | `mdi:map` | high | No |
| `exclusion_zone` | 1 / The Quiet Zone | `mdi:fence` | high | Yes / 96 / high / 4 |
| NULL (not a group) | 5 NPC vault seeds / Vault 274, Vault 077; also arbitrary emergent names | No catalog icon | None | No group-derived clear state |

`vault_tec` is a PLACE archetype, not canonical VAULT: a named Vault 32 can be a clearable site while an NPC VAULT signal is ungrouped. Names alone do not determine canonical kind.

Catalog validation checks duplicate keys, label/description, clearability and valid reclear/difficulty/loot parameters, and seed group references (`backend/app/utils/place_groups.py:24–67`). It does not enforce a risk enum or require/validate an icon there; `PlaceGroupRead` requires string fields (`backend/app/schemas/wasteland_location.py:46`). Group lookups tolerate unknown keys as missing (`utils/place_groups.py:103`), resulting in no clear state rather than an automatic fallback archetype.

## 3. Backstory → identity → unlock → bio link

### Generated and curated bios

- Procedural bios choose an origin and rarity-scaled visited places from a 14-name pool, not the prototype eight-kind vocabulary (`backend/app/utils/dwellers.py:24–53`). Creation payload carries `_bio_places` (`utils/dwellers.py:166–188`). Named templates supply explicit metadata and bypass the visited cap because their bio is authoritative (`backend/app/services/dweller_service.py:130–157`; `utils/dwellers.py:199–244`).
- AI `DwellerBackstory` carries `bio`, one `origin_place` (≤64 characters), and up to five visited names; `ExtendedBio` carries up to three new names. **Neither carries kind/group/registry ID** (`backend/app/schemas/dweller_ai.py:8–40`). Dynamic agent instructions request specific named places, including towns/outposts/vaults, not selection from the registry or taxonomy (`backend/app/agents/dweller_agents.py:24–40,52–62`).
- Registry-backed prompt defaults make the same proper-name request (`backend/app/services/prompt_service.py:29–49`). AI generation retrieves versioned instructions; actual DB prompt overrides and actual model outputs were not inspected. Generated bio is committed before best-effort map registration; extension registers new visited names without a new origin (`backend/app/services/dweller_ai.py:154–181,244–257`).
- `register_bio_places` takes explicit origin when truthy, otherwise extracted origin; skips empty/Wasteland/the wasteland/unknown; truncates names to 64; skips visited names matching the origin; applies rarity cap except curated template path. It creates per-vault origin/visited states and locked dweller relations (`backend/app/services/map_service.py:115–254`; `backend/app/utils/places.py:13`). Retries/savepoints and actionable failure notification exist (`map_service.py:147–193,256–283`), despite older BIO_MAP_UNCOVERING documentation calling failure surfacing deferred.
- Legacy bio scanning is a different path: scans curated origin/visited role lists, not arbitrary semantic extraction (`backend/app/services/bio_place_backfill_service.py:27–81,100–111`; `backend/app/services/place_seed_service.py:30–39`).

### Registry matching and kind assignment

`normalize_place_name` casefolds, collapses whitespace and removes trailing `.`, `,`, `!` (`backend/app/utils/places.py:22–29`). Unique normalized name is the global merge key, shared by all vaults. It is **not** fuzzy matching, alias resolution, geographic disambiguation, or Vault-number parsing.

`get_or_create_location` reuses any matching existing registry row unchanged. A new row is explicitly PLACE, receives hash-derived schematic coordinates plus global collision nudge, defaults source to emergent, and gets a group only from exact normalized seed-name mapping (`backend/app/crud/world_location.py:50–112`; `backend/app/utils/place_groups.py:87–100`; `backend/app/models/world_location.py:33`). Thus an AI “Vault 999” is not automatically canonical VAULT. Home marker creation can later promote a matching `Vault NNN` row to VAULT and slot coordinates (`crud/world_location.py:114–174`). Different zero-padding/spelling is not normalized into the same name.

Seed loading inserts VAULT only when `entry['kind'] == 'vault'`, otherwise PLACE. Existing rows keep kind/name/coordinates/source; seed-owned descriptions refresh and group assignment backfills/updates any matching row (`backend/app/services/place_seed_service.py:47–91`). Consequently, a pre-existing emergent name matching a later VAULT seed is not automatically promoted by seed loading. Five seeded NPC vault numbers are reserved for player creation via `backend/app/utils/place_seed.py:33–36`.

### Unlock and UI identity

Bio registration defaults links to locked. Chat's shared post-message path unlocks all associated links after **three user messages**, not a particular archetype or AI place mention (`backend/app/services/chat/notifications.py:50–78`; `backend/app/services/chat/persistence.py:77`; `backend/app/crud/world_location.py:517–537`). Map identity unlock is any unlocked linked dweller within that vault (`backend/app/services/map_service.py:483–519`). Home is always known; NPC signals are exempt from hint styling (`frontend/src/modules/map/utils/visibility.ts:14–22`).

`useDwellerDetail` selects registry locations linked to the current dweller without filtering unlock, and `DwellerBio` linkifies those names to `/vault/{id}/map?place={locationId}` (`frontend/src/modules/dwellers/composables/useDwellerDetail.ts:222–227`; `frontend/src/modules/dwellers/components/DwellerBio.vue:116–175`). A readable bio and clickable name therefore do **not** imply unlocked map identity/actions. “Unknown Location” is a presentation gate, not secrecy of the response: the default map API includes locked records and their names (`backend/app/api/v1/endpoints/map.py:47–55`).

## 4. Features relying on these distinctions

| Feature | Actual dependency and evidence | Important boundary |
|---|---|---|
| Global registry / NPC signals | Canonical kind + source seed (`backend/app/crud/world_location.py:204–211`) | Signals have no raid action implemented by this map path; response text says raiding is future (`services/map_service.py:523–534`). Player vault overlay uses slot/ownership records separately (`map_service.py:538–549`). |
| Fog/known identity/list/selection | `type`, unlock and shared visibility helper (`frontend/src/modules/map/components/WorldMap.vue:85–103`; `utils/visibility.ts:14`) | Locked bio places remain hints. Per-vault type is provenance, not biome or difficulty. |
| Random exploration discovery | Prefix/suffix string generation (`backend/app/services/exploration/event_generator.py:72–83`; `data/exploration/discovery_names.json:50–83`) | Names include Factory/Gas Station/Power Station, but no corresponding group inference. |
| Discovery registration / Journal / bio | Same registry upsert; discovery state + unlocked visited link (`services/map_service.py:289–319`); persist location ID/coords and record visit (`services/exploration/event_service.py:217–254,306–315`) | Existing state remains its old type (`crud/world_location.py:293–314`); unlocking is independent. Event history, not one deduplicated place row, drives route trails (`map_service.py:335–367`). First bio visit is recorded idempotently (`services/bio_service.py:185–191`). |
| Scout | Coordinates/distance, free-roam lifecycle (`backend/app/services/exploration_service.py:283–310`) | No WorldLocation target or archetype dependency; does not select a prototype kind or guarantee a specific named site's discovery. |
| Targeted party dispatch | Vault-state existence, clearable group, elapsed clear window; Euclidean slot-origin distance (`services/exploration_service.py:362–395`) | No direct canonical-kind/type test; no explicit dweller-link unlock check in this service. UI locked-state gating is not equivalent to server enforcement. This is an audit finding, not a runtime exploit claim. |
| Clear/combat/rewards | Group base difficulty + tier (capped at 5), group loot table, per-tier/party reward scaling (`services/exploration/dispatch_resolution.py:50–117`) | Group `risk` is not the combat difficulty input; non-clearable/ungrouped points have no dispatch clear loop. |
| Reclear / escalation | Successful surviving party sets group reclear hours and increments count (`dispatch_resolution.py:120–143`); map derives availability (`services/map_service.py:373–391`); sweep notifies ready (`map_service.py:438–468`) | Per-vault state, not global exhaustion. Prototype kinds do not drive it. |
| Interactive expedition sites | Authored site ID, level, rooms/rewards; run gate by vault/site (`schemas/expedition.py:102–119`; `services/exploration/expedition.py:156–179,320–348`) | Separate anti-farm window/run status from registry reclear state. Sites are appended independently to map payload (`services/map_service.py:551–568`); no backstory registry linking. |

## 5. Production representation / icons

Source of presentation defaults: `frontend/src/modules/map/models/markerTypeMeta.ts:15–31`.

| Marker presentation | Main map icon | Notes |
|---|---|---|
| `home_vault` | `mdi:home-city` | Always known |
| `origin` | `mdi:flag` | Locked → `mdi:lock-question` / Unknown Location |
| `visited` | `mdi:eye` | Same locked override |
| `discovery` | `mdi:compass` | Unseen unlocked discovery pulses |
| `vault` | `mdi:radioactive` | Seed signal or other-player overlay; warning treatment |
| `expedition_site` | `mdi:map-marker-star` | Uniform shared star, regardless of site name |
| `explorer` | `mdi:walk` | Explicit WorldMap override, non-interactive; not in MARKER_TYPES legend/list table |
| Unknown presentation string | `mdi:map-marker`, raw label | Marker fallback only; list enumerates known MARKER_TYPES and therefore does not retain unknown groups |

`MapMarker` supports explicit icon/label overrides, then metadata defaults; locked override wins over icon (`components/MapMarker.vue:47–60`). It also has cleared badge/dimming and explorer rings (`MapMarker.vue:88–106,184–217`). Ordinary locations pass `loc.type` without a group icon override (`components/WorldMap.vue:283–296`). Expedition and explorer overrides are explicit (`WorldMap.vue:323–349`). Real player vaults use `is_mine ? home_vault : vault` and are non-interactive (`WorldMap.vue:311–320`); this does not distinguish the currently selected owned vault from all other owned vaults.

- **Legend:** relationship/status icons plus catalog icons for groups present in store locations (`frontend/src/modules/map/components/MapLegend.vue:17–20,27–52`). Presence is computed from store locations, not explicitly known-only records.
- **List:** groups by presentation type; each known location can have an additional archetype icon/label chip (`components/MarkerListPanel.vue:51–90,208–210`). Unknown presentation types are omitted by its MARKER_TYPES filter, unlike marker fallback. WorldMap supplies a known-only index (`components/WorldMap.vue:85–88`).
- **Detail modal:** looks up group metadata and displays archetype chip/lore; locked branch withholds normal identity/actions; dispatch is derived from clear state (`components/MarkerDetailModal.vue:38–42,115–119,238–256,334–399`).
- **API:** group catalog travels as `place_groups` alongside `group_key`; already sufficient for a future production archetype icon resolver without inventing another taxonomy (`backend/app/schemas/wasteland_location.py:39,46–57,133–141`).

## 6. Prototype / atlas taxonomy is not the registry taxonomy

`frontend/src/modules/map/utils/atlasWorldgen.ts:155–163` defines eight generated kinds. Its placement routines generate names/positions (`atlasWorldgen.ts:1000–1171`), road graph uses selected kinds (`atlasWorldgen.ts:785`), and supply caches are a separate local-scavenge guarantee overlay rather than density-count locations (`atlasWorldgen.ts:773–781,1866–1881`). These are generation/simulation effects, not production group-driven rewards.

Actual DEV canvas icon table: `frontend/src/core/views/map-prototype/MapPrototypeView.vue:435–456`.

| Generated kind | Actual prototype silhouette | Registry relationship verified in code/data |
|---|---|---|
| `settlement` | `drawHouses` | Same spelling as group, but separate generated identity |
| `red_rocket` | `drawRocket` | Named registry Red Rocket instances use `gas_station`; no kind bridge |
| `super_duper_mart` | `drawStore` | Named registry instances use `supermarket`; separate expedition site also shares this ID spelling |
| `abandoned_factory` | `drawFactory` | Registry catalog has `factory`; no generic/generated-name bridge |
| `radio_tower` | `drawTower` | No same-key registry group |
| `water_treatment` | `drawWaterDrop` | No same-key registry group |
| `raider_camp` | `drawSkull` | No same-key registry group |
| `supply_cache` | `drawSupplyCrate` | No same-key registry group; several generated cache name templates share this silhouette |
| Unknown kind | `drawUnknown` | Prototype fallback with underscore-to-space label, not production Iconify fallback |

Do not treat semantic similarity in this table as an implemented mapping. Conversely, most registry groups have no dedicated prototype silhouette. DEV production-data overlay fetches unlocked registry records separately, not classification into these kinds (`frontend/src/core/views/map-prototype/prodMap.ts:23–43`).

Production `AtlasTerrain` calls the TS generator and draws its terrain/roads, **not its location silhouettes** (`frontend/src/modules/map/components/AtlasTerrain.vue:12–36,48–64`). Thus generated archetypes can influence the decorative road graph without becoming discoverable/clearable registry sites. Python `GeneratedWorld` and snapshot response currently contain terrain/slots only, no generated place-kind inventory (`backend/app/services/world_generation.py:115–124`; `backend/app/schemas/world_snapshot.py:16–30`). Existing snapshot adoption issues cover this geography split; an icon-only change must not imply backend travel or place generation adoption.

## 7. Drift/default/migration findings and bounded follow-ups

| Finding | Impact / recommended follow-up (not implemented here) |
|---|---|
| Novel AI/discovery names have NULL groups | A “factory” can be visible yet non-clearable. Decide whether emergent places should remain narrative-only or receive validated explicit archetypes. Reuse group catalog; avoid guessing taxonomy from unrestricted names. |
| Archetype icons already available but absent on SVG markers | Define explicit precedence: identity archetype icon vs provenance/status badges, with locked override and known fallback. Reuse backend group data and existing prototype artwork only after agreeing mappings; keep legend/list/modal consistent. |
| First-write state type versus evolving relations | Discovery can unlock an origin without changing marker icon or exploration link on state. Document provenance semantics; use event history for journeys, not type mutation as a substitute. |
| Similar names across three identity systems | Registry/expedition/prototype content can coexist independently (including exact Super Duper Mart display name). Any unification needs stable IDs, coordinate ownership and progress compatibility, not name-based visual merging. |
| Seed kind fallback and limited validation | Loader validates duplicate normalized names, not a strict kind vocabulary (`utils/place_seed.py:19–30`); seed service treats every non-`vault` value as PLACE. A kind typo can silently classify incorrectly. Existing rows do not get seed kind promotion. |
| Normalization is intentionally narrow | Case/space/trailing punctuation merge; spelling, aliases, zero-padding and variants do not. 64-character truncation at registration can conflate long names. No geographic uniqueness dimension. Clarify authoring/alias policy before broadening matching. |
| Unknown group / presentation behavior differs | Missing group → no clear state/chip; unknown presentation → generic SVG marker but omitted list category. Future taxonomy additions need consistent fallbacks across consumers. |
| UI unlock gate is not dispatch authorization | Service checks vault state/group/cooldown but not unlocked links. If intended contract requires discovery before clearing, enforce it at the service boundary in a separately test-backed change. Locked data is returned by default, so do not describe UI hiding as data confidentiality. |
| Canonical descriptions versus per-vault detail | Seeds store canonical description, but ordinary map/detail projects `state.description` rather than `location.description` (`services/map_service.py:428,512`). Group lore is another field. Review fallback before expecting seeded place-specific lore in every detail panel. |
| Historical docs/schema comments lag | BIO_MAP_UNCOVERING still references retired WastelandLocation/failure surfacing; VaultMarkerRead says “never persisted” although NPC signals project persisted registry rows; model phase-1 comments predate rewiring. Code, not these statements, was used as audit authority. |

**Migration boundaries:** `placekind`, `locationtypeenum`, and `dwellerlocationrelationenum` are PostgreSQL enum contracts (stored labels are uppercase member names, wire values lowercase). Snapshot labels are recorded at `backend/app/tests/test_db/test_enum_drift.py:47,64,97`; registry creation migration is `backend/app/alembic/versions/2026_09_12_0001-b7e4c1a9f2d3_add_world_place_registry.py:61–90`. Adding canonical kinds requires manual PG enum migration **and** review of the kind/vault-number check constraint and partial unique index, not just Python edits. Enum changes must update the drift snapshot per project rules. Group additions are data-defined and do not require enum migration, but persistent assignments need seed refresh/backfill and renamed keys need explicit compatibility handling. Do not replace “unpopulated” NULL groups with an arbitrary legal archetype default.

**Suggested scope for future taxonomy/icon work:** agree vocabulary and mappings first; reuse `place_groups`/`group_key`; preserve canonical UUIDs, per-vault unlock/clear history and expedition IDs; then wire one production icon resolution policy across map/list/legend/detail. Handle generated-world placement and interactive-site unification as separate contracts. Existing `WORLD_EVOLUTION_ISSUES.md` already tracks later presentation and snapshot/travel sequencing; this audit adds evidence without modifying that backlog.

## Limitations

No database population/seed execution/prompt override was verified. JSON counts describe the checked-in roster only. No browser rendering, network payload, migration application, concurrency behavior, exploit, AI output quality, or reward balance was runtime validated. No claim that Python/TS generated geography is equivalent. No test removal or validation runs; existing regression tests were referenced only as contract evidence. This document is the sole file created by this audit.
