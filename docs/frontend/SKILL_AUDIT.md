# Frontend Skill Audit — Rule Violations

> Audit date: 2026-08-18 · Scope: `frontend/src` checked against the project agent-skill rulebooks
> (`vue-best-practices`, `tailwindcss-v4`, `pinia-best-practices`, `vueuse-functions`,
> `vue-router-best-practices`, AGENTS.md frontend rules, `docs/frontend/STYLEGUIDE.md`).
> Findings verified against a real production build (`vp build` → exit 0; compiled CSS inspected).

Severity legend: 🔴 CRITICAL (silent rendering bug / dead code) · 🟠 MAJOR (rule violation, visual or type-safety) · 🟡 MINOR (preferred-pattern deviation)

---

## 🔴 CRITICAL — Dead classes from camelCase token usage (20 files)

> **Status: ✅ REMEDIATED** (baseline finding from 2026-08-18; fixed in `fix/frontend-audit`).
> The camelCase utilities below were a real defect at audit time, but the token migration is now
> complete — all `text-terminalGreen` / `bg-terminalBackground` / `bg-terminalGreen` occurrences
> were converted to their kebab-case equivalents. Keep this section as the historical baseline;
> do not treat these as active defects.

**Rule violated** (`tailwindcss-v4`): design tokens are consumed via their exact utility name. The theme defines
**kebab-case** tokens (`--color-terminal-green`, `--color-terminal-background` → utilities `text-terminal-green`,
`bg-terminal-background`). CamelCase spellings generate **nothing** in Tailwind v4.

**Evidence (compiled CSS):** only kebab utilities exist (`bg-terminal-background`, `text-terminal-background`).
`text-terminalGreen`, `bg-terminalBackground`, `bg-terminalGreen` appear in **zero** generated utilities. The only
compiled `.text-terminalGreen` comes from a manual scoped rule in `DwellersView.vue:390-392`, so it works *only*
inside that component. Every other occurrence is silently dead.

Affected files (1–8 dead classes each):

| File | Classes |
|---|---|
| `src/modules/vault/views/VaultView.vue` (8×) | `text-terminalGreen` (incl. retry button, below), `bg-terminalGreen`, `bg-terminalBackground` |
| `src/modules/dwellers/views/DwellersView.vue` | `text-terminalGreen` (works only here — manual scoped rule) |
| `src/modules/dwellers/views/DwellerDetailView.vue`, `DwellersList.vue`, `GraveyardView.vue` | `text-terminalGreen` / `bg-terminalBackground` |
| `src/modules/exploration/views/ExplorationDetailView.vue` | `text-terminalGreen`, `bg-terminalBackground` |
| `src/modules/map/views/MapView.vue`, `src/modules/profile/views/PreferencesView.vue` | `text-terminalGreen`, `bg-terminalBackground` |
| `src/modules/progression/views/{ObjectivesView,QuestDetailView,QuestsView,TrainingView}.vue` | `text-terminalGreen` / `bg-terminalBackground` |
| `src/modules/radio/views/RadioView.vue`, `src/modules/rooms/components/RoomMenu.vue` | `text-terminalGreen` |
| `src/modules/social/views/RelationshipsView.vue`, `components/pregnancy/PregnancyDebugPanel.vue` | `text-terminalGreen` |
| `src/modules/storage/views/StorageView.vue`, `src/modules/vault/views/HomeView.vue` | `bg-terminalBackground` |
| `src/core/components/ui/UInput.vue`, `src/views/UITestView.vue` | `text-terminalGreen` / `bg-terminalBackground` |

**Real visible bug:** `VaultView.vue:314` retry button `class="rounded bg-terminalGreen ... text-black"` → dead
background + black text = **invisible button** on the black page.

**Fix:** `text-terminalGreen` → `text-terminal-green`, `bg-terminalBackground` → `bg-terminal-background`,
`bg-terminalGreen` → `bg-terminal-green`. Delete the manual `.text-terminalGreen` scoped rule in
`DwellersView.vue:390-392` (the kebab utility replaces it).

---

## 🔴 CRITICAL — References to non-existent CSS variables

