# Asset Pipeline & Provenance Convention (Issue #817)

**Status:** Decision record, **pending maintainer ratification**
**Scope:** One manifest/provenance convention for generated assets
**Parent of:** #818 (arena actor layer stack), #819 (room detail scenes)

This document records the chosen asset pipeline and the provenance convention
that ships with it, plus the comparison evidence a maintainer needs to ratify
the choice. Ratification matters because #817 commits the repo to a generation
pipeline and its usage/licensing terms. Nothing here is marketing prose; every
number is measured or explicitly labeled as an estimate.

---

## 1. Purpose & Scope

Generated assets need one place that says what they are, how they were made,
and whether they are safe to ship. The asset manifest is that place: a curated
registry of AI-generated assets with provenance metadata, validated against the
files on disk. It is the single convention for every generated asset in the
game, and it is the parent of two follow-ups:

- **#818** : arena actor layer stack (equipment swaps change actor layers).
- **#819** : room detail scenes (camera, floor baseline, actor slots).

The ancestor spec is `docs/backend/AI_LAYER_PLAN.md` (Plan 5, pre-generation
shift, around line 222): offline batch generation, a human curation gate, and a
versioned manifest mapping asset key, archetype, generation seed, source, and
review status. This document is the concrete implementation of that plan for
images.

---

## 2. Asset Brief

Every generated asset is authored against one style reference: **Fallout
Shelter flat cel-shaded art, tuned to be CRT-friendly** (the game UI is a
terminal CRT theme). The brief per role:

| Role | Aspect ratio | Camera | Resolution | Alpha / tiling | Intended UI size |
|---|---|---|---|---|---|
| `room_detail_scene` | 3:2 | side-on 2.5D | 1536×1024 | no alpha, no tiling | room detail modal, full-bleed |
| `arena_actor` | 2:3 | full-body, front-facing | 1024×1536 | alpha, no tiling | actor canvas 1024×1536 |
| `arena_equipment` | 1:1 | layer-only, transparent | 1024×1024 | alpha, no tiling | composited onto actor canvas |
| `room_grid` | 1:1 | top-down-ish sprite | wiki-derived | no alpha, no tiling | grid cell |
| `weapon_icon` / `outfit_icon` / `junk_icon` / `pet_icon` | 1:1 | icon | 1024×1024 | alpha, no tiling | inventory / equip slots |
| `dweller_portrait` | 1:1 | head-and-shoulders | 1024×1024 | no alpha, no tiling | portrait card |

Format is PNG everywhere. Palette follows the Fallout Shelter flat cel-shaded
look; equipment and actor layers carry alpha so they composite onto the actor
canvas, scenes and portraits do not.

### The four #817 outputs

| Output | Produced | Deferred |
|---|---|---|
| Empty Arena (room detail scene) | ✅ `room_detail_scene.arena`, 1536×1024, via `gpt-image-2.5-flare` | |
| Full-body dweller (arena actor base) | ✅ `arena_actor.base`, 1024×1536, via `gpt-image-2.5-flare` | |
| Rocky wasteland scene | | ⏸️ deferred |
| Repeatable rock/ground tile | | ⏸️ deferred |

Two equipment layers were also produced via `gpt-image-2.5-flare` as part of
the actor pipeline: `arena_equipment.outfit_overcoat` and
`arena_equipment.weapon_rifle`, both 1024×1024 with alpha. The wasteland scene
and the repeatable tile are deferred until the pipeline is ratified and the
ComfyUI arm is evaluated.

### Prototype asset locations

The Arena prototype assets live in `/static/poc_v25/`:

| File | Role | Size |
|---|---|---|
| `arena_empty.png` | room detail scene | 1536×1024 |
| `pose_guard.png` | arena actor base | 1024×1536 |
| `outfit_layer_overcoat.png` | equipment layer | 1024×1024 |
| `weapon_layer_rifle.png` | equipment layer | 1024×1024 |

The `gpt-image-1` assets (`/static/actor_poc/*`,
`/static/room_images/arena_empty_poc.png`) remain as the v1 comparison set.

---

## 3. Workflow Comparison

Three candidate workflows were considered. Two were actually run; the third is
a blocked arm.

