# Soft Delete Feature

> **Status:** ✅ Implemented (v2.6)
> **Last Updated:** 2026-01-26

## Overview

Soft delete functionality has been implemented for Users and Dwellers to preserve data integrity and enable future data reuse, particularly for AI-generated content like dweller backstories and visual attributes.

## What is Soft Delete?

Instead of permanently removing records from the database, soft delete marks them as deleted using flags:
- `is_deleted` (boolean): Indicates if the record is deleted
- `deleted_at` (timestamp): Records when the deletion occurred

Soft-deleted records are hidden from normal queries but remain in the database for potential recovery or future reuse.

## Implemented Models

### User
- Soft deletes preserve user account data
- Prevents accidental data loss
- Allows account recovery/restoration

### Dweller
- Soft deletes preserve AI-generated content (names, bios, visual attributes)
- **Future Goal:** Recycle dwellers with rich backstories for new vaults
- Maintains referential integrity with relationships

## Database Changes

### Migration: `3a4b32b46a8b_add_soft_delete_to_users_and_dwellers`

Added columns to `user` and `dweller` tables:
```sql
-- Added to both tables
is_deleted BOOLEAN NOT NULL DEFAULT false
deleted_at TIMESTAMP NULL
```

Indexes created on `is_deleted` for query performance.

## API Endpoints

### Dweller Soft Delete Endpoints

#### Delete Dweller (Soft by Default)
```http
DELETE /api/v1/dwellers/{dweller_id}?hard_delete=false
```
- Default behavior: Soft delete (preserves data)
- Use `hard_delete=true` for permanent deletion
- Requires dweller access permission

#### Explicit Soft Delete
```http
POST /api/v1/dwellers/{dweller_id}/soft-delete
```
- Explicitly marks dweller as deleted
- Preserves all dweller data

#### Restore Dweller
```http
POST /api/v1/dwellers/{dweller_id}/restore
```
- Restores a soft-deleted dweller
- Clears `is_deleted` flag and `deleted_at` timestamp

#### List Deleted Dwellers
```http
GET /api/v1/dwellers/vault/{vault_id}/deleted?skip=0&limit=100
```
- Returns soft-deleted dwellers for a vault
- Useful for recovery operations

## CRUD Operations

### Automatic Filtering

All standard CRUD read operations automatically exclude soft-deleted records:

```python
# These automatically filter out soft-deleted records
await crud.dweller.get(db_session, dweller_id)
await crud.dweller.get_multi(db_session)
await crud.dweller.get_multi_by_vault(db_session, vault_id)
```

### Including Deleted Records

To include soft-deleted records, use the `include_deleted` parameter:

```python
# Include soft-deleted records
await crud.dweller.get(db_session, dweller_id, include_deleted=True)
await crud.dweller.get_multi(db_session, include_deleted=True)
```

### Soft Delete Methods

```python
# Soft delete a dweller
await crud.dweller.soft_delete(db_session, dweller_id)

# Restore a dweller
await crud.dweller.restore(db_session, dweller_id)

# Get deleted records only
await crud.dweller.get_deleted(db_session, skip=0, limit=100)

# Hard delete (permanent)
await crud.dweller.delete(db_session, dweller_id, soft=False)
```

## Code Examples

### Backend: Soft Delete a Dweller

```python
from app import crud
from app.db.session import get_async_session

async def soft_delete_dweller_example(dweller_id: UUID4):
    async with get_async_session() as db:
        # Soft delete
        deleted_dweller = await crud.dweller.soft_delete(db, dweller_id)
        print(f"Deleted: {deleted_dweller.is_deleted}")  # True
        print(f"Deleted at: {deleted_dweller.deleted_at}")  # Timestamp
```

### Backend: Restore a Dweller

```python
async def restore_dweller_example(dweller_id: UUID4):
    async with get_async_session() as db:
        # Restore
        restored_dweller = await crud.dweller.restore(db, dweller_id)
        print(f"Deleted: {restored_dweller.is_deleted}")  # False
        print(f"Deleted at: {restored_dweller.deleted_at}")  # None
```

### Frontend: API Calls

```typescript
// Soft delete a dweller (default behavior)
await apiClient.delete(`/api/v1/dwellers/${dwellerId}`)

// Hard delete a dweller
await apiClient.delete(`/api/v1/dwellers/${dwellerId}?hard_delete=true`)

// Restore a dweller
await apiClient.post(`/api/v1/dwellers/${dwellerId}/restore`)

// Get deleted dwellers for a vault
const deletedDwellers = await apiClient.get(
  `/api/v1/dwellers/vault/${vaultId}/deleted`
)
```

