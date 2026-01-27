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