> **Status: ✅ REMEDIATED** (baseline finding from 2026-08-18; fixed in `fix/frontend-audit`).
> The `text-[--color-terminal-green-400]` / `-100` / `-300` text utilities in `AboutView.vue` and
> `ChangelogModal.vue` were switched to kebab-case token classes, and the
> `border-[--color-terminal-green-500]/30` border in `ChangelogModal.vue:195` was replaced with the
> existing `border-terminal-green/30` token. No active references remain.

**Rule violated** (`tailwindcss-v4`): arbitrary values must reference real tokens. (Note: consuming
design tokens is a **project policy** — AGENTS.md "Design token source of truth" + STYLEGUIDE —
not a Tailwind requirement; Tailwind only requires arbitrary values to resolve to valid CSS.)

**Historical evidence (compiled CSS):** `.border-\[--color-terminal-green-500\]\/30{border-color:var(--color-terminal-green-500)}`
→ invalid (undefined var) → silently ignored.

**Fix (applied):** use the existing token `border-terminal-green/30` instead of the undeclared
`--color-terminal-green-500` shade.

---

## 🟠 MAJOR — Hardcoded hex where design tokens exist (9 files)

**Rule violated** (`tailwindcss-v4` "Use Design Token Classes" + AGENTS.md "Design token source of truth"):

| File | Hex | Existing token |
|---|---|---|
| `vault/components/shell/NotificationBell.vue:248,249,271,274,299,307,308` | `bg-[#1c1917]`, `bg-[#141210]`, `bg-[#211e1b]`, `border-[#211e1b]`, `divide-[#211e1b]` | `--color-surface-warm` / `-dark` / `-hover` (exact match) |
| `vault/components/shell/NavBar.vue:70` | `bg-[#1c1917]` | `bg-surface-warm` |
| `vault/components/shell/GameControlPanel.vue:85` | `bg-[#1c1917]/90` | `bg-surface-warm/90` |
| `vault/components/shell/ResourceBar.vue:154` | `border-[#57534e] bg-[#292524]` | nearest tokens (`border-stone-*` / surface scale) |
| `exploration/components/ExplorerCard.vue:69`, `components/QuestPartyCard.vue:77` | `'#FFD700'` (progress 100%) | `--color-rarity-legendary: #ffd700` |
| `vault/components/HappinessDashboard.vue` (13×) | `#4ade80`, `#fbbf24`, `#ef4444`, `#9ca3af`, `#e5e7eb` in JS + `<style>` + inline attrs | `--color-success` / `-warning` / `-danger` |
| `progression/components/QuestCard.vue:105-109,241,247,477,516-517,570`, `views/QuestDetailView.vue:65-69,364,433,435,509,513,645-652` | quest-type palette `#ffb000/#c0c0c0/#00d9ff/#9b59b6/#00ff00` + `#ff6600/#666666` | **no tokens exist — needs new `--color-quest-*` in `@theme`** |

---

## 🟠 MAJOR — Inline styles (2 files)

**Rule violated** (AGENTS.md: "Tailwind utilities only; avoid inline styles"):

- `src/views/UITestView.vue` — 60+ `:style=` bindings (lines 88–438, 461–772). Dev/test view, but still in `src/`.
- `src/modules/vault/components/HappinessDashboard.vue` — inline `style="color: #4ade80"` attributes (254, 274, 294)
  + `backgroundColor`/`color` in JS config objects (137, 155, 266, 286, 306).

---

## 🟠 MAJOR — Router prototype monkey-patch with `any` (1 file)

**Rule violated** (`vue-router-best-practices` + repo no-`as any` rule): `src/router/index.ts:5-13` patches
`createRouter.prototype.push` with `location: any` / `err: any` and swallows `NavigationDuplicated` +
`No match found` errors globally; logs via `console.warn`.

**Fix:** keep the behavior but type it — `err instanceof Error && ...` or a typed wrapper — and log via the app
logger instead of `console.warn`.

---

## 🟡 MINOR — v-for index keys (8 files)

