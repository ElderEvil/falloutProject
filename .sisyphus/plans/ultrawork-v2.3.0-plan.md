# v2.3.0 Ultrawork Implementation Plan

**Status:** Ready for Execution
**Created:** 2026-01-23
**Scope:** P0 Storage Fix + P1 Pregnancy Debug
**Estimated:** 14-16 hours

---

## Phase 1: P0 - Storage Validation (8h)

### Task P0-1: Create Storage CRUD Module (1h)

**New File:** `backend/app/crud/storage.py`

Functions needed:
- `count_storage_items(db, storage_id)` - Count weapons + outfits + junk
- `get_available_space(db, storage_id)` - max_space - used_space
- `update_used_space(db, storage_id)` - Sync used_space with actual count

### Task P0-2: Add Validation to Coordinator (3h)

**Modify:** `backend/app/services/exploration/coordinator.py`

Changes to `_transfer_loot_to_storage()` method (line 254):
1. Check available space before transfer
2. Sort loot by rarity (legendary > rare > uncommon > common)
3. Transfer items until space full
4. Track transferred vs overflow items
5. Log all operations (info: transfers, warning: overflows)
6. Update storage.used_space after transfer

Return: `{"transferred": [...], "overflow": [...]}`

### Task P0-3: Add Storage API Endpoint (2h)

**New Files:**
- `backend/app/api/v1/endpoints/storage.py` - Router with GET /vault/{id}/space
- `backend/app/schemas/storage.py` - StorageSpaceResponse schema

**Modify:**
- `backend/app/api/v1/api.py` - Register storage router
- `backend/app/schemas/exploration_event.py` - Add overflow_items to RewardsSchema

Response: `{used_space, max_space, available_space, utilization_pct}`

### Task P0-4: Add Storage Tests (2h)

**New Files:**
- `backend/app/tests/test_services/test_exploration_coordinator.py`
- `backend/app/tests/test_api/test_storage.py`

Tests:
- test_transfer_respects_storage_limits
- test_transfer_prioritizes_rare_items
- test_transfer_logs_overflow_warning
- test_get_storage_space_info

---

## Phase 2: P1 - Pregnancy Debug (6h)

### Task P1-1: Add Debug Config (30min)

**Modify:** `backend/app/core/game_config.py`

Add to BreedingConfig:
- debug_mode: bool
- debug_force_conception: bool
- debug_instant_pregnancy: bool
- debug_instant_growth: bool
- debug_conception_rate_multiplier: float

Load from env vars: BREEDING_DEBUG_*

### Task P1-2: Add Debug Logging (2h)

**Modify:** `backend/app/services/breeding_service.py`

Add logging to `check_for_conception()`:
- Log eligible couples count
- Log each conception check (dweller IDs, chance, roll, result)
- Log failed attempts with reasons
- Log debug mode overrides

### Task P1-3: Add Admin Debug Endpoints (2h)

**Modify:** `backend/app/api/v1/endpoints/pregnancy.py`

Add endpoints (require CurrentSuperuser + debug_mode):
- POST /debug/force-conception?female_id=&male_id=
- POST /{pregnancy_id}/debug/accelerate?hours=N

### Task P1-4: Add Debug Tests (1.5h)

**Modify:**
- `backend/app/tests/test_services/test_breeding_service.py`
- `backend/app/tests/test_api/test_pregnancy.py`

Tests:
- test_force_conception_in_debug_mode
- test_debug_endpoints_require_admin
- test_debug_endpoints_require_debug_mode_enabled
- test_accelerate_pregnancy

### Task P1-5: Update Env Example (5min)

**Modify:** `backend/.env.example`

Add section:
```
# Breeding Debug
BREEDING_DEBUG_MODE=false
BREEDING_DEBUG_FORCE_CONCEPTION=false
BREEDING_DEBUG_INSTANT_PREGNANCY=false
BREEDING_DEBUG_INSTANT_GROWTH=false
BREEDING_DEBUG_CONCEPTION_RATE=1.0
```

---

## Execution Order

1. P0-1 (storage CRUD) - Foundation
2. P0-2 (coordinator) - Core logic
3. P0-3 (API) - Exposure
4. P0-4 (tests) - Validation
5. P1-1 (config) - Foundation
6. P1-2 (logging) - Observability
7. P1-3 (endpoints) - Debug tools
8. P1-4 (tests) - Validation
9. P1-5 (env) - Documentation

**Dependencies:**
- P0-2 depends on P0-1
- P0-3 depends on P0-2
- P0-4 depends on P0-2, P0-3
- P1-2 depends on P1-1
- P1-3 depends on P1-1
- P1-4 depends on P1-2, P1-3

---

## Files Summary

**New:** 4 files
- backend/app/crud/storage.py
- backend/app/api/v1/endpoints/storage.py
- backend/app/schemas/storage.py
- backend/app/tests/test_services/test_exploration_coordinator.py

**Modified:** 8 files
- backend/app/services/exploration/coordinator.py
- backend/app/schemas/exploration_event.py
- backend/app/api/v1/api.py
- backend/app/core/game_config.py
- backend/app/services/breeding_service.py
- backend/app/api/v1/endpoints/pregnancy.py
- backend/app/tests/test_api/test_storage.py
- backend/.env.example

**Tests Added:** ~10-12 new test functions

---

*Plan ready for execution. Exit plan mode to implement.*
