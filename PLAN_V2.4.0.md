# Implementation Plan: v2.4.0 - Critical Bug Fixes

**Version:** 2.4.0
**Branch:** feat/v2.4.0
**Focus:** Critical bug fixes and vault management improvements

---

## 🎯 Objectives

Fix critical bugs affecting vault building mechanics, room management, and dweller systems.

---

## 🐛 Critical Bug Fixes

### 1. Vault Door Protection
**Issue:** Can remove vault door and build multiple vault doors (not intended)

**Root Cause:** No validation preventing vault door removal or duplicate creation

**Fix:**
- Backend: Add validation in room destroy endpoint to prevent vault door removal
- Backend: Add validation in room build endpoint to prevent multiple vault doors
- Frontend: Disable destroy button for vault door in UI
- Add room type check: `room_type.name == "Vault Door"`

**Files:**
- `backend/app/api/v1/endpoints/room.py` - Add validation
- `backend/app/services/room_service.py` - Add business logic checks
- `frontend/src/modules/rooms/components/RoomDetailModal.vue` - Disable UI

---

### 2. Elevator Level Access Control
**Issue:** Make elevators give access to level and prevent removal when rooms exist on that level

**Root Cause:** No level access validation or dependency checking

**Fix:**
- Backend: Track which levels have rooms (excluding elevators)
- Backend: Prevent elevator removal if it's the only access to a level with rooms
- Add validation: Check if any rooms exist on levels that would become inaccessible
- Frontend: Show warning/disable delete for essential elevators

**Files:**
- `backend/app/api/v1/endpoints/room.py` - Add elevator removal validation
- `backend/app/services/room_service.py` - Add level access logic
- `backend/app/crud/room.py` - Add helper to check level dependencies

---

### 3. Thumbnail URL Protocol Fix
**Issue:** Thumbnails have `http://` before URL (likely double protocol)

**Root Cause:** Backend or frontend adding protocol when URL already has one

**Fix:**
- Find where image URLs are constructed
- Remove hardcoded `http://` prefix
- Use URL as-is if it already has protocol
- Validate URLs properly

**Files:**
- Search: `grep -r "http://" --include="*.ts" --include="*.vue" --include="*.py"`
- Likely: Frontend image components or backend serializers

---

### 4. Living Quarters Max Dwellers Recalculation
**Issue:** Max dwellers not recalculated when living rooms are built/upgraded

**Root Cause:** Vault capacity not updated after room operations

**Fix:**
- Backend: Add recalculation trigger after room build/upgrade/destroy
- Formula: Sum all living quarters capacities
- Update `vault.max_dwellers` field
- Add service method: `recalculate_vault_capacity(vault_id)`

**Files:**
- `backend/app/services/vault_service.py` - Add recalculation method
- `backend/app/api/v1/endpoints/room.py` - Call after room operations
- Test: Verify capacity updates correctly

---

### 5. Production Room Resource Capacity Bug
**Issue:** Max resources (power/food/water) not recalculated on production room builds

**Root Cause:** Same as #4 - missing recalculation trigger

**Fix:**
- Backend: Recalculate `max_power`, `max_food`, `max_water` after room operations
- Formula: Sum all production room capacities by type
- Call recalculation after build/upgrade/destroy
- Ensure capacity formulas are correct

**Files:**
- `backend/app/services/vault_service.py` - Add resource recalculation
- `backend/app/api/v1/endpoints/room.py` - Call after operations
- Verify room capacity formulas in room templates

---

### 6. Living Space Display
**Issue:** No cap of living space shown on UI

**Root Cause:** Missing display of `current_dwellers / max_dwellers` in vault UI

**Fix:**
- Frontend: Add living space indicator to vault dashboard
- Show: `X / Y Dwellers` with progress bar
- Highlight when at/near capacity
- Use vault store data: `vault.dwellers_count` and `vault.max_dwellers`

**Files:**
- `frontend/src/modules/vault/components/VaultStats.vue` (or similar)
- Add to vault overview dashboard

---

