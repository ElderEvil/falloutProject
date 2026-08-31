# Boosted Vault Diversity + Configurable Start + Onboarding — Delivery Plan

> **Status:** Plan (not started) — `master` at `2.67.0`. ROADMAP pruned 2026-08-31 (arena / AI-settings / breeding-debt all shipped). No active branch.
>
> **Owners:** backend `vault_service` + `game_config` + `utils/dwellers` + `crud/dweller`; frontend `HomeView` + `vault` store + `App` shell + `VaultView` + `SidePanel`/`OverseerBriefing`.
>
> **Docs:** `docs/ROADMAP.md` (Boosted Vault Rarity & Race/Faction Diversity + Onboarding fragment), `docs/backend/AI_LAYER_PLAN.md`, `docs/features/BIO_MAP_UNCOVERING.md`, `frontend/src/assets/tailwind.css` + `docs/frontend/STYLEGUIDE.md` for tokens.

---

## TL;DR

**What you'll get:** Boosted vaults feel special (boosted rarity 12% RARE vs 4% standard, see §1) and vaults stop being 100 % human (70/15/10/5 human/ghoul/synth/super-mutant via configurable `race_weights`), vault start becomes tunable via `VaultStartConfig` without a new preset enum, and first-session players get a 9-step **explanatory** tour (links + briefing, not a build-it-yourself tutorial) that is dismissable and remembered per-user.

**Why this approach:** One choke-point fix (`utils/dwellers.py:119`) plus a `VaultStartConfig` in `game_config.py` covers both diversity and start configurability without a migration; onboarding is greenfield and follows the single established "first-time dismissable" pattern (`useVersionDetection.ts` / changelog modal) mounted in `App.vue` and triggered in `VaultView.loadVaultData`. Preset `diverse` is **out of scope this slice** — diversity is global, and `boosted: bool` stays the only start toggle (see point 2 below).

**What it will NOT do:** No race/faction gameplay modifiers (thats `Race & Faction Gameplay Mechanics`, separate), no DB columns for race/faction, no live multiplayer, no analytics pipeline, no tour library, no new `preset` enum this slice.

**Effort:** Medium (3 streams, parallel) | **Risk:** Medium (touches `initiate_vault`, generator determinism, and a new UI surface)
**Decisions — resolved for this slice (see §6):** `race_weights` 70/15/10/5 with strict validation; recycling preserves race; onboarding is explanatory with hybrid `preferences.onboarding` merge; `boosted: bool` stays, `VaultStartConfig` is internal tuning only.

Your next move: approve the 3 decisions above, then `ulw-plan`/`start-work` per stream.

---

## 1. Scope

### Must have (P0 for the slice)

**Stream A — Boosted Vault Diversity (P1 Low-Hanging Fruit)**

