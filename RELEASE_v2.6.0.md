# Release v2.6.0 - Soft Delete Implementation

**Release Date:** 2026-01-26
**Branch:** feat/v2.6-ux-improvements
**Status:** Ready for Testing

---

## 🎯 Overview

Version 2.6.0 introduces comprehensive **soft delete functionality** for Users, Dwellers, and Vaults. This major feature enables data preservation (especially expensive AI-generated content) while providing standard deletion capabilities.

---

## ✨ New Features

### Soft Delete System

**What is Soft Delete?**
Instead of permanently removing records, soft delete marks them as deleted using flags:
- `is_deleted` (boolean) - Indicates deletion status
- `deleted_at` (timestamp) - Records deletion time

Soft-deleted records are hidden from normal queries but preserved in the database for recovery or future reuse.

**Models with Soft Delete:**
- ✅ User
- ✅ Dweller
- ✅ Vault

---

## 🔧 Technical Changes

### Database

**Migrations Applied:**
1. `3a4b32b46a8b` - Add soft delete to users and dwellers
2. `7dfe123803d6` - Add soft delete to vaults

**Schema Changes:**
```sql
-- Added to user, dweller, and vault tables
is_deleted BOOLEAN NOT NULL DEFAULT false
deleted_at TIMESTAMP NULL
CREATE INDEX ON table_name (is_deleted)
```

### Backend

**Models:**
- Added `SoftDeleteMixin` to base models with:
  - `soft_delete()` method - Marks record as deleted with timestamp
  - `restore()` method - Unmarks record and clears timestamp

**CRUD Layer:**
- All read operations now filter soft-deleted records by default
- New `include_deleted` parameter for all `get*()` methods
- New methods:
  - `soft_delete(db, id)` - Explicitly soft delete
  - `restore(db, id)` - Restore soft-deleted record
  - `get_deleted(db, skip, limit)` - List only deleted records
- Modified `delete(db, id, soft=True)` - Soft delete by default

**API Endpoints:**

Dweller Endpoints:
```
DELETE /api/v1/dwellers/{id}?hard_delete=false
POST   /api/v1/dwellers/{id}/soft-delete
POST   /api/v1/dwellers/{id}/restore
GET    /api/v1/dwellers/vault/{vault_id}/deleted
```

Vault Endpoints:
```
DELETE /api/v1/vaults/{id}?hard_delete=false
```

**Default Behavior:**
- Soft delete is the default for all DELETE operations
- Hard delete requires explicit `hard_delete=true` parameter
- Users are protected from accidental permanent data loss

### Frontend

**Vault Store Updates:**
- `deleteVault()` now supports `hardDelete` parameter
- Console logging for deletion feedback:
  - Soft delete: "Vault soft deleted - Data preserved for potential recovery"
  - Hard delete: "Vault permanently deleted"
  - Error: "Failed to delete vault"

---

## 📊 Benefits

1. **Data Preservation** - AI-generated dweller content (names, bios, backstories) is expensive to create
2. **Undo Capability** - Users can recover accidentally deleted records
3. **Audit Trail** - `deleted_at` timestamp provides deletion history
4. **Future Recycling** - Foundation for reusing dweller content across vaults
5. **Safe by Default** - Prevents accidental permanent data loss

---

## 🔮 Future Features (Planned)

### Dweller Recycling Service
A skeleton service exists at `backend/app/services/dweller_recycling_service.py` marked as **NOT YET IMPLEMENTED**.

**Planned Features:**
- Reuse soft-deleted dwellers with rich AI-generated content in new vaults
- Reset game stats while preserving personality/backstory/appearance
- Cross-vault dweller pool for content efficiency
- Bulk recycling operations
- Automatic cleanup of very old soft-deleted records

**Planned Methods:**
- `get_recyclable_dwellers()` - Find eligible dwellers
- `recycle_dweller_for_vault()` - Assign to new vault
- `bulk_recycle_dwellers()` - Recycle multiple at once
- `permanently_delete_old_dwellers()` - Cleanup operation
- `get_recycling_stats()` - Analytics on recycling pool

**TODO Items:**
- Auto soft-delete on dweller permanent death
- Frontend UI for viewing/restoring deleted records
- Admin panel for managing soft-deleted data