### 7. Build Mode State Management
**Issue:** Build mode doesn't change to cancel building on room built

**Root Cause:** Build mode state not reset after successful room creation

**Fix:**
- Frontend: Reset build mode state after room is successfully created
- Emit event or watch for room creation success
- Set `buildMode` to null or `BuildMode.NORMAL`
- Clear selected room template

**Files:**
- `frontend/src/modules/rooms/stores/room.ts` - Reset state after build
- `frontend/src/modules/vault/views/VaultView.vue` - Handle build complete

---

### 8. Negative Dweller Experience Bug
**Issue:** Weird bug with dweller exp lower than 0

**Root Cause:** Experience calculation allowing negative values

**Fix:**
- Backend: Add validation `ge=0` to dweller experience field
- Backend: Clamp experience to minimum 0 in all calculations
- Find where experience is modified (exploration, room work, events)
- Add database constraint: `CHECK (experience >= 0)`
- Migration: Fix existing negative values to 0

**Files:**
- `backend/app/models/dweller.py` - Add validation
- `backend/app/services/dweller_service.py` - Clamp experience
- Migration: Update negative values + add constraint

---

### 9. Large Room Build 500 Error
**Issue:** Error 500 on building rooms of big size

**Root Cause:** Validation or database error when room size exceeds limits

**Fix:**
- Backend: Add proper validation for room size before building
- Check: Room template max size, grid bounds, overlapping rooms
- Return 400 error with message instead of 500
- Add try-except with proper error handling
- Log error details for debugging

**Files:**
- `backend/app/api/v1/endpoints/room.py` - Add size validation
- `backend/app/services/room_service.py` - Validate placement
- Improve error handling and logging

---

## 📋 Implementation Steps

### Phase 1: Backend Validation & Logic (Priority 1)
1. Vault door protection (#1)
2. Elevator access control (#2)
3. Negative experience fix (#8)
4. Room size validation (#9)

### Phase 2: Capacity Recalculation (Priority 2)
5. Living quarters recalculation (#4)
6. Production room recalculation (#5)

### Phase 3: UI & Polish (Priority 3)
7. Thumbnail URL fix (#3)
8. Living space display (#6)
9. Build mode state management (#7)

---

## ✅ Testing Requirements

**Backend Tests:**
- Unit tests for all validation logic
- Test vault door cannot be removed
- Test elevator removal with dependencies
- Test negative experience clamping
- Test room size validation
- Test capacity recalculation formulas

**Frontend Tests:**
- Test build mode state resets
- Test living space display accuracy
- Test vault door UI disabled

**Manual Testing:**
- Build and destroy various rooms
- Verify capacities update correctly
- Test elevator scenarios
- Verify no 500 errors on large rooms

---

## 📊 Success Criteria

- ✅ Cannot remove vault door
- ✅ Cannot build multiple vault doors
- ✅ Elevators protect level access
- ✅ Thumbnails display correctly (no double http://)
- ✅ Max dwellers updates when living quarters change
- ✅ Max resources update when production rooms change
- ✅ Living space shown in UI
- ✅ Build mode resets after building
- ✅ No negative dweller experience possible
- ✅ Large rooms build without 500 errors
- ✅ All tests passing (>80% coverage)

---

## 🔧 Technical Notes

**Room Type Constants:**
```python
VAULT_DOOR = "Vault Door"
ELEVATOR = "Elevator"
LIVING_QUARTERS = ["Living Quarters", "Overseer's Office"]
PRODUCTION_POWER = ["Power Generator", "Nuclear Reactor"]
PRODUCTION_FOOD = ["Diner", "Garden"]
PRODUCTION_WATER = ["Water Treatment", "Water Purification"]
```

**Capacity Recalculation Trigger Points:**
- After room build (success)
- After room upgrade
- After room destroy
- On vault load (safety check)

**Database Constraints:**
```sql
ALTER TABLE dweller ADD CONSTRAINT dweller_experience_positive CHECK (experience >= 0);
```

---

*Plan created: 2026-01-24*
*Target completion: v2.4.0 release*