| Criterion | `gpt-image-1` | `gpt-image-2.5-flare` | ComfyUI (local) |
|---|---|---|---|
| Art quality | baseline | better (adopted) | not evaluated |
| Cost per 4-asset set | ≈ $0.83 | ≈ $0.19 | $0 (local, RTX 3080) |
| Deterministic seed | none (`seed: null`) | none (`seed: null`) | yes (expected) |
| Runs offline | no | no | yes |
| Status | scheduled for removal 2026-10-23 | **adopted** | **blocked, not evaluated** |

**ComfyUI is a blocked arm, not a result.** There is no local ComfyUI in this
environment, so no ComfyUI generations, seeds, or prices exist to record. The
arm is documented so it can be run on the RTX 3080 later; the ancestor spec
(`docs/backend/AI_LAYER_PLAN.md`) anticipated exactly this: local batch
generation with seeds, curated before shipping. Until that arm runs, the
OpenAI comparison stands alone.

**Decision: `gpt-image-2.5-flare` (raw) is adopted for the Arena prototype
assets.** Raw 2.5 output is more rendered and saturated than `gpt-image-1`;
that was explicitly accepted as good enough for the prototype. It also costs
less than `gpt-image-1`, which is scheduled for removal on 2026-10-23. The
choice is pending maintainer ratification because it commits the repo to a
generation pipeline and its usage/licensing terms.

**`gpt-image-2` is not viable for layered assets.** The API rejects
`background="transparent"` for it (`400: Transparent background is not
supported for this model`), so it cannot produce actor or equipment layers at
all, only opaque scenes.

**Style-match fallback (recorded, not chosen).** `gpt-image-2.5-flare` in edit
mode (`images.edit`) with a `gpt-image-1` asset as the reference image
reproduces the flat-vector Fallout Shelter look closely: bold outlines, flat
cel fills, muted palette, no letterbox. Use this path if raw 2.5's style is
later rejected.

---

## 4. Measured Evidence

### Official OpenAI pricing (per 1M tokens)

| Model | text-in | image-in | image-out |
|---|---|---|---|
| gpt-image-1 | $5 | $10 | **$40** |
| gpt-image-1.5 | $5 | $8 | $32 |
| gpt-image-2 | $2.50 | $4 | $15 |
| gpt-image-2.5 (flare & sunburst) | $5 | $8 | **$30** |

### Measured per-image cost (actual token usage)

**`gpt-image-1`:**

| Asset | Size | Tokens | Cost |
|---|---|---|---|
| Arena | 1536×1024 | 6,208 | $0.249 |
| Actor | 1024×1536 | 6,240 | $0.250 |
| Layer (outfit / weapon) | 1024×1024 | 4,160 | $0.167 each |

4-asset set ≈ **$0.83**.

**`gpt-image-2.5-flare` (at $30/M output):**

| Asset | Size | Tokens | Cost |
|---|---|---|---|
| Square | 1024×1024 | 1,756 | **$0.053** |
| Pose | 1024×1536 | 1,372 | **$0.041** each |
| Arena | 1536×1024 | 1,372 | **$0.041** |

4-asset set ≈ **$0.19**. The arena figure is now measured, not scaled; the
measured 2.5 set is cheaper than the earlier scaled estimate.

**Other facts:** the Batch API is 50% off. Text input is negligible, roughly
$0.0003 per image. `gpt-image-2.5` does not expose a deterministic seed, so
manifest records carry `seed: null` and outputs are non-reproducible.

---

## 5. Manifest Convention

### Location

- Registry: `backend/app/data/assets/manifest.json`
- Loader: `backend/app/utils/asset_manifest.py`
- Enums: `AssetRole` and `ReviewStatus` in `backend/app/core/enums.py`

### Fields

Each record carries: `key`, `role`, `catalog_key`, `source`, `workflow`,
`model`, `prompt_ref`, `seed`, `path`, `width`, `height`, `format`,
`has_alpha`, `tiling`, `review_status`, `ui_placement`, plus optional `scene`
(room detail geometry) and `actor` (layer stack geometry).

`AssetRole` values: `room_grid`, `room_detail_scene`, `weapon_icon`,
`outfit_icon`, `junk_icon`, `pet_icon`, `dweller_portrait`, `arena_actor`,
`arena_equipment`.

`ReviewStatus` values: `draft`, `reviewed`, `approved`, `rejected`,
`deprecated`. Only `reviewed` and `approved` records resolve to URLs.

### The overlay rule

