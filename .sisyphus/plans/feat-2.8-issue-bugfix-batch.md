# Issue Bugfix Batch (feat/2.8)

## TL;DR

Fix 4 user-facing issues (+ recruitment cost mismatch) across frontend + backend:

1) Make **Build/Construction hotkey `B`** work on RU layout and avoid Ctrl/Cmd+B conflicts.
2) Make **Happiness “bottom buttons”** behavior clearer (keep conditional actions, but visible placement).
3) Make **Radio recruitment gating** consistent: if no dwellers assigned to radio room(s), recruitment is blocked **in backend**, and UI shows clear info. Also fix **recruit cost display** to match backend.
4) Make **Room destroy refund** = floor(50% of (base + 1×incremental + applied upgrades by tier)). Update UI to refresh caps after destroy.

**Estimated Effort**: Medium

**Critical Path**: backend refund + backend radio gating → frontend UI updates → tests

---

## Context

### Source issues
- Build mode hotkey `B` fails on Russian keyboard layout.
- Happiness page appears to have “no buttons at the bottom”.
- Radio room should show: “if there are no residents in the radio room, you cannot hire new ones.”
- Destroyed rooms should refund 50% of creation cost (incl upgrades; include incremental cost approximation).
- Recruitment cost is incorrect in UI.

### Confirmed decisions
- Target branch: `feat/2.8`
- Backend changes allowed: **YES**
- Tests: **YES**

#### Destroy refund
- Refund basis: **approximation**, no history persistence.
- Formula: `refund_caps = floor(0.5 * (base_cost + incremental_cost + upgrade_costs_applied_by_tier))`
- Upgrade costs by tier:
  - If `room.tier >= 2` include `t2_upgrade_cost` (if present)
  - If `room.tier >= 3` include `t3_upgrade_cost` (if present)
- Rounding: **round down to int**

#### Happiness quick actions UX
- Keep actions conditional, but move to a clearer “bottom” placement.

#### Radio rules
- Backend must enforce: **manual recruit requires at least one dweller assigned to any radio room in the vault**.
- Recruitment cost display: source must be the **radio stats response**.

---

## Scope

### IN
- Hotkey handling changes in VaultView + SidePanel.
- Happiness UI action placement improvements.
- Radio backend validation + UI messaging.
- Room destroy refund + UI caps refresh.
- Automated tests (backend + frontend).

### OUT (guardrails)
- No schema/migration to persist historical “price paid”.
- No broad hotkey system rewrite (only adjust the relevant handlers).
- No redesign of happiness system logic (only UI affordances/placement).

---

## Verification Strategy

### Backend
- Commands:
  - `cd backend && uv run pytest app/tests/`

### Frontend
- Commands:
  - `cd frontend && pnpm test`
  - `cd frontend && pnpm run build`

---

## Execution Strategy (Waves)

**Wave 1 (parallel):**
- A) Hotkey fix (VaultView + SidePanel) + frontend tests
- B) Happiness quick-actions placement + frontend tests
- C) Radio cost + gating (backend + frontend) + tests

**Wave 2 (after Wave 1):**
- D) Room destroy refund (backend) + UI refresh caps + tests

---

## TODOs

> Each task includes references (what to edit) and acceptance criteria (automated).

### 1) Fix Build/Construction hotkey for RU layout + avoid Ctrl/Cmd+B conflicts

**What to do**
- Update build-mode toggle in `VaultView` to use layout-independent `KeyboardEvent.code`:
  - Replace `e.key.toLowerCase() === 'b'` with `e.code === 'KeyB'`.
- Add guards in `VaultView`:
  - ignore if `e.defaultPrevented`.
  - ignore if `e.ctrlKey || e.metaKey || e.altKey`.
  - ignore if target is `input`, `textarea`, or `contenteditable`.
- Update SidePanel Ctrl/Cmd+B to use `e.code === 'KeyB'`.
- Add the same “editable target” guard to SidePanel before toggling, so Ctrl/Cmd+B doesn’t hijack text editing.

**References**
- `frontend/src/modules/vault/views/VaultView.vue` (keyboard shortcuts): lines ~201–220 show `handleKeyPress`.
- `frontend/src/core/components/common/SidePanel.vue` (keyboard shortcuts): lines ~127–146 show Ctrl/Cmd+B logic.

**Acceptance Criteria**
- Frontend unit test(s): dispatch `keydown` with `{ code:'KeyB', key:'и' }` toggles build mode.
- Dispatch `{ code:'KeyB', ctrlKey:true }` toggles SidePanel only, does **not** toggle build mode.
- `cd frontend && pnpm test` passes.

---

### 2) Happiness page: make “bottom buttons” visible/understandable (keep conditional)

**What to do**
- Move the “Quick Actions” UI out of the scrollable main content into a clearer bottom placement.
  - Preferred: render “Quick Actions” in `UCard` footer slot (`UCard` supports `#footer`).
  - Keep buttons conditional (only render buttons that apply), but ensure:
    - The footer area is present when there are negative modifiers.
    - When there are **no** actions, show a small footer hint like “No actions needed right now” (not a button).

**References**
- `frontend/src/modules/vault/views/HappinessView.vue` (layout + where dashboard is mounted).
- `frontend/src/modules/vault/components/HappinessDashboard.vue`:
  - `hasNegativeModifiers` computed
  - "Quick Actions" section currently gated.
- `frontend/src/core/components/ui/UCard.vue` supports `#footer`.

