# UI Consolidation Audit

**Status:** Audit complete; first modal behavior batch complete; further consolidation pending
**Date:** 2026-09-03
**Scope:** Vue UI components, views, shared UI primitives, and terminal-theme patterns

## Objective

Find UI elements that serve the same user-facing purpose but are implemented with different markup, styling, or interaction behavior. Consolidation should reduce visual drift, duplicated logic, and accessibility differences while preserving intentional domain-specific variants.

## Findings

### P0 — Consolidate modal foundations

There are several modal implementations responsible for the same overlay/dialog behavior:

- `core/components/ui/UModal.vue`
- `core/components/common/RewardsModalShell.vue`
- `modules/exploration/components/ExplorationDurationModal.vue`
- `modules/dwellers/components/DwellerEquipment.vue`
- `modules/rooms/components/RoomMenu.vue`

They independently implement backdrop closing, focus management, close buttons, scrolling, sizing, animation, and dialog semantics. `UModal` and `RewardsModalShell` even contain separate focus-trap implementations.

**Next action:** make `UModal` the single modal foundation. Add header/footer slots and narrowly scoped visual options for reward, orange/wasteland, and wide room-menu variants. Migrate the custom overlays afterward and remove duplicate focus/scroll behavior.

References: `UModal.vue:151`, `RewardsModalShell.vue:74`, `ExplorationDurationModal.vue:55`, `DwellerEquipment.vue:319`, `RoomMenu.vue:43`.

### P1 — Consolidate the vault page shell

Fourteen views repeat the same `vault-layout`, `main-content`, sidebar offset, and collapsed-sidebar CSS. Some pages use `PageContentRail`; others recreate `container`, max-width, and padding rules.

**Next action:** introduce one shared vault-page shell containing `SidePanel`, main-content offset handling, scanlines, and `PageContentRail`. Migrate pages incrementally, starting with the closest matches: Trading Post, Training, Dwellers, Graveyard, Radio, Happiness, and Relationships.

References: `TradingPostView.vue:29`, `TrainingView.vue:68`, `DwellersView.vue:302`, `HappinessView.vue:100`, `PageContentRail.vue:2`.

### P1 — Standardize loading, error, and empty states

Loading and failure states are implemented as custom markup in multiple places. `ExplorationView` and `DwellerChatPage` contain nearly identical CRT loading markup and CSS. Other pages use different spinner sizes, copy, retry buttons, and error containers. `TerminalEmptyState` already exists but is not used consistently.

**Next action:** create a shared terminal async-state component with `loading`, `error`, `empty`, and retry slots/props. Use `TerminalEmptyState` as the empty-state base and standardize loading copy with the ellipsis character (`Loading…`).

References: `ExplorationView.vue:261`, `DwellerChatPage.vue:55`, `HappinessView.vue:110`, `GraveyardView.vue:69`, `DwellerDetailContainer.vue:57`, `TerminalEmptyState.vue:14`.

### P1 — Use one tab primitive

`UTabs` is used by Storage, Trading, Profile, Settings, and Dweller details. Quests and Objectives instead define their own `.tabs`, `.tab-button`, active state, spacing, and hover behavior; these two implementations are almost identical.

**Result:** Quests and Objectives now use `UTabs` with optional icon metadata; their duplicate tab CSS was removed while preserving the existing labels, icons, active state, and content behavior.

**Next action:** keep `UTabs` as the default for future tabs and audit any new stateful tab groups for URL-sync requirements separately.

References: `UTabs.vue:33`, `QuestsView.vue:239`, `ObjectivesView.vue:62`.

### P1 — Consolidate progress indicators

`UProgressBar` exists, but simple progress bars are reimplemented in Objective cards, active explorations, combat, storage, room population, and SPECIAL stats. These copies differ in border radius, track color, fill color, and accessibility semantics.

**Next action:** extend `UProgressBar` with configurable track/fill classes or colors and an optional value-label slot. Migrate simple percentage bars first; keep domain-specific wrappers such as resource readouts where they add meaningful information.

References: `UProgressBar.vue:41`, `ObjectiveCard.vue:83`, `ActiveExplorationList.vue:99`, `CombatModal.vue:72`, `StorageView.vue:239`, `RoomMenuItem.vue:106`.

### P1 — Consolidate explorer item variants

`ExplorerCard` and `ActiveExplorationList` both render active exploration identity, equipment, stats, progress, completion, and recall actions. They contain duplicated data formatting, progress markup, and action styling, with only the presentation density differing.

