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
  dompurify: multiple sanitization bypasses, Trusted Types poisoning, IN_PLACE mode issues
  form-data: CRLF injection via unescaped multipart field names
  js-yaml: Quadratic-complexity DoS in merge key handling

- **Backend dep bumps** - Bumped `python-multipart` to 0.0.32, `aiohttp` to 3.14.1 to fix Dependabot advisories:
  python-multipart: CVE-2025-22140 (header leading to unlimited buffer copy)
  aiohttp: CVE-2024-52304, CVE-2024-52303, CVE-2024-52302 (request smuggling, x-xss-protection bypass, DOS via empty multipart)