- Replace hardcoded `{"race":"human","faction":"vault_dweller"}` at `backend/app/utils/dwellers.py:119` with a seeded roll: race from `game_config.dweller.get_race_weights()`, faction from `faction_restrictions[race]` (`options/factions.py:26`) with an explicit **faction-weighting policy** (see below), `state_of_being` for non-humans from `STATE_OF_BEING_OPTIONS` (`options/races.py:48`). Use the existing `rng: Random` so `seed` determinism is preserved.
- Add `race_weights: dict[str,int]` to `DwellerConfig` (`backend/app/core/game_config.py:652`) with defaults `human:70 ghoul:15 synth:10 super_mutant:5`, **strictly validated**: reject unknown keys, reject missing `RaceOption` keys, require integer >=0, require positive total, normalize enum strings (`"Super Mutant"` → `super_mutant`) — stronger than `BioConfig`'s non-negative check. Add `get_race_weights()` accessor like `IncidentConfig.get_spawn_weights()` (`game_config.py:135`) that returns a normalized `{str: float}` or validated `dict[str,int]` copy and raises `ValueError` on bad config before `rng.choices` can fail. Env: `DWELLER_RACE_WEIGHTS`.
- **P0 rarity boost (decided, not optional):** add `DwellerConfig.boosted_rare_chance: float = 0.12` (standard seeding rare 0.04 via new `DwellerConfig.standard_rare_chance` or reuse `RadioConfig.rare_chance`; choose one source and document it). Vault seeding at `vault_service.py:219/244/260/276/294` currently hardcodes `RarityEnum.COMMON`; change it to roll `RARE` at `standard_rare_chance` (default 0.04) for standard and `boosted_rare_chance` (0.12) for boosted — gate on `is_boosted`. Radio keeps `game_config.radio.rare_chance`. LG remains legendary-template only.
- **Faction-weighting policy (explicit, not uniform):** humans must remain lore-coherent — `vault_dweller` dominant. Define `faction_weights: dict[FactionOption, int]` or a simple rule: for `human`, `vault_dweller: 70, others: 30` split weighted by lore (e.g. `brotherhood:3, ncr:3, raiders:2, …`); for non-humans, use `faction_restrictions[race]` uniformly or with a tuned map. Document the table in `game_config.py` and `options/factions.py` docstring. Do not give humans uniform faction distribution.
- Respect the override path: `DwellerCreateCommonOverride.visual_attributes` (`schemas/dweller.py:142`) → `crud/dweller.create_random` (`crud/dweller.py:204`) already wins over the generator, and `DwellerVisualAttributes` validator (`schemas/dweller.py:109`) rejects invalid race/faction pairs — generator must emit valid pairs.
- Radio recruitment (`radio_service.py:204-211`) inherits diversity automatically because it goes through `crud.create_random`; **recycling preserves race**: preserved dwellers (`radio_service.py:170`) keep their original race (do not re-roll), documented in test — this keeps recycling semantics and avoids erasing recycled identity.

**Stream B — Configurable Vault Start (intersects A)**

- Introduce `VaultStartConfig` in `game_config.py` (env prefix `VAULT_START_`) covering initial resource % (today `//2` at `vault_service.py:640`), stimpaks/radaway `min(5, cap)` at `vault_service.py:657`, dweller counts, legendary roster, room set, objective counts (today hardcoded in `_prepare_initial_rooms:83`, `_create_initial_dwellers:194`, `_create_boosted_legendary_dwellers:467`, `_assign_initial_objectives:518`). No preset enumeration this slice — `boosted: bool` stays the only start toggle (see §6). `VaultStartConfig` is internal tuning only; `diverse` is not a preset — diversity is global (both standard and boosted get 70/15/10/5 via `race_weights`).
- Keep `VaultNumber` (`schemas/vault.py:19`) as `{number, boosted}` only this slice — do **not** add `preset`/`start_profile`. `POST /vaults/initiate` (`endpoints/vault.py:146` `is_boosted = vault_data.boosted or user.is_superuser`) remains unchanged except for consuming `VaultStartConfig` values inside the service. No API contract change this slice, so no `types:generate` churn and no `preset`→`is_boosted` mapping to spec.
- Frontend: `HomeView.vue:24` `boostedStart` checkbox stays, but copy may hint at the new start tuning ("standard 4% RARE / boosted 12% RARE" etc if the rarity boost lands). No preset selector this slice; store `stores/vault.ts:102` and Zod `schemas/vault.ts:16` remain `{number, boosted}` until a follow-up explicitly defines every preset's rooms/counts/rarity/race-weights mapping.

**Stream C — Onboarding (greenfield, 9 steps per ROADMAP) — explanatory, not interactive tutorial**