The manifest is a **provenance/validation overlay, NOT a replacement for the
six name→file resolvers** in `backend/app/utils/`:

- `room_assets.py`
- `actor_assets.py`
- `outfit_assets.py`
- `junk_assets.py`
- `pet_assets.py`
- `legendary_dweller_assets.py`

Those resolvers encode fallback semantics the manifest cannot express (tier and
segment fallbacks for rooms, portrait fallback for non-adult dwellers). The
resolvers consult the manifest first via `manifest_url()` and fall through to
their existing logic when nothing is registered. `actor_assets.py` builds the
arena layer stack entirely from manifest records; every layer path comes from
the manifest, never hardcoded in Python.

### Prototype geometry (Arena)

The Arena manifest scene record was re-authored to match the 2.5 arena:
`floor_baseline_y: 625`, with actor slots at `x 522` and `x 1014` (both
`y 625`). The weapon equipment layer anchor was tuned for the guard pose
(`anchor_x 205`, `anchor_y 400`). The arena itself was re-rolled with an
explicit "no border, no frame, no letterbox, no dark band" instruction to
remove the band the first 2.5 arena had.

### Validation

`backend/app/tests/test_utils/test_asset_manifest.py` validates the registry
with Pillow, comparing declared fields against decoded files. Named failure
modes:

- `AssetMissing` : file not on disk
- `AssetEncodingMismatch` : declared format differs from decoded format
- `AssetDimensionMismatch` : declared size differs from decoded size
- `AssetAlphaMismatch` : declared `has_alpha` differs from decoded mode
- `AssetExtensionMismatch` : file extension differs from decoded format

The strict per-file extension check applies only to manifest-registered assets
(see Finding 1). A separate slow test sweeps every static image and asserts it
decodes and is a supported web format.

---

## 6. Findings & Known Issues

### Finding 1 : legacy asset encoding drift

619 of 624 existing static wiki assets are **WebP payloads stored under `.png`
filenames**. The strict per-file extension check is therefore enforced only on
manifest-registered assets; the full-static sweep asserts decodability plus a
supported format instead. Recommended follow-up: rename the legacy files to
`.webp` or document the drift explicitly.

### Finding 2 : layer alignment

Text-to-image cannot guarantee rig-aligned equipment. Equipment layers must be
authored with explicit per-layer anchors (`anchor_x` / `anchor_y` / `width` /
`height` in actor-canvas pixels), and the weapon anchor must be tuned per pose.
A T-pose / arms-down base needs a different weapon anchor than a guard pose.
For the prototype the weapon anchor was tuned to `anchor_x 205`, `anchor_y 400`
for the guard pose. The manifest's `actor.layers` geometry is the mechanism for
this.

### Finding 3 : pose

Four poses were generated: `idle`, `guard`, `ready`, `relaxed`. `guard` was
selected as the arena-fighter idle. All four are non-T-pose.

### Portrait invariant

Equipment swaps change actor layers and **never regenerate portraits**.
Portraits are `{dweller_id}.png` and are only rewritten by an explicit
`generate_photo(force=True)` call. This is enforced by a backend regression
test.

---

## 7. Deferred Work

- **ComfyUI arm** : run on the RTX 3080, then compare against the OpenAI
  numbers above. No results exist yet.
- **Full manifest coverage** : register the remaining roles (icons, portraits,
  room grid) as assets are generated.
- **Sprite-sheet animation** : the manifest has no animation concept yet.
- **Per-dweller actor appearance persistence** : actor appearance is currently
  derived from age group plus equipped items; persisting per-dweller appearance
  is future work.
- **Pet asset wiring** : `pet_assets.py` exists but no pet assets are
  registered.

---

## References

- `backend/app/utils/asset_manifest.py` : loader and validation overlay
- `backend/app/data/assets/manifest.json` : the registry
- `backend/app/utils/actor_assets.py` : arena actor layer stack (#818)
- `backend/app/utils/room_assets.py` : room grid + detail scene resolution (#819)
- `backend/app/schemas/room.py` : `RoomDetailScene`, `RoomDetailActorSlot`
- `backend/app/schemas/arena.py` : `ArenaActor`, `ArenaActorLayer`
- `backend/app/tests/test_utils/test_asset_manifest.py` : validation tests
- `docs/backend/AI_LAYER_PLAN.md` : ancestor spec, Plan 5 (~line 222)
