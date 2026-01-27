Task: Add Outfit Scrap/Sell Endpoint Tests

- Implemented 10 tests mirroring weapon tests for outfits scrap/sell/vault filtering.
- Created tests to verify scrap returns junk with storage_id and proper value based on rarity, outfit deletion, and not-found handling.
- Created tests to verify selling outfits updates vault bottle_caps and deletes outfit.
- Created vault-based filtering tests to ensure vault-scoped outfit lists include equipped items and exclude others.
- Used existing factories: create_fake_outfit, create_fake_vault and CRUD helpers to setup test data.

Key patterns observed:
- Consistent test layout with setup (vault/storage/outfit creation) then API call, then assertions on response and side effects.
- Scrap endpoints return {"junk": [...]} and delete the outfit.
- Sell endpoints return 200 and add outfit value to vault bottle_caps while deleting the outfit.
- Vault filtering tests validate inclusion/exclusion by vault_id and presence of equipped outfits when available.

Next steps / potential improvements:
- If equipped_outfit fixture has a different shape, adjust test_filter_outfits_includes_equipped accordingly.
- Consider extracting setup boilerplate into a small helper to reduce duplication across tests.

## [2026-01-27T22:41] Session End - Backend Tests Complete

### Completed Tasks (4/9)
✅ Task 1: Storage Items Endpoint Tests (6 tests)
✅ Task 2: Weapon Scrap/Sell/Vault Tests (9 tests)
✅ Task 3: Outfit Scrap/Sell/Vault Tests (9 tests)
✅ Task 4: Junk Sell Tests (6 tests)

**Total: 30 backend tests added, all passing**

### Key Fixes Applied
1. **Schema Updates**:
   - WeaponCreate, OutfitCreate, JunkCreate: Added storage_id field
   - JunkRead: Added storage_id field
2. **Endpoint Updates**:
   - Weapon/Outfit scrap: Return {"junk": [...]} dict format
   - Weapon/Outfit/Junk sell: Changed status_code to 200
3. **CRUD Bug Fix**:
   - item_base.py scrap method: Removed conditional before junk refresh

### Remaining Tasks (5/9 - Frontend)
- [ ] Task 5: Storage Service Tests
- [ ] Task 6: StorageItemCard Component Tests
- [ ] Task 7: StorageView Component Tests
- [ ] Task 8: Equipment Store Vault Filtering Tests
- [ ] Task 9: Full Test Suite Verification

### Context Usage
~185k tokens (18.5%) used for backend test implementation