## Future: Dweller Recycling (NOT YET IMPLEMENTED)

The soft delete infrastructure is in place to support future dweller recycling features:

### Planned Features
- **Dweller Pool:** Reuse soft-deleted dwellers with rich AI-generated content
- **Content Preservation:** Names, backstories, visual attributes preserved
- **Stats Reset:** Game stats reset while keeping personality/appearance
- **Cross-Vault Reuse:** Dwellers from deleted vaults can appear in new vaults

### Recycling Service
A skeleton service exists at `app/services/dweller_recycling_service.py` marked as "NOT YET IMPLEMENTED"

Planned methods:
- `get_recyclable_dwellers()` - Find dwellers eligible for recycling
- `recycle_dweller_for_vault()` - Assign recycled dweller to new vault
- `bulk_recycle_dwellers()` - Recycle multiple dwellers at once
- `permanently_delete_old_dwellers()` - Cleanup very old soft-deleted records
- `get_recycling_stats()` - Statistics on recyclable dweller pool

## Implementation Details

### SoftDeleteMixin

Base mixin class in `app/models/base.py`:

```python
class SoftDeleteMixin(SQLModel):
    is_deleted: bool = Field(default=False, index=True)
    deleted_at: datetime | None = Field(default=None)

    def soft_delete(self):
        """Marks the object as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self):
        """Restores the object if it was soft-deleted."""
        self.is_deleted = False
        self.deleted_at = None
```

### Model Updates

Both `User` and `Dweller` models now inherit from `SoftDeleteMixin`:

```python
class User(BaseUUIDModel, UserBase, TimeStampMixin, SoftDeleteMixin, table=True):
    # ... user fields

class Dweller(BaseUUIDModel, DwellerBase, TimeStampMixin, SoftDeleteMixin, table=True):
    # ... dweller fields
```

### CRUD Base Class Updates

Enhanced `CRUDBase` with soft delete support:
- All `get*` methods support `include_deleted` parameter
- New `soft_delete()` method for explicit soft deletion
- New `restore()` method for undeleting records
- New `get_deleted()` method for retrieving only deleted records
- Modified `delete()` method with `soft` parameter (defaults to `True`)

## Testing

Existing tests continue to pass as soft delete is the default behavior.

### Test Soft Delete Behavior

```python
async def test_soft_delete_dweller():
    # Create and soft delete
    dweller = await crud.dweller.create(db, dweller_data)
    await crud.dweller.soft_delete(db, dweller.id)

    # Should not appear in normal queries
    result = await crud.dweller.get_multi(db)
    assert dweller.id not in [d.id for d in result]

    # Should appear when including deleted
    result = await crud.dweller.get_multi(db, include_deleted=True)
    assert dweller.id in [d.id for d in result]

    # Restore and verify
    await crud.dweller.restore(db, dweller.id)
    result = await crud.dweller.get_multi(db)
    assert dweller.id in [d.id for d in result]
```

## Benefits

1. **Data Preservation:** AI-generated content is expensive to create
2. **Undo Capability:** Users can recover accidentally deleted dwellers
3. **Audit Trail:** `deleted_at` timestamp provides deletion history
4. **Future Recycling:** Foundation for content reuse across vaults
5. **Safe Operations:** Default soft delete prevents accidental data loss

## Migration Guide

### For Existing Data

All existing users and dwellers automatically have:
- `is_deleted = false`
- `deleted_at = null`

No data migration required - the migration sets sensible defaults.

### For Developers

When querying dwellers or users:
- Normal queries automatically exclude deleted records
- Use `include_deleted=True` when you need to see deleted records
- Use `soft_delete()` instead of `delete()` when appropriate
- Remember to check `is_deleted` flag in business logic if needed

## Performance Considerations

- Indexes on `is_deleted` ensure fast filtering
- Soft-deleted records do consume database space
- Consider implementing periodic cleanup of very old soft-deleted records (future feature)

## Related Files

- Models: `backend/app/models/user.py`, `backend/app/models/dweller.py`
- Base: `backend/app/models/base.py`
- CRUD: `backend/app/crud/base.py`, `backend/app/crud/user.py`, `backend/app/crud/dweller.py`
- Endpoints: `backend/app/api/v1/endpoints/dweller.py`
- Migration: `backend/app/alembic/versions/2026_01_26_2028-3a4b32b46a8b_add_soft_delete_to_users_and_dwellers.py`
- Future Service: `backend/app/services/dweller_recycling_service.py`

---

*Feature implemented as part of v2.6 update - 2026-01-26*