**Acceptance Criteria**
- Frontend unit/component test renders HappinessDashboard with:
  - negative modifiers → footer action section visible and buttons appear.
  - no negative modifiers → footer shows hint (or no footer) per chosen implementation, but UX is explicit (no empty mystery).
- `cd frontend && pnpm test` passes.

---

### 3) Radio recruitment: enforce “must have assigned dwellers” + fix UI message + ensure cost consistency

#### 3a) Backend: manual recruit requires staffed radio room

**What to do**
- In `RadioService.manual_recruit`, after fetching radio rooms, verify that at least one dweller has `Dweller.room_id` equal to any radio room id.
- If none assigned, raise `ValueError` with a specific message (stable string) e.g.:
  - `"No residents assigned to radio room"`
- Ensure this applies to manual recruit endpoint (`POST /api/v1/radio/vault/{vault_id}/recruit`).

**References**
- `backend/app/services/radio_service.py` `manual_recruit(...)` around lines ~186–240.
- `backend/app/api/v1/endpoints/radio.py` manual recruit endpoint.

**Acceptance Criteria**
- Backend test:
  - Create vault + radio room + zero assigned dwellers → POST recruit returns HTTP 400 with detail containing the chosen message.
  - Assign dweller to radio room → POST recruit succeeds.

#### 3b) Frontend: show clear info + unify recruitment cost display

**What to do**
- UI messaging:
  - In `RoomDetailModal.vue` radio controls: when `assignedDwellers.length === 0`, render inline info (`UAlert` or existing pattern) that explains why recruiting is disabled.
  - In `RadioStatsPanel.vue`: if backend now enforces staffing, show toast error from API; optionally pre-empt with a note if stats include “has_staffed_radio” (if added).
- Cost display:
  - Ensure cost uses `stats.manual_cost_caps` everywhere.
  - Audit `RoomDetailModal.vue` for any hardcoded/manual cost and replace with `manual_cost_caps` from radio stats (fetch or pass down).
  - (If RoomDetailModal can’t easily access radio stats): add a small store getter that exposes `manual_cost_caps` and ensure it is loaded when opening radio controls.

**References**
- `frontend/src/modules/radio/components/RadioStatsPanel.vue` uses `stats.manual_cost_caps` (lines ~201–216).
- `frontend/src/modules/radio/stores/radio.ts` fetches stats from `/api/v1/radio/vault/${vaultId}/stats`.
- `frontend/src/modules/rooms/components/RoomDetailModal.vue` (radio controls + recruit button state).
- Backend schema already includes `manual_cost_caps`: `backend/app/schemas/radio.py`.

**Acceptance Criteria**
- Frontend tests assert cost label matches mocked `manual_cost_caps`.
- Backend + frontend integrated behavior: UI shows message when no dwellers assigned; attempting recruit returns 400 and toast shows error.
- `cd frontend && pnpm test` passes.

---

### 4) Room destroy refund: 50% incl upgrades + incremental (approx) + refresh caps in UI

#### 4a) Backend refund calculation

**What to do**
- Update `backend/app/crud/room.py`:
  - Replace `DESTROY_ROOM_REWARD = 0.2` behavior.
  - Compute refundable_total as:
    - `base_cost` (required)
    - + `incremental_cost` (if present)
    - + applied upgrades by tier (`t2_upgrade_cost`, `t3_upgrade_cost` if present and tier reached)
  - `refund = floor(0.5 * refundable_total)` (ensure int).
  - Deposit caps using `vault_crud.deposit_caps(..., amount=refund)`.
- Consider updating the UI copy “partial refund” to “50% refund” (optional).

**References**
- `backend/app/crud/room.py`:
  - `DESTROY_ROOM_REWARD = 0.2` line ~18.
  - `destroy(...)` lines ~241+.
- `backend/app/crud/vault.py` deposit/withdraw helpers.

**Acceptance Criteria**
- Backend test builds room with known costs, upgrades it to tier 2 or 3, destroys it, and asserts caps delta equals refund formula.
- `cd backend && uv run pytest app/tests/` passes.

#### 4b) Frontend: refresh vault caps after destroy

**What to do**
- In `frontend/src/modules/rooms/stores/room.ts`, after successful destroy, refresh vault like build/upgrade do.
  - This requires passing `vaultId` into `destroyRoom` or deriving it; match existing patterns.
- Ensure `RoomDetailModal.handleDestroy` has vaultId available and calls store accordingly.

**References**
- `frontend/src/modules/rooms/stores/room.ts`:
  - `buildRoom` refreshes vault
  - `destroyRoom` currently does not.
- `frontend/src/modules/rooms/components/RoomDetailModal.vue` destroy handler.

**Acceptance Criteria**
- Frontend store test asserts `vaultStore.refreshVault` called on destroy.
- `cd frontend && pnpm test` passes.

---

## Commit Strategy

Prefer 2–3 atomic commits:
1) `fix(hotkeys): make build mode toggle layout-independent`
2) `fix(happiness): clarify quick actions placement`
3) `fix(radio,rooms): enforce recruitment staffing + 50% destroy refund`

---

## Success Criteria

- Build hotkey works on RU layout (via `code`-based tests).
- Happiness page no longer feels like it’s “missing buttons”.
- Radio recruitment blocked (backend) if no staff; UI clearly explains.
- Recruitment cost shown consistently from stats.
- Destroy refund uses new formula; caps update in UI immediately.
- All tests + builds pass:
  - `cd backend && uv run pytest app/tests/`
  - `cd frontend && pnpm test && pnpm run build`