- Steps 1–9 verbatim from `ROADMAP.md:513` plus soft hooks, **reinterpreted for the pre-seeded vault** (both standard and boosted already have production rooms and assigned dwellers, boosted has the full room set). Onboarding is **explanatory with links**, not an interactive "build/assign your first power plant" tutorial that requires an empty vault:
  1. Welcome & goal  2. Power — observe the existing power room and why power gates everything (link to power room)  3. Production chain — walk through water/food already running and what happens on depletion (link to bars)  4. Assigning dwellers — show SPECIAL→rooms mapping and link to `DwellerGrid`/`auto-assign` tools (do not require the user to perform the assign)  5. Vault expansion — point to building/elevators/merging when ready (link to build menu)  6. Population basics  7. Incidents & defense  8. Wasteland  9. Progression loop (objectives/quests/training → `SidePanel` links)  → soft hooks: `OverseerBriefing` attention items replace tutorial after dismissal. A genuinely minimal start profile (empty vault) is **out of scope this slice** — if later desired, it becomes a separate `VaultStartConfig` preset with its own room/dweller table.
- Composable `useOnboarding` modeled on `useVersionDetection.ts` (localStorage first-time detection + conditional overlay). Mount overlay in `App.vue` alongside `ChangelogModal`/`GaryOverlay`.
- Trigger in `VaultView.loadVaultData` (`VaultView.vue:158`) after `isLoading` resolves and `currentVault` populated, and in `HomeView.createVault` (`HomeView.vue:41`) for the welcome step. Handle Boosted Start vaults specially (23 rooms/25 dwellers already built — steps 2/4 use the explanatory variant described above, no branching into required actions).
- Persistence — hybrid with **namespaced merge, not replace**: localStorage instant read `useLocalStorage('onboarding_completed_${userId}|${vaultId}')` plus server durability via a narrowly scoped write that **read–merge–writes** `UserProfile.preferences` JSONB (`models/user_profile.py:17`) under the single key `preferences.onboarding` (e.g. `{ completed_steps, dismissed_at, vault_id }`). The existing `PUT /api/v1/users/me/profile` (`endpoints/user.py:180`) replaces the whole `preferences` object — a stale onboarding `PUT` would erase `preferences.theme`. Implement either (a) a scoped `PATCH /api/v1/users/me/preferences/onboarding` (preferred) or (b) a service helper `merge_onboarding_preferences(user_id, patch)` that `SELECT … FOR UPDATE` / JSONB merge `preferences || jsonb_build_object('onboarding', patch)` so theme and onboarding never clobber each other. LocalStorage remains source of truth for the session; server is cross-device durability.
- No tour library (none installed — `package.json` has no driver.js/shepherd), no analytics system (no posthog/segment/mixpanel; steps must be driven by vault game state: `vaultStore.loadedVaults` rooms/dwellers/resources, not events). Use shared primitives (`UButton`/`UCard`/`UModal`, `.terminal-glow`, tokens from `tailwind.css`) — no inline styles, no new deps unless justified.

### Must NOT have (guardrails)

