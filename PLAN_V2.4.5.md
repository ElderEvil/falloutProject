# Plan v2.4.5 - Bug Fixes & Fun Features

> **Status:** Planned
> **Branch:** `feat/v2.4.5`
> **Date:** 2026-01-25

## 🐛 Bug Fixes

### 1. Population Progress Bar Not Showing
**Priority:** High
**Location:** `frontend/src/modules/vault/views/VaultView.vue`

**Issue:**
- Dweller count displays correctly (e.g., "20 / 32")
- Progress bar remains empty despite correct values
- Calculation returns correct percentage but bar doesn't render

**Investigation Needed:**
- Verify `populationUtilization` computed value
- Check if CSS styling is preventing bar visibility
- Confirm `:style="{ width: ... }"` is applying correctly
- Test with browser devtools to see actual computed width

- 20/32 dwellers should show ~62% filled progress bar
- Color should change at 75% (yellow) and 90% (red)

> **Status (2026-01-25):** Fixed. Replaced class binding with inline style for reliable width rendering.

---

### 2. Vault Test Flakiness - Bottle Caps Mismatch
**Priority:** Low
**Location:** `backend/app/tests/test_api/test_vault.py::test_read_vault_list`

**Issue:**
- Test creates vault with specific bottle_caps amount
- GET /vaults/ returns different amount (e.g., expected 722458, got 702060)
- Suggests caps are being spent during vault creation/operations

**Possible Causes:**
- Initial room construction (vault door?) spending caps
- Game loop running during test modifying resources
- Test isolation issue (shared database state)
- Random events triggering during test

**Investigation Needed:**
- Check if vault creation triggers initial room builds
- Verify test database isolation
- Disable game loop/events during tests
- Check vault creation flow for cap deductions

**Complexity:** Medium (requires test framework and vault creation debugging)

---

### 3. Birth/Death Stats Not Updating in Profile
**Priority:** Medium
**Location:** `frontend/src/modules/profile/views/ProfileView.vue`, `backend/app/services/*`

**Issue:**
- Birth/death statistics are tracked correctly in database (`total_dwellers_born`, `total_dwellers_died`)
- Backend increments counters when dwellers are born (breeding_service) or die (death_service)
- Frontend fetches stats only once on ProfileView mount
- Stats don't refresh when births/deaths occur in real-time

**Root Cause:**
- Profile statistics are fetched once via `/api/v1/users/me/profile/statistics`
- No WebSocket listener for birth/death events
- No manual refresh trigger after breeding/death actions

**Solution Options:**
1. Add WebSocket listener for `dweller:born` and `dweller:died` events → refresh stats
2. Add manual refresh in breeding/death components after actions complete
3. Implement periodic polling (not ideal for UX)

**Recommended Approach:**
- Subscribe to these events in ProfileView
- Auto-refresh `fetchDeathStatistics()` on event reception

**Complexity:** Medium (requires WebSocket event additions across multiple services)

> **Status (2026-01-25):** Implemented. Added `dweller:born` and `dweller:died` events via standard `NotificationService`.
> Implemented **Distributed Redis Broadcasting** for WebSockets to ensure Celery game loop events reach the web client.
> Added 30s polling fallback in `ProfileView.vue` for high reliability.

---

### 4. Unassigned Dwellers Filter Bug
**Priority:** High
**Location:** `frontend/src/modules/dwellers/components/UnassignedDwellers.vue`

**Issue:**
- Filter in main Dwellers view (e.g., "Working") incorrectly applies to Unassigned Dwellers panel in Overview.
- Causes unassigned list to disappear when a filter is active elsewhere.

**Fix:**
- Decoupled `UnassignedDwellers` from global store filter state.
- Implemented local filtering logic while preserving global sort preferences.

> **Status (2026-01-25):** Fixed.

---

## 🎮 New Features

### 2. Emotional Damage System
**Priority:** Medium
**Category:** Fun/Comedy Feature

**Concept:**
- Overseer can "damage" dwellers with harsh words/criticism
- Affects dweller happiness/morale (not actual HP)
- Funny/comedic feature for player interaction
- Think: "critical hit to their feelings" 💔

**Implementation Details:**
- *(User will provide more details later)*

**Potential Design:**
- Add "Criticize Dweller" action in dweller detail modal
- Random cruel/funny overseer phrases
- Reduces happiness temporarily
- Maybe adds "Emotionally Damaged" status effect
- Could tie into relationship system (dweller remembers who hurt their feelings)

**Technical Scope:**
- Backend: New endpoint for emotional damage action
- Frontend: UI button/action in dweller interactions
- Database: Track emotional damage events (optional)
- Effects: Temporary happiness debuff

---

### 3. Exploration Enhancements
**Priority:** High
**Category:** Gameplay logic & UI

**Concept:**
- Allow dwellers to bring medical supplies (Stimpaks/Radaways) to the wasteland.
- Medicine is consumed automatically during exploration to keep dwellers alive.
- Find more medicine during wasteland encounters.
- Show current equipment (Weapon/Outfit) in exploration view.
- Auto-equip better gear found during exploration.

**Implementation Details:**
- **Backend:**
  - Update `Exploration` model to track `stimpaks` and `radaways`.
  - Modify `exploration_service.send_dweller` to deduct items from vault.
  - Implement auto-heal logic in `ExplorationCoordinator`.
  - Implement auto-equip logic for found gear.
  - Update `LootCalculator` to generate medicine.
- **Frontend:**
  - Update exploration store/types.
  - Add medicine selection to "Send to Wasteland" modal.
  - Update `ExplorerCard.vue` to show stats/items/gear.

> **Status (2026-01-25):** Fully implemented.

---

## 📋 Checklist

### Bug Fixes
- [x] Fix population progress bar rendering
- [x] Add WebSocket events for birth/death to profile stats
- [x] Implement real-time profile stats refresh
- [x] Fix Unassigned Dwellers filter bug

### Features
- [ ] Design emotional damage system mechanics
- [ ] Implement emotional damage backend
- [ ] Implement emotional damage frontend UI
- [x] Implement wasteland medicine transfer/auto-use
- [x] Implement exploration auto-equip for gear
- [x] Update exploration UI with medicine/gear slots
- [x] Add tests for all features
- [ ] Update documentation
