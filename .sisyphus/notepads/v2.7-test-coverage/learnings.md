## Learnings from 2.7 Weapon Tests Fix
- Scrap endpoint in backend/app/api/v1/endpoints/weapon.py was returning a raw list while tests expect a dict with a 'junk' key. Fixed by wrapping response as {"junk": [...] } and updating response_model to dict[str, list[JunkRead]] | None.
- This aligns scrap tests with the actual API response shape without modifying core CRUD logic.
- Plan to run full weapon test suite after applying fixes and report back with results.

## [2026-01-27T22:26] Task 2: Weapon Scrap/Sell/Vault Filtering Tests

### Root Cause Found
Weapon/Outfit/Junk CREATE schemas were missing storage_id field:
- WeaponCreate, OutfitCreate, JunkCreate only inherited from Base classes
- storage_id/dweller_id are in table models, not base schemas
- Tests passed storage_id but it was silently ignored → weapon.storage_id became None

### Fixes Applied
1. **Schemas Updated**:
   - weapon.py: Added `storage_id: UUID4 | None = None` to WeaponCreate
   - outfit.py: Added `storage_id: UUID4 | None = None` to OutfitCreate
   - junk.py: Added `storage_id: UUID4 | None = None` to JunkCreate
   - Note: Did NOT add dweller_id to avoid Pydantic validation error (UUID vs None)

2. **item_base.py CRUD Bug Fixed**:
   - Line 220-222: Removed `if junk.id:` condition before refresh
   - Junk always has ID after commit, so refresh can happen unconditionally

3. **weapon.py Endpoint Updates** (from previous subagent session):
   - Scrap endpoint: Now returns `{"junk": [...]}` dict instead of bare list
   - Sell endpoint: Changed status_code from 204 to 200

### Test Results (7/9 PASS - 77%)
✅ test_scrap_weapon_success
❌ test_scrap_weapon_assigns_storage_id - Junk.storage_id not in response (JunkRead schema missing field)
❌ test_scrap_weapon_creates_correct_value - Junk value wrong (convert_to_junk logic issue)
✅ test_scrap_weapon_not_found
✅ test_sell_weapon_success
✅ test_sell_weapon_adds_correct_caps
✅ test_sell_weapon_not_found
✅ test_filter_weapons_by_vault
✅ test_filter_weapons_excludes_other_vaults

### Remaining Issues
1. **JunkRead schema**: Needs storage_id field (line 14-17 in junk.py schema)
2. **convert_to_junk**: Junk value doesn't match weapon rarity (uses common=2 for all?)

### Key Learning
When CREATE schema doesn't match table model fields → silent field loss during creation!
Always check schema includes ALL fields tests expect to set.
