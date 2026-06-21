# Changelog

All notable changes to this project will be documented in this file.
See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

---

## [Unreleased]

### Added

- 
### Fixed

- 
### Changed

- 

---

## [2.19.0] - 2026-06-21

### Added

- **SSE streaming infrastructure** — `SSEManager` singleton with per-user pub/sub queues. 4 SSE endpoints: notifications (`GET /stream/notifications`), game ticks (`GET /stream/game/{vault_id}/ticks`), AI chat tokens (`POST /stream/chat/{dweller_id}`), exploration events (`GET /stream/exploration/{vault_id}`).
- **Heartbeat keepalive** — `_with_heartbeat` wrapper yields comments every 30s of inactivity on GET SSE endpoints, preventing proxy timeouts.
- **Dual notification broadcast** — `NotificationService.send_notification` now publishes via both WebSocket and SSE. Frontend `NotificationBell.vue` replaced 30s polling with live SSE subscription (`useSse`).
- **Streaming AI chat** — `chat_service.stream_response()` yields token-by-token via `run_stream()`. Chat SSE endpoint streams tokens with `event: token`, then `event: done` with dweller_message_id and happiness_impact.
- **Game tick SSE publishing** — `process_vault_tick()` publishes tick results to SSE after each game tick. Duplicate SSE publish bug fixed with 3 regression tests.
- **Exploration SSE publishing** — `ExplorationCoordinator.process_event()`, `complete_exploration()`, and `recall_exploration()` publish live events to the `exploration` SSE topic.
- **Frontend SSE composables** — `useEventStream` (GET, wraps VueUse `useEventSource` with safe JSON parsing), `usePostEventStream` (POST, fetch-based with proper SSE protocol parser handling event/data/id fields), `useSse` (GET with Authorization headers for authenticated streams).
- **Stream manager tests** — 11 unit tests covering subscribe/publish, multi-subscriber, disconnect cleanup, queue full (best-effort), close/shutdown, broadcast_to_vault, and heartbeat passthrough/timeout.
- **Response schemas** — Added `GameBalanceResponse`, `HappinessModifiersResponse`, `DeathStatsResponse`, `UnassignResponse`, `AutoAssignResponse`, `DwellerAssignmentItem`, `QuestPartyMemberRead`, `EligibleDwellerRead` schemas.
- **`unequip_outfit`/`unequip_weapon` return types** — Added `response_model=None` and `-> None` type annotations.

### Fixed

- **Duplicate SSE publish in game loop** — `process_game_tick` no longer publishes SSE after `process_vault_tick` (which already publishes). Fixed with TDD (3 regression tests in `test_game_loop_sse.py`).
- **`usePostEventStream` SSE parsing** — Rewrote to properly parse `event:`, `data:`, `id:` fields, safe JSON parsing with fallback to raw text, and no hardcoded `[DONE]` sentinel (metadata preserved).
- **Lint warnings** — `stream_manager.py`: unused `after_id`/`vault_id` parameters renamed, unused loop variables prefixed. `stream.py`: `asyncio.TimeoutError` → `TimeoutError`, removed stale `noqa`.
- **Password validation** - Added `min_length=8` to `UserCreate.password` schema. Added client-side password length and email format validation to RegisterForm.
- **Game balance endpoint** — Added missing `dweller` and `exploration` fields to `GameBalanceResponse` construction.

### Changed

- **Dict → Pydantic schema refactoring** — Replaced `dict` return types with typed Pydantic schemas in 8+ endpoints: `get_game_balance_settings` (`GameBalanceResponse`), `get_happiness_modifiers` (`HappinessModifiersResponse`), `get_death_statistics` (`DeathStatsResponse`), vault auto-assign endpoints (`UnassignResponse`/`AutoAssignResponse`), quest party/eligible dweller endpoints (`QuestPartyMemberRead`/`EligibleDwellerRead`).
- **Schema unpacking** — 4 pregnancy endpoints switched from manual field mapping to `PregnancyRead.model_validate()`.
- **Service layer relocation** — Radio mode vault mutation moved from `radio.py` endpoint to `radio_service.set_radio_mode()`. CRUD exploration `get_by_vault`/`get_active_by_vault` consolidated into single `get_by_vault(active_only=False)`.
- **Auth endpoint return types** — 5 auth endpoints wired to existing `MessageResponse` schema.
- **Game control return type annotations** — Added `-> dict[str, Any]` to `get_game_state`, `manual_tick`, `resolve_incident`.
- **UI component accessibility** — Added `role=button`, `tabindex`, keyboard Enter/Space handlers to UDropdown. Added `role=dialog` and `aria-modal=true` to UModal. Added auto-generated `id` + label `for` association to UInput. Replaced inline `:style` color with `text-theme-primary` class on UCard.
- **Admin password** - Updated `backend/.env.example` password to meet `min_length=8` requirement.

---

## [2.18.0] - 2026-06-21

### Added

- **Library skills** — Added FastAPI, Typer, and Pydantic AI compliance skills from `uvx library-skills`. Added `.agents/skills/fastapi/SKILL.md`, `.agents/skills/typer/SKILL.md`, `.agents/skills/building-pydantic-ai-agents/SKILL.md`.
- **Router prefix/tags in APIRouter constructors** — Moved `prefix` and `tags` from `include_router()` into individual `APIRouter()` definitions across all 22 router files. Cleans up `api.py` router registration.
- **`ChatMessage` schema** — Moved request model from `chat.py` endpoint to `schemas/chat.py`.
- **`ChatService.send_chat_notification()`** — Moved `_send_chat_notification` helper from endpoint to service layer as a static method.

### Changed

- **Annotated dependency style** — Standardized 12 endpoint params and 6 shared deps to `Annotated[Type, Depends()]` pattern in `deps.py` and 9 endpoint files.
- **Return type annotations** — Added explicit return type annotations to ~108 endpoint functions across all 22 endpoint files.
- **Nested try-except extraction** — Extracted `_extract_usage()` helpers in `chat_service.py` and `conversation_service.py`. Extracted `_send_chat_notification()` in `chat.py`.
- **Async safety** — Wrapped sync S3/storage/OpenAI calls with `asyncio.to_thread()` in `open_ai.py`, `dweller_ai.py`, `conversation_service.py`, and `exploration/coordinator.py`.
- **Version bump** — Backend 2.17.0 → 2.18.0, frontend 2.17.0 → 2.18.0.

### Fixed

- **Chat endpoint nested try-except** — `_send_chat_notification` was nested inside the main `try` block in `voice_chat_with_dweller`; extracted to a helper called after the try block.

### Removed

- **Stale documentation** — Deleted `docs/archive/` (8 outdated planning docs from v2.4–v2.6) and `docs/TWELVE_FACTOR_COMPLIANCE.md` (Jan 2026 one-time audit).
- **Irrelevant skills** — Removed `tsdown/` (library bundler, not used) and `zod-v4/` (leftover).
- **Duplicate skills** — Removed `backend/.agents/skills/` copies of fastapi, typer, and building-pydantic-ai-agents (exact duplicates of root copies).

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