**Next action:** create one explorer item with `compact` and `detailed` variants, or extract shared `ExplorerProgress` and `ExplorerActions` components before merging the shells.

References: `ExplorerCard.vue:42`, `ExplorerCard.vue:65`, `ActiveExplorationList.vue:43`, `ActiveExplorationList.vue:98`.

### P1 — Consolidate top-right activity summary badges

The explorer and quest-team card placement is intentional and useful. The inconsistency is limited to the two top-right header badges in `ExplorationView`: they repeat the counts already shown beside each activity section, use bespoke markup instead of the shared `TerminalMetric`, and use different terminology from the vault status summary. Their values also need an explicit contract: “Explorations” means active expeditions, while “Quests” means active quest records with a party, not questing dwellers.

Quest status is already refreshed by the exploration page polling cycle. Detailed quest management should remain in `/quests`; this summary should be read-only unless the badges become links to the relevant content.

**Next action:** remove the duplicated header badges and retain the section-level counts. If a quick page summary is still desired, replace them with a compact shared `TerminalMetric` group using the labels `EXPEDITIONS` and `QUEST PARTIES`, the same definitions as the section counters, and optional links/scroll targets. Do not change the placement of explorer or quest-party cards.

References: `ExplorationView.vue:237`, `ExplorationView.vue:303`, `ExplorationView.vue:326`, `ExplorationView.vue:102`, `TerminalMetric.vue:22`.

### P1 — Standardize buttons and icon buttons

`UButton` is the project action primitive, but common actions still use local button CSS: retry, refresh, vault load/delete, explorer complete/recall, and several modal actions. This produces different padding, borders, hover behavior, loading behavior, and focus states for equivalent actions.

**Next action:** migrate standard text actions to `UButton`. Add a small `UIconButton` primitive for icon-only controls, with required accessible labels and consistent focus treatment. Add a contextual variant only where the wasteland/amber styling is intentional.

References: `UButton.vue:14`, `HappinessView.vue:120`, `VaultList.vue:73`, `TrainingQueuePanel.vue:123`, `ExplorerCard.vue:122`.

### P1 — Consolidate auth terminal layout

Login, registration, forgot-password, and reset-password repeat the terminal container, CRT frame, header, system-message, form spacing, and feedback styles. The form fields already use shared `UInput` and `UButton` components, but the surrounding layout is duplicated.

**Next action:** create `AuthTerminalLayout` with slots for subtitle, system messages, form, feedback, navigation links, and footer. Add a shared auth feedback style/component for error and success messages.

References: `LoginFormTerminal.vue:110`, `RegisterForm.vue:152`, `ForgotPasswordView.vue:112`, `ResetPasswordView.vue:146`.

### P2 — Standardize form controls

`UInput` and `USelect` coexist with raw inputs and selects. AI settings use `UInput` for the model but raw controls for provider, base URL, and gateway route. Profile editing and changelog search also use locally styled controls.

**Next action:** migrate raw single-line inputs/selects to `UInput`/`USelect`. Decide whether repeated textarea styling justifies a small `UTextarea` primitive. Preserve native controls only when a shared component cannot support the required behavior.

References: `AISettingsPanel.vue:230`, `AISettingsPanel.vue:252`, `ProfileEditor.vue:23`, `ProfileEditor.vue:75`, `ChangelogView.vue:151`.

### P2 — Standardize badges and status chips

`UBadge` exists, but profile verification badges, combat status badges, quest categories, and several training/room chips use local spans and CSS. Similar state and category indicators therefore have different shape, padding, border weight, glow, and color semantics.

**Next action:** map informational, live-status, actionable, and semantic states to `UBadge` variants. Add only the variants that correspond to established design intents; do not use animated/glowing badges for static information.

References: `UBadge.vue:13`, `ProfileView.vue:270`, `CombatModal.vue:375`, `QuestCard.vue:299`.

### P2 — Unify navigation item behavior

The top `NavBar` uses `router-link` for navigation, while `SidePanel` uses buttons that manually call the router. The same destination behavior is therefore implemented differently, including different middle-click, focus, and browser-navigation behavior.

**Next action:** extract a shared navigation-item pattern. Use router links for navigable destinations and buttons only for non-navigation actions or disabled/coming-soon entries.

References: `NavBar.vue:82`, `SidePanel.vue:195`.

### P2 — Remove or classify legacy terminal classes

The global stylesheet still defines `.terminal-card`, `.terminal-button`, `.terminal-input`, and `.terminal-badge`, while the active UI uses `UCard`, `UButton`, `UInput`, and `UBadge`. The legacy classes currently appear unused in Vue templates.

