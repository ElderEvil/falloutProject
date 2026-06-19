# Changelog

All notable changes to this project will be documented in this file.
See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

---

## [Unreleased]

### Fixed

- **Password validation** - Added `min_length=8` to `UserCreate.password` schema. Added client-side password length and email format validation to RegisterForm.

### Changed

- **UI component accessibility** - Added `role=button`, `tabindex`, keyboard Enter/Space handlers to UDropdown. Added `role=dialog` and `aria-modal=true` to UModal. Added auto-generated `id` + label `for` association to UInput. Replaced inline `:style` color with `text-theme-primary` class on UCard.
- **Admin password** - Updated `backend/.env.example` password to meet `min_length=8` requirement.

---

## [2.17.0] - 2026-06-19

### Added

- **Storage model medical fields** — Added `stimpack` and `radaway` fields to `StorageBase`. Alembic migration `abc123def456` copies existing data from vault to storage and drops the 4 legacy vault columns.
- **Medical production config** — Added `MEDICAL_ROOM_PRODUCTION` mapping (medbay→stimpak, science lab→radaway) and `compute_medical_capacity()` to `game_config.py`. Capacity is now computed dynamically from rooms instead of stored on the vault.
- **StorageView medical display** — Added `stimpack`/`radaway` fields to `StorageSpaceResponse` endpoint. StorageView now reads stimpak/radaway counts from storage API instead of removed vault fields.

### Changed

- **Resource manager** — Medical production (`_apply_room_production`) uses `MEDICAL_ROOM_PRODUCTION` config mapping instead of string matching. Writes stimpaks/radaways to Storage, capped by `compute_medical_capacity`.
- **Vault service** — Room build no longer updates `stimpack_max`/`radaway_max` on vault. Vault init writes initial medical supplies to Storage. `transfer_medical_supplies` reads/writes Storage instead of vault fields.
- **Exploration service** — `send_dweller` deducts stimpaks/radaways from Storage. Unused supplies returned on recall are written to Storage, capped by computed capacity.
- **Vault CRUD** — Removed `stimpack_max`/`radaway_max` special-casing in `_handle_production_room`.
- **Vault model** — Removed `stimpack`, `stimpack_max`, `radaway`, `radaway_max` fields.
- **Version bump** — Backend 2.16.0 → 2.17.0, frontend 2.16.0 → 2.17.0.

### Removed

- **Legacy vault medical fields** — `stimpack`, `stimpack_max`, `radaway`, `radaway_max` no longer exist on the Vault model. Stimpack/radaway data lives exclusively on Storage.

---

## [2.16.0] - 2026-06-18

### Added

- **UModal focus trap** — Hand-rolled (no new deps) with Tab cycling, Escape close, focus restore.
- **`role="button"`/`tabindex`/keyboard handlers** — Added to 13 clickable elements across 8 files.
- **`aria-label` attributes** — Added to 8 icon-only buttons in dwellers and rooms modules.
- **ARIA on inline modals** — Added `role="dialog"`, `aria-modal`, escape-key close to DwellerEquipment and RoomMenu.
- **Module READMEs** — Added 12 `README.md` files in `frontend/src/modules/` (auth, vault, dwellers, rooms, etc.).
- **Nuxt UI migration plan** — Added `.omo/drafts/nuxt-ui-migration-plan.md`.

### Changed

- **Auth forms migrated to UButton/UInput** — `LoginFormTerminal`, `RegisterForm`, `ForgotPassword`, `ResetPassword`, `VerifyEmail` now use home-grown UI components instead of raw `<button>`/`<input>`.
- **HomeView vault creation form** — Migrated to `UButton`/`UInput`.
- **CSS variable migration** — ~45 files: hardcoded hex colors in scoped CSS replaced with CSS variables (`--color-theme-primary`, `--color-danger`, etc.).
- **UButton `type` prop** — Added `type` prop (`button`/`submit`/`reset`) for form submit support.

### Fixed

- **12 skipped backend tests** — Fixed and now passing (quest datetime, 6 bare-skips, 3 incident assertions, 2 room session-race).
- **VerifyEmailView theme color** — Replaced nonstandard `--theme-color` with canonical `--color-theme-primary`.
- **LoginForm.vue dead code** — Deleted (route uses `LoginFormTerminal.vue`).
- **`fix-changelog-freeze.md` dropped** — Superseded; fix shipped in v2.14.4.

---

## [2.15.0] - 2026-06-18

### Added

- **Dweller Visual Unification** — Merged `DwellerVisualAttributesInput` (user-facing), `DwellerVisualAttributes` (AI output), and `VisualAttributes` (frontend) into a single 22-field schema with canonical field names (`hair_style`, `build`).
- **Race/Faction-aware AI agent** — The visual attributes agent now receives race and faction context, generating lore-appropriate appearances (ghoul skin/scarring, super mutant builds, synth metallic features).
- **Race/faction display in frontend** — `DwellerAppearance.vue` now shows Race, Faction, State of Being, plus all new fields.
- **Default visual attributes** — New dwellers get `{race: human, faction: vault_dweller}` on creation.
- **Manual appearance editor** — `DwellerAppearanceEditor.vue` modal with race-filtered dropdowns for all 22 visual fields, plus a Randomize button.
- **Portrait regeneration** — `POST /dwellers/{id}/generate_photo/?force=true` allows regenerating portraits after editing appearance.
- **Options data module** — Added `backend/app/options/` with race/faction/appearance/item/scene data ported from `fallout-avatar` project.

### Changed

- **Schema unification** — Removed duplicate `DwellerVisualAttributes` from `schemas/dweller_ai.py`; all usages now import from `schemas/dweller.py`. `DwellerVisualAttributesInput` kept as backward-compat alias.
- **AI enrichment flow** — `_has_substantial_visual_attributes()` helper allows AI generation to enrich minimal identity defaults without blocking.
- **Generate/Edit button logic** — "Generate" button only appears when AI can still enrich; "Edit" appears once any attributes exist.
- **Frontend types regenerated** — OpenAPI types now include `DwellerVisualAttributes` with all 22 fields.

### Fixed

- **RustFS bucket policies** — Ran `set_rustfs_bucket_policies.py` to enable public read on `dweller-images`, `dweller-thumbnails`, `dweller-audio`.
- **Editor theming** — Replaced hardcoded green colors with CSS theme variables.
- **Editor field backgrounds** — Changed from semi-transparent to solid black with `appearance: none` on selects.

---

## [2.14.4] - 2026-06-17

### Security

- **Frontend dep bumps** - Bumped `dompurify` to 3.4.11, `form-data` to 4.0.6, `js-yaml` to 4.2.0 to fix Dependabot advisories:
  - dompurify: multiple sanitization bypasses, Trusted Types poisoning, IN_PLACE mode issues
  - form-data: CRLF injection via unescaped multipart field names
  - js-yaml: Quadratic-complexity DoS in merge key handling

- **Backend dep bumps** - Bumped `python-multipart` to 0.0.32, `aiohttp` to 3.14.1 to fix Dependabot advisories:
  - python-multipart: CVE-2025-22140 (header leading to unlimited buffer copy)
  - aiohttp: CVE-2024-52304, CVE-2024-52303, CVE-2024-52302 (request smuggling, x-xss-protection bypass, DOS via empty multipart)