---

## 📝 Documentation

**New Documentation:**
- `docs/features/SOFT_DELETE.md` - Comprehensive feature guide
- `SOFT_DELETE_UPDATE.md` - Implementation summary

**Includes:**
- API endpoint documentation
- Code examples (backend & frontend)
- Implementation details
- Testing guidelines
- Migration guide
- Performance considerations

---

## 🧪 Testing

**Verification:**
- ✅ All 422 existing tests pass
- ✅ Migrations applied successfully (current: `7dfe123803d6`)
- ✅ Models import correctly with soft delete attributes
- ✅ CRUD operations have soft delete methods
- ✅ API endpoints import without errors
- ✅ Frontend builds successfully

**Manual Testing Required:**
- [ ] Soft delete a dweller via API
- [ ] Restore a soft-deleted dweller
- [ ] List deleted dwellers for a vault
- [ ] Soft delete a vault
- [ ] Hard delete with `hard_delete=true` parameter
- [ ] Verify soft-deleted records don't appear in normal queries
- [ ] Verify soft-deleted records appear with `include_deleted=True`

---

## 📦 Files Changed

**Total:** 17 files (1,037 insertions, 143 deletions)

**Created:**
- `backend/app/alembic/versions/2026_01_26_2028-3a4b32b46a8b_add_soft_delete_to_users_and_dwellers.py`
- `backend/app/alembic/versions/2026_01_26_2045-7dfe123803d6_add_soft_delete_to_vault.py`
- `backend/app/services/dweller_recycling_service.py` (skeleton)
- `docs/features/SOFT_DELETE.md`
- `SOFT_DELETE_UPDATE.md`
- `RELEASE_v2.5.0.md` (this file)

**Modified:**
- `backend/app/models/base.py` - Added SoftDeleteMixin
- `backend/app/models/user.py` - Added mixin
- `backend/app/models/dweller.py` - Added mixin
- `backend/app/models/vault.py` - Added mixin
- `backend/app/crud/base.py` - Soft delete methods & filtering
- `backend/app/crud/user.py` - Filter deleted users in auth
- `backend/app/crud/dweller.py` - Filter deleted dwellers
- `backend/app/crud/vault.py` - Filter deleted vaults
- `backend/app/api/v1/endpoints/dweller.py` - Soft delete endpoints
- `backend/app/api/v1/endpoints/vault.py` - Soft delete support
- `frontend/src/modules/vault/stores/vault.ts` - Console notifications

---

## 🚀 Deployment Notes

### Database Migration
```bash
cd backend
uv run alembic upgrade head
```

### Environment Variables
No new environment variables required.

### Breaking Changes
None. All changes are backward compatible.

### Performance Impact
- Minimal: Indexed `is_deleted` column ensures fast filtering
- Soft-deleted records consume database space (consider periodic cleanup)

---

## 📋 Commits

**Primary Commits:**
1. `af6d178` - feat: implement soft delete for users, dwellers, and vaults
2. `8405c97` - fix: remove vue-toastification dependency, use console logging

**Previous Merge:**
- `c02f224` - Merge origin/master into feat/v2.6-ux-improvements

---

## ⚠️ Known Issues

None currently identified.

---

## 🔐 Security Considerations

- Soft-deleted users cannot authenticate (`is_active && !is_deleted`)
- Soft-deleted records are hidden from normal queries by default
- Hard delete requires explicit parameter (reduces accidental data loss)
- No sensitive data is exposed through soft delete mechanism

---

## 📞 Support

For issues or questions:
1. Check `docs/features/SOFT_DELETE.md` for detailed documentation
2. Review `SOFT_DELETE_UPDATE.md` for implementation details
3. Check existing test coverage in `backend/app/tests/`

---

## ✅ Release Checklist

- [x] All tests passing
- [x] Migrations applied successfully
- [x] Frontend builds without errors
- [x] Code committed to branch
- [x] Documentation updated
- [ ] Manual testing completed
- [ ] Code review completed
- [ ] Ready for merge to master
- [ ] Ready for production deployment

---

**Version:** 2.6.0
**Release Type:** Feature Release
**Stability:** Stable (Ready for Testing)

---

*Built with ❤️ for the Fallout Shelter project*