- No `race`/`faction` columns on `Dweller` or `Vault` — stays `visual_attributes` JSONB.
- No gameplay modifiers/perks (thats `Race & Faction Gameplay Mechanics`) — this plan only diversifies who exists.
- No PG enum for `preset` (use `str` + validator); if a PG enum is ever added, the mandatory manual `op.execute()` migration + `PG_ENUM_LABELS_SNAPSHOT` update in `test_enum_drift.py` applies (AGENTS.md).
- No `as any` / `@ts-ignore` / `@ts-expect-error`, no nested try-except, no `.dockerignore` or version bumps (Semantic Release owns versions).
- No new `preset`/`start_profile` API field this slice — `boosted: bool` stays the only start input (see §1 Stream B); a future `preset` enum needs an explicit per-preset mapping table before it ships.
- Net-LOC rule (v2.35+): every stream must be net-negative or neutral in `backend/app` + `frontend/src` source LOC (consolidate the 3 scattered bio-adjacent template pools if touched; don't duplicate `faction_restrictions`).

---

## 2. Verification strategy — test-first (mandatory per AGENTS.md Bug Fix Workflow)

- **Bug-fix workflow (mandatory):** write a failing test reproducing the bug/requirement first, then fix and prove it by running that test (and the relevant suite). This repo's CI gate is `uv run prek run` (see `.github/workflows/backend-ci.yml`); every stream below starts with a red test.
- **Backend gates (from `AGENTS.md`):** `uv run ruff check . --fix` + `uv run ruff format .` (120-col) + `uv run pytest app/tests -q` (≈4.5 min) — run the named subsets per stream. CI gate: `uv run prek run`.
- **Frontend gates:** `pnpm run lint && pnpm run typecheck` + `pnpm run test:run` (CI-equiv). No `pnpm run types:generate` this slice (no API contract change — `boosted: bool` stays).
- **Evidence dir:** `.omo/evidence/<goal>/<attempt>/` — store `pytest -q` tail, `ruff` output, `vitest` output.

### Test-first order per stream (red → green)

- **A Diversity:** red test `create_random_common_dweller` produces non-human races (`test_crud/test_dweller.py:67` hard-assert `race=="human"` must be rewritten to accept the new distribution), plus seeded determinism and faction-validity tests in `test_utils/test_dwellers.py`, and a radio `race_weights` mirroring test (`test_radio_service.py:549`). Fix the generator only after the tests are red.
- **B Start config:** red test that `VaultStartConfig` values are consumed (resource % at `vault_service.py:640` and stimpaks `657` come from config, not literals) and that `initiate_vault` with `is_boosted` yields the new rare-chance boost. No API-preset test this slice.
- **C Onboarding:** red test for `useOnboarding` (first-time detection, dismiss, per-vault key, merge-safe profile write) — Vitest — before the composable lands.

### Evidence per stream

| Stream | Key test targets (test-first: red before green) | What proves it |
|---|---|---|
| A Diversity | `test_crud/test_dweller.py:67` `test_create_random_common_dweller` — rewrite hard-assert `race=="human"` at 82/94 to `race in RaceOption` + `faction in faction_restrictions[race]` (red first); add seeded determinism test (same seed→same race/faction/state_of_being) + distribution test in `test_utils/test_dwellers.py` (e.g. 1000 seeded draws within tolerance, positive-total/unknown-key validator tests); add radio `race_weights` mirroring test (`test_radio_service.py:549`) | Non-human races appear (~15/10/5), determinism holds, validator rejects bad config before `rng.choices`, and every pair validates against `schemas/dweller.py:109` |
| B Start config | `test_services/test_vault_service.py` `TestCreateInitialDwellers:418` + `TestInitiateVault:1206` — add config-consumption tests (resource % and stimpaks come from `VaultStartConfig`, not literals) and the new rare-chance boost (`is_boosted` yields 0.12 vs 0.04) | `initiate_vault` honors `VaultStartConfig`; no API contract change this slice (`{number, boosted}` only) |
| C Onboarding | New `frontend/tests/unit/composables/useOnboarding.test.ts` (first-time, dismiss, per-vault key, **merge-safe** `preferences.onboarding` write — stale theme must survive) + mount tests for `App.vue` overlay | Overlay shows on first vault visit as explanatory links, skippable/dismissable, not re-shown, and `PUT` does not clobber `preferences.theme` |

---

## 3. Execution strategy

### Parallel waves — updated after review (preset deferred, onboarding explanatory)

- **Wave 0 (plan only, this doc):** done — patched 2026-08-31 to resolve 7 contradictions (explanatory onboarding, no new preset enum, rarity P0, test-first, merge-safe persistence, strict race_weights, faction weighting).
- **Wave 1 (parallel, 3 streams):**
  - `A` — Diversity generator + `game_config` race_weights + faction weighting + strict validation + rarity boost (1 deep agent, backend-only)
  - `B1` — `VaultStartConfig` backend (resource % + stimpaks + rare-chance boost) without new API field (`boosted: bool` stays) (1 deep agent, backend)
  - `C1` — `useOnboarding` composable (explanatory variant) + `App.vue` mount + `VaultView`/`HomeView` triggers + **namespaced merge-safe** `preferences.onboarding` hybrid persistence (1 deep agent, frontend + thin backend `PATCH`/service helper)
- **Wave 2 (small, parallel):**
  - `B2` — HomeView copy hints for the tuned start values (rare 4%→12% etc) — no preset selector this slice (depends on B1; `types:generate` not needed this slice)
  - `C2` — Onboarding step content (9 explanatory steps) + `SidePanel` links (step 9) + `OverseerBriefing` soft-hook handoff, plus Tailwind token alignment (depends on C1)

### Dependency matrix

| Todo | Depends on | Blocks | Can parallelize with |
|---|---|---|---|
| A — race/faction generator + faction weights | — | — | B1, C1 |
| B1 — VaultStartConfig + rarity boost (no API field) | — | B2 | A, C1 |
| B2 — HomeView copy hints (no selector this slice) | B1 | — | C2 |
| C1 — onboarding shell + namespaced merge persistence | — | C2 | A, B1 |
| C2 — onboarding steps + polish | C1 | — | B2 |

### File map (where the work lives)

```
backend/app/utils/dwellers.py:79            ← race/faction roll (replace line 119)
backend/app/crud/dweller.py:182             ← override merge (already handles visual_attributes)
backend/app/core/game_config.py:652         ← DwellerConfig.race_weights + VaultStartConfig
backend/app/schemas/dweller.py:59,135       ← DwellerVisualAttributes + DwellerCreateCommonOverride
backend/app/options/races.py:6,48           ← RaceOption + STATE_OF_BEING_OPTIONS
backend/app/options/factions.py:8,26        ← FactionOption + faction_restrictions
backend/app/services/vault_service.py:83,194,467,600 ← rooms/dwellers/legendaries/initiate_vault
backend/app/services/radio_service.py:140   ← inherits diversity via crud.create_random; recycling at 170
backend/app/api/v1/endpoints/vault.py:134   ← POST /vaults/initiate (is_boosted at 146, unchanged this slice)
backend/app/schemas/vault.py:19             ← VaultNumber ({number, boosted} — no new field this slice)
backend/app/models/user_profile.py:17       ← preferences JSONB (onboarding hybrid)
backend/app/api/v1/endpoints/user.py:180    ← profile PUT + needed PATCH/merge helper for preferences.onboarding
frontend/src/modules/vault/views/HomeView.vue:24,127 ← creation UI (boostedStart stays; copy may hint at tuned values)
frontend/src/modules/vault/stores/vault.ts:102 ← createVault(number, boosted) — unchanged this slice
frontend/src/modules/vault/schemas/vault.ts:8   ← Zod vaultNumberSchema — unchanged this slice
frontend/src/modules/vault/views/VaultView.vue:158 ← loadVaultData trigger
frontend/src/App.vue                          ← global overlay mount (ChangelogModal pattern)
frontend/src/router/index.ts:57               ← beforeEach guard (not the onboarding hook — VaultView is)
frontend/src/core/composables/useVersionDetection.ts ← pattern to copy
frontend/src/modules/vault/components/shell/OverseerBriefing.vue ← soft-hook target
frontend/src/core/components/common/SidePanel.vue  ← step 9 links
frontend/src/assets/tailwind.css             ← tokens (no inline styles, no new deps lightly)
```

### Blockers & sequencing notes

- Vault initiation is the tightest seam — `initiate_vault` orchestrates rooms+dwellers+items+objectives+resources; keep `VaultStartConfig` minimal and env-overridable like the other nested configs (`game_config.py:763`).
- Diversity touches every dwellers creation path — run the `test_crud/test_dweller.py:67` update first or the suite will fail (it hard-asserts `race=="human"`).
- Roadmap direction: P1 low-hanging fruit (A) outranks new systems; C is greenfield but follows the single established overlay pattern — no tour library needed unless a11y focus management requires it (decide then, not now).

---

## 4. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Seeded determinism breaks (`seed` at `utils/dwellers.py:79` uses a single `rng`) | Keep using the same `rng` instance for race/faction/`state_of_being` rolls; add a seeded determinism test (same seed→same triple) + distribution test |
| `DwellerVisualAttributes` validator rejects generated pair | Generator must read the canonical `faction_restrictions` and `STATE_OF_BEING_OPTIONS` — no ad-hoc tables; strict `race_weights` validation prevents unknown keys reaching `rng.choices` |
| `race_weights` misconfig (unknown key, zero total, enum string) | Validator rejects unknown/missing RaceOption, requires positive total, normalizes `"Super Mutant"`→`super_mutant` before `rng.choices`; accessor raises `ValueError` before generation, never silently empty |
| Faction lore incoherence (uniform faction makes most humans not vault_dweller) | Ship an explicit faction-weighting policy for humans (`vault_dweller` dominant) instead of uniform; document the table |
| Onboarding `preferences` clobber (stale PUT erases theme) | Implement read–merge–write under `preferences.onboarding` only (`PATCH` or `SELECT … FOR UPDATE` + `preferences || jsonb_build_object('onboarding', patch)`); never `PUT` whole `preferences` from a stale read |
| `POST /vaults/initiate` contract drift | This slice keeps `{number, boosted}` unchanged — no `preset` field, so no drift; if a preset enum ever ships, add it with `boosted` compat and `types:generate` in that follow-up |
| Net-LOC regression | Consolidate the 3 scattered template pools if touched; don't duplicate `faction_restrictions`; count only non-test source per v2.35 rule |

---

## 5. Todos (append batches below with edit/apply_patch — never rewrite headers)

- [ ] A1. `backend/app/core/game_config.py` — add `DwellerConfig.race_weights: dict[str,int]` default 70/15/10/5 + **strict** validator (reject unknown/missing RaceOption, require int>=0, require positive total, normalize enum strings) + `faction_weights` policy for humans (vault_dweller dominant) + `get_race_weights()` (mirror `IncidentConfig.get_spawn_weights` `135`) + `standard_rare_chance=0.04` / `boosted_rare_chance=0.12`; register in `GameConfig` `763`
  Parallelization: Wave 1 | References: `backend/app/core/game_config.py:521-783` | Test-first: failing validator + distribution + determinism tests before code
- [ ] A2. `backend/app/utils/dwellers.py:79` — replace line 119 hardcode with seeded `rng.choices` race roll from `game_config.dweller.get_race_weights()`, faction via weighted `faction_weights` (or at least vault_dweller-weighted for humans) from `faction_restrictions[race]` (`options/factions.py:26`), `state_of_being` from `STATE_OF_BEING_OPTIONS` (`options/races.py:48`) for non-humans; keep determinism; **test-first**: rewrite `test_crud/test_dweller.py:82/94` to accept distribution + add `test_utils/test_dwellers.py` seeded + distribution tests (red before green)
  Parallelization: Wave 1 | Blocked by: A1 (weights) | References: `backend/app/utils/dwellers.py:79`, `backend/app/options/races.py:6`, `backend/app/options/factions.py:8` | Test-first
- [ ] B1. `backend/app/core/game_config.py` + `backend/app/services/vault_service.py:600` — add `VaultStartConfig` (`VAULT_START_*`: `initial_resource_pct`, `initial_stimpaks`, `initial_radaways`, `standard_rare_chance`/`boosted_rare_chance` if not in DwellerConfig) and wire `initiate_vault`/`_prepare_initial_rooms`/`_create_initial_dwellers`/`_assign_initial_objectives` to consume it (replace literals at 640-642 `//2` and 657-658 `min(5,cap)`). No new API field this slice — `VaultNumber` (`schemas/vault.py:19`) and `POST /vaults/initiate` (`endpoints/vault.py:134`) stay `{number, boosted}`.
  Parallelization: Wave 1 | References: `backend/app/services/vault_service.py:600` | Test-first: config-consumption test before wiring
- [ ] B2. `frontend/src/modules/vault/views/HomeView.vue:24` — copy hint for tuned start values (rare 4%→12% etc) within the existing `boostedStart` checkbox line; no preset selector this slice. No `stores/vault.ts:102` or `schemas/vault.ts:8` change; no `types:generate` needed this slice (no API change).
  Parallelization: Wave 2 | Blocked by: B1 | References: `frontend/src/modules/vault/views/HomeView.vue:24`
- [ ] C1. `frontend/src/core/composables/useOnboarding.ts` (new, **explanatory variant**) + `frontend/src/App.vue` + `frontend/src/modules/vault/views/VaultView.vue:158` + `backend/app/models/user_profile.py:17` + `backend/app/api/v1/endpoints/user.py:180` — onboarding composable (pattern: `useVersionDetection.ts`), global overlay mount in `App.vue`, trigger in `VaultView.loadVaultData` and `HomeView.createVault`, **hybrid merge-safe** persistence (`localStorage` per-user×vault instant + `PATCH /api/v1/users/me/preferences/onboarding` or `merge_onboarding_preferences` service that `SELECT … FOR UPDATE` + `preferences || jsonb_build_object('onboarding', patch)`), skippable/dismissable, explanatory links not required actions, boosted-vault explanatory branch, `prefers-reduced-motion`
  Parallelization: Wave 1 | References: `frontend/src/core/composables/useVersionDetection.ts`, `frontend/src/App.vue`, `frontend/src/modules/vault/views/VaultView.vue:158` | Test-first: `useOnboarding.test.ts` red before composable
- [ ] C2. Onboarding step content + `frontend/src/core/components/common/SidePanel.vue` + `frontend/src/modules/vault/components/shell/OverseerBriefing.vue` — 9 **explanatory** step copy (ROADMAP:510, rewritten for pre-seeded vault: "observe your power room" + links, not "build it"), sidebar links (step 9), soft-hook handoff to briefing attention items, warm-surface token alignment (`tailwind.css`), `prefers-reduced-motion` guard; add `frontend/tests/unit/composables/useOnboarding.test.ts` + mount tests (test-first)
  Parallelization: Wave 2 | Blocked by: C1 | References: `frontend/src/core/components/common/SidePanel.vue`, `frontend/src/modules/vault/components/shell/OverseerBriefing.vue`

---

## 6. Open decisions — resolved for this slice (review feedback applied 2026-08-31)

1. **Race weights & env shape — RESOLVED:** `DWELLER_RACE_WEIGHTS='{"human":70,"ghoul":15,"synth":10,"super_mutant":5}'` with strict validation (reject unknown/missing, require positive total, normalize enum strings). Single config (no separate `boosted_race_weights`); diversity is global.
2. **Recycling rule — RESOLVED:** preserve original race (do not re-roll); document in test.
3. **Onboarding persistence — RESOLVED:** hybrid with **namespaced merge** (`preferences.onboarding` via `PATCH` / `merge_onboarding_preferences` read–merge–write), not whole-object `PUT`.
4. **Start presets — RESOLVED for this slice:** keep `boosted: bool`; no new `preset` enum. `VaultStartConfig` is internal tuning only; a future preset enum requires an explicit per-preset mapping table.

---

_Last updated: 2026-08-31_ — patched after review: onboarding is explanatory (pre-seeded vault), `boosted: bool` stays, rarity boost is P0 (12% vs 4%), test-first mandatory, merge-safe `preferences.onboarding`, strict `race_weights` + faction weighting (see `docs/ROADMAP.md` P1s and ROADMAP:510).