**Next action:** verify usage outside `frontend/src`, then remove the unused definitions or explicitly mark them as compatibility-only. Do this after the component migrations to avoid deleting a still-supported surface.

References: `assets/tailwind.css:395`.

## Recommended implementation order

1. Establish component contracts and visual decisions for modal, async-state, tabs, progress, button, and badge primitives.
2. Implement modal consolidation first because focus and scroll behavior are cross-cutting.
3. Add the shared vault page shell and migrate the most repetitive page wrappers.
4. Migrate Quests/Objectives tabs and simple progress bars.
5. Consolidate explorer cards and auth layout.
6. Migrate raw controls, status chips, and local retry/refresh actions.
7. Remove verified legacy CSS and run a visual regression pass across all themes.

## Verification checklist

- Run `pnpm run lint` and `pnpm run typecheck` after each migration group.
- Run `pnpm run test:run` after the component contracts stabilize.
- Check all three themes: FO4 green, FO3 teal, and FNV amber.
- Check desktop, tablet, and mobile layouts.
- Verify modal Escape handling, outside-click behavior, focus trapping, focus restoration, and background scroll locking.
- Verify loading, error, retry, and empty states for every migrated view.
- Verify icon-only controls have accessible labels and visible `:focus-visible` states.
- Verify navigable items remain keyboard accessible and support normal browser link behavior.

## Lightweight performance and regression tracking

For each consolidation batch, take a simple before/after snapshot using the same browser, viewport, data, and local environment. The goal is to see whether the change improves the experience, has no meaningful impact, or introduces a regression.

Record these signals:

- Load time: approximate page load and time until the main content is visible.
- Memory: browser/app memory after opening the page, then after repeated navigation or modal open/close cycles.
- Bundle size: total JavaScript and CSS size from the production build.
- UI behavior: console errors, failed requests, broken states, and the relevant existing tests.

Use a small representative set: one public page, two vault pages, and the affected component or modal. Repeat each check a few times and report the rough average or range; exact lab-grade precision is not required for this plan.

Prefer browser DevTools, the production build output, and existing unit/manual checks for this tracking. Avoid adding or running Playwright unless a behavior cannot be verified reliably with a simpler check.

### Before/after log

| Batch | Change | Load before → after | Memory before → after | Bundle before → after | Bugs fixed / regressions | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Baseline | Audit only; no implementation yet | TBD | TBD | TBD | 0 / 0 | Populate before the first migration |
| Modal behavior | Shared focus, Escape, body-scroll, and focus-restoration behavior for `UModal` and `RewardsModalShell` | Not measured for this behavior-only batch | Not measured for this behavior-only batch | CSS unchanged at 119.03 kB / 18.08 kB gzip; shared UI JS 37.13 → 37.27 kB | 1 lifecycle/accessibility behavior corrected / 0 | Focused Vitest tests, typecheck, lint, and production build passed |
| Vault page shell | Shared sidebar offset/layout shell adopted by Trading Post, Training Center, and Relationships | Not measured for this structural batch | Not measured for this structural batch | CSS 119.03 kB / 18.08 kB gzip; shared UI JS 37.27 kB / 13.44 kB gzip; new shell chunk 0.56 kB / 0.39 kB gzip | 0 / 0 | 2 new shell tests; full suite 1,424 passed / 1 skipped; typecheck, lint, and production build passed |
| Tabs | Quests and Objectives adopted shared `UTabs` with optional icons; duplicate tab markup and CSS removed | Not measured for this UI-only batch | Not measured for this UI-only batch | CSS 119.03 kB / 18.08 kB gzip; shared UI JS 37.27 → 37.38 kB / 13.44 → 13.46 kB gzip | 0 / 0 | Focused tab/view tests, full suite, typecheck, lint, and production build passed; behavior preserved |

### Bug-fix accounting

For each behavior change, note whether it fixes a pre-existing bug, prevents a regression, or is only a refactor. Count a bug as fixed only when the old behavior can be reproduced and the new behavior is covered by a test or durable manual check.

Likely behaviors to verify include modal focus and scroll restoration, duplicate loading/retry actions, tab and browser-back behavior, empty/error recovery, progress values, and stale state after route changes.

The first implementation batch should establish the baseline row. Every later batch should add one before/after row and record any bug evidence alongside the related tests.

## Guideline reference

The accessibility and interaction recommendations above follow the current [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md), especially the guidance for semantic buttons/links, icon-button labels, visible focus states, async feedback, and modal interaction.
