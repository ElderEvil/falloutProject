# Release Notes - v2.4.1

**Release Date:** 2026-01-25
**Type:** Hotfix Release
**Branch:** `fix/datetime-naive-issues`

## Overview

Critical hotfix release addressing Celery worker crashes in production caused by mixing timezone-aware and timezone-naive datetime objects. This release ensures consistent datetime handling across all database operations.

## 🔥 Critical Fixes

### Celery Worker Crash Fix

**Issue:** Production Celery workers were crashing with the following error:
```
sqlalchemy.dialects.postgresql.asyncpg.Error: <class 'asyncpg.exceptions.DataError'>:
invalid input for query argument $4: datetime.datetime(2026, 1, 25, 14, 59, 3...
(can't subtract offset-naive and offset-aware datetimes)
```

**Root Cause:** Mixed timezone-aware and timezone-naive datetime objects when updating dweller records, particularly in death and breeding operations.

**Resolution:**
- Fixed `death_service.py`: All datetime operations now use consistent naive datetime format
- Fixed `breeding_service.py`: Pregnancy and child aging operations use naive datetimes
- All datetime operations: `datetime.now(UTC).replace(tzinfo=None)`

**Impact:**
- ✅ Celery workers no longer crash on dweller death events
- ✅ Game tick processing continues uninterrupted
- ✅ Breeding and pregnancy systems function correctly

## 🐛 Bug Fixes

### Test Suite Fixes

**Issue:** `test_get_info_returns_valid_build_date` was failing due to missing timezone information in ISO format output.

**Resolution:** Updated `system.py` endpoint to use timezone-aware datetime (`datetime.now(UTC)`) for `build_date` field to ensure ISO format includes timezone information (`+00:00` or `Z`).

## 📝 Documentation

### New Documentation Added

1. **`HOTFIX_TIMEZONE_NAIVE.md`** (184 lines)
   - Deployment guide with step-by-step instructions
   - Rollback plan for emergency situations
   - Verification procedures
   - Monitoring recommendations

2. **`TIMEZONE_NAIVE_ANALYSIS.md`** (1,062 lines)
   - Complete analysis of 169 timezone-naive issues across codebase
   - Detailed breakdown by pattern type:
     - `datetime.utcnow()`: 91 occurrences
     - `sa.DateTime()` (no timezone): 53 occurrences
     - `datetime.now()` (naive): 7 occurrences
     - `Field(default_factory=datetime.utcnow)`: 7 occurrences
     - `replace(tzinfo=None)`: 6 occurrences
     - `datetime.fromisoformat()`: 5 occurrences
   - Migration strategy for future timezone-aware implementation
   - Best practices and recommendations

## 📦 Changed Files

### Backend
- `backend/app/services/death_service.py` - Fixed 3 datetime instances
- `backend/app/services/breeding_service.py` - Fixed 6 datetime instances
- `backend/app/api/v1/endpoints/system.py` - Fixed build_date to use timezone-aware datetime
- `backend/pyproject.toml` - Version bump to 2.4.1
- `backend/uv.lock` - Updated lock file

### Frontend
- `frontend/package.json` - Version bump to 2.4.1

### Documentation
- `docs/HOTFIX_TIMEZONE_NAIVE.md` - New deployment guide
- `docs/TIMEZONE_NAIVE_ANALYSIS.md` - New analysis document
- `docs/RELEASE_NOTES_v2.4.1.md` - This file

## 🚀 Deployment Instructions

### Quick Deploy (Recommended)

```bash
# Pull latest changes
git checkout fix/datetime-naive-issues
git pull origin fix/datetime-naive-issues

# Restart services
docker compose restart backend celery-worker celery-beat

# Monitor logs
docker compose logs -f celery-worker
```

### Full Redeploy

```bash
# Pull changes
git checkout fix/datetime-naive-issues
git pull origin fix/datetime-naive-issues

# Rebuild and restart
docker compose down
docker compose up -d --build

# Verify
docker compose ps
docker compose logs -f celery-worker
```

## ✅ Verification Steps

After deployment, verify the fix:

```bash
# Check for errors (should be none)
docker compose logs --tail=100 celery-worker | grep -i "DataError\|timezone\|tzinfo"

# Monitor for 5 minutes
docker compose logs -f celery-worker

# Check that game ticks are processing
docker compose logs --tail=50 celery-worker | grep "game_tick"
```

## ⚠️ Known Issues

### Long-Term Solution Required

This release provides a **temporary fix** by ensuring all datetime objects remain naive (without timezone info) to match the current database schema (`TIMESTAMP WITHOUT TIME ZONE`).

**Future Work Required:**
1. Database migration: Convert all `TIMESTAMP` columns to `TIMESTAMP WITH TIME ZONE`
2. Model updates: Change `TimeStampMixin` to use timezone-aware defaults
3. Code refactor: Replace all `datetime.utcnow()` with `datetime.now(UTC)`
4. Remove `.replace(tzinfo=None)` workarounds

See `docs/TIMEZONE_NAIVE_ANALYSIS.md` for complete migration strategy.

## 🔍 Technical Details

### Datetime Strategy

**Current Approach (v2.4.1):**
- All datetime objects are **naive** (no timezone information)
- PostgreSQL server timezone is configured to UTC in `db/session.py`
- Datetimes are interpreted as UTC but stored without timezone info
- Pattern: `datetime.now(UTC).replace(tzinfo=None)`

**Why This Works:**
- Matches database schema: `TIMESTAMP WITHOUT TIME ZONE`
- Consistent with `TimeStampMixin` using `datetime.utcnow()`
- PostgreSQL connection forced to UTC timezone
- Prevents asyncpg from mixing aware/naive datetimes

## 📊 Testing

All tests pass:
- ✅ `test_get_info_returns_valid_build_date`
- ✅ All system info endpoint tests
- ✅ No regressions in existing test suite

## 🔗 Related Issues

- Production Celery worker crashes - **RESOLVED**
- Mixed timezone-aware/naive datetime errors - **RESOLVED**
- Test failures in info endpoint - **RESOLVED**

## 👥 Contributors

- **Claude Sonnet 4.5** - Analysis, fixes, and documentation
- **ElderEvil** - Review and deployment

## 📝 Commits

1. `44a79e2` - fix: resolve timezone-naive datetime mixing causing Celery worker crashes
2. `1ffe6b3` - fix: use timezone-aware datetime for build_date in system info endpoint
3. `3e512f3` - chore: bump version to 2.4.1

## 🔄 Rollback Plan

If issues occur:

```bash
# Revert to v2.4.0
git checkout master
git pull origin master

# Restart services
docker compose restart backend celery-worker celery-beat
```

## 📞 Support

For questions or issues with this release:
1. Check `docs/HOTFIX_TIMEZONE_NAIVE.md` for deployment troubleshooting
2. Review `docs/TIMEZONE_NAIVE_ANALYSIS.md` for technical details
3. Monitor Celery worker logs for any errors

---

**Version:** 2.4.1
**Previous Version:** 2.4.0
**Next Planned Version:** 2.5.0 (full timezone-aware migration)