**Rule violated** (`vue-best-practices` stable keys): `:key="index"/"idx"/"i"` in:

- `HappinessDashboard.vue:320`, `FormattedChangeDescription.vue:116`, `ExplorerCard.vue:187`,
  `ExplorationEventLog.vue:40`, `CombatModal.vue:85` (loot list), `ExplorationRewardsModal.vue:139,176`,
  `EventTimeline.vue:74`, `FakeCrashOverlay.vue:98,111`
- Acceptable (static/append-only): `ChangelogView.vue:173` (skeleton), `RadioStatsPanel.vue:151` (enum index)

Loot/event lists that can change order should get stable ids.

---

## 🟡 MINOR — Hand-rolled timers vs VueUse (23 files)

**Rule violated** (`vueuse-functions`): raw `setTimeout`/`setInterval` in `useEventStream.ts:149`,
`useWebSocket.ts:96`, `useTokenRefresh.ts:128`, `useVisualEffects.ts:146`, `useToast.ts`, `ExplorerCard.vue:36`,
`QuestPartyCard.vue:28`, etc.

The repo already has the right pattern — `src/core/composables/usePolling.ts` uses `useIntervalFn` correctly.
Timer-based composables should use `useIntervalFn` / `useTimeoutFn` / `useTimeoutPoll`.

---

## 🟡 MINOR — Direct `localStorage` instead of `useStorage` (5 files)

**Rule violated** (`vueuse-functions`): raw `localStorage` in `QuestsView.vue:154`, `quest.ts:40`,
`AIUsageCard.vue:60/66`, `core/plugins/axios.ts:19-59`, `useVersionDetection.ts:22/54/68`.

Precedent already set — `src/modules/auth/stores/auth.ts` uses `useLocalStorage` correctly.

---

## ✅ CLEAN — Verified non-violations

- **Pinia**: all stores are setup-style `defineStore`; `storeToRefs` used correctly (`ExplorationView.vue:38`,
  `PregnancyDebugPanel.vue:19-21`); the `dweller.ts` slice pattern (`const { filter: dwellerStore } = useDwellerStore()`)
  destructures store *instances*, not state — reactivity-safe, matches `pinia-best-practices`
- **v-html**: only in `DwellerBio.vue:141`, sanitized with DOMPurify + strict allowlist (`PURIFY_OPTIONS`) — safe
- **v-if + v-for same element**: none found
- **`.value.sort()` / `.reverse()` mutation**: none found
- **Router guards**: `beforeEach` uses clean `return '/login'` redirect — no `next` misuse
- **Tailwind v4 config**: `@import 'tailwindcss'` + `@theme` in `tailwind.css` is correct CSS-first setup;
  `@tailwindcss/vite` plugin wired; `vite.config.ts` / `vitest.config.ts` align with AGENTS.md (vite-plus)
- **Build**: passes (`vp build` exit 0)

---

## Suggested fix order

> **Status (post-`fix/frontend-audit`):** items 1–5 are done. The CRITICAL camelCase migration,
> the `-green-*00` text-variable fixes, the hex→token migrations, the router-instance remediation,
> and the inline-style cleanup are all applied and verified (typecheck/lint/tests/build green).
> Item 6 (MINOR) remains open and is incremental.

1. ✅ 🔴 CRITICAL batch 1 — dead camelCase classes (~20 files) incl. invisible `VaultView.vue:314` retry button
2. ✅ 🔴 CRITICAL batch 2 — broken `--color-terminal-green-*00` vars in `AboutView.vue` / `ChangelogModal.vue`
   (incl. the `--color-terminal-green-500` border reference, now `border-terminal-green/30`)
3. ✅ 🟠 MAJOR — `NotificationBell` / `NavBar` / `GameControlPanel` hex → existing `surface-warm` tokens
4. ✅ 🟠 MAJOR — remaining hex → token migrations (`ExplorerCard`, `HappinessDashboard`, quest-type palette)
5. ✅ 🟠 MAJOR — router patch typing (now wraps the router instance, not the prototype), inline styles
6. 🟡 MINOR — v-for keys, timers, localStorage (incremental, no rush)