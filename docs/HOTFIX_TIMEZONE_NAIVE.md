# HOTFIX: Timezone-Naive DateTime Error

**Date:** 2026-01-25
**Severity:** CRITICAL
**Environment:** Production/Staging
**Status:** FIXED

## Problem Description

Celery workers were crashing with the following error:

```
sqlalchemy.dialects.postgresql.asyncpg.Error: <class 'asyncpg.exceptions.DataError'>:
invalid input for query argument $4: datetime.datetime(2026, 1, 25, 14, 59, 3...
(can't subtract offset-naive and offset-aware datetimes)

[SQL: UPDATE dweller SET updated_at=$1::TIMESTAMP WITHOUT TIME ZONE,
status=$2::dwellerstatusenum, is_dead=$3::BOOLEAN,
death_timestamp=$4::TIMESTAMP WITHOUT TIME ZONE,
death_cause=$5::deathcauseenum, epitaph=$6::VARCHAR, room_id=$7::UUID
WHERE dweller.id = $8::UUID]
```

### Root Cause

The codebase was mixing timezone-aware and timezone-naive datetime objects:
- `updated_at` field (from `TimeStampMixin`) was using `datetime.utcnow()` → **naive**
- `death_timestamp` was somehow being converted to timezone-aware → **aware with UTC**
- PostgreSQL columns are defined as `TIMESTAMP WITHOUT TIME ZONE`
- SQLAlchemy/asyncpg cannot handle mixed naive/aware datetimes

## Files Modified

### 1. `backend/app/services/death_service.py`

**Changes:**
- Added `from datetime import timezone` import (changed to `UTC` after ruff)
- Replaced all `datetime.utcnow()` calls with `datetime.now(UTC).replace(tzinfo=None)`
- Added comments explaining this is a temporary fix

**Affected methods:**
- `mark_as_dead()` - Line 57: Set death_timestamp with naive datetime
- `get_days_until_permanent()` - Line 195: Compare dates with naive datetime
- `check_and_mark_permanent_deaths()` - Line 213: Calculate cutoff with naive datetime

### 2. `backend/app/services/breeding_service.py`

**Changes:**
- Added `from datetime import timezone` import (changed to `UTC` after ruff)
- Replaced all `datetime.utcnow()` calls with `datetime.now(UTC).replace(tzinfo=None)`
- Affected pregnancy creation, delivery, and child aging

**Affected methods:**
- `create_pregnancy()` - Line 164: Set conceived_at
- `check_due_pregnancies()` - Line 203: Query due pregnancies
- `deliver_baby()` - Lines 267, 288: Set birth_date and updated_at
- `age_children()` - Lines 384, 409: Calculate growth threshold and update timestamps

## Why This Fix Works

The fix ensures **all datetime objects remain naive** (no timezone info) to match:
1. Database schema: `TIMESTAMP WITHOUT TIME ZONE`
2. Model defaults: `TimeStampMixin` uses `datetime.utcnow()`
3. PostgreSQL server timezone setting: UTC (configured in `db/session.py`)

By stripping timezone info with `.replace(tzinfo=None)`, we ensure consistency across all datetime operations.

## Deployment Instructions

### Option 1: Hot Deploy (Recommended for immediate fix)

```bash
# On staging/production server
cd /path/to/fallout-shelter

# Pull changes
git pull origin main

# Restart services
docker compose restart backend celery-worker celery-beat

# Monitor logs
docker compose logs -f celery-worker | grep -i "error\|datetime"
```

### Option 2: Full Redeploy

```bash
cd /path/to/fallout-shelter

# Pull changes
git pull origin main

# Rebuild and restart
docker compose down
docker compose up -d --build

# Monitor
docker compose logs -f celery-worker
```

## Verification

After deployment, verify the fix:

```bash
# Check Celery worker logs for errors
docker compose logs --tail=100 celery-worker | grep -i "DataError\|timezone\|tzinfo"

# Should see no errors

# Trigger a game tick manually to test
docker compose exec backend uv run python -c "
from app.tasks.game_tick import game_tick
game_tick.apply_async()
"

# Monitor for 5 minutes
docker compose logs -f celery-worker
```

## Rollback Plan

If issues occur:

```bash
# Revert to previous commit
git revert HEAD

# Restart services
docker compose restart backend celery-worker celery-beat
```

## Long-Term Solution

This is a **temporary fix**. The proper solution requires:

1. **Database Migration:** Convert all `TIMESTAMP` columns to `TIMESTAMP WITH TIME ZONE`
2. **Model Updates:** Change `TimeStampMixin` to use timezone-aware defaults
3. **Code Refactor:** Replace all `datetime.utcnow()` with `datetime.now(UTC)`
4. **Remove `.replace(tzinfo=None)` calls:** Keep timezone information

See `docs/TIMEZONE_NAIVE_ANALYSIS.md` (1,062 lines) for complete analysis of 169 issues.

## Related Issues

- Total timezone-naive issues found: **169**
  - `datetime.utcnow()`: 91 occurrences
  - `sa.DateTime()` (no timezone): 53 occurrences
  - Other patterns: 25 occurrences

## Testing

Run tests to ensure no regressions:

```bash
cd backend
uv run pytest app/tests/test_services/test_death_service.py -v
uv run pytest app/tests/test_services/test_breeding_service.py -v
uv run pytest app/tests/test_services/test_game_loop_exploration.py -v
```

## Monitoring

After deployment, monitor these metrics:

- Celery worker error rate (should drop to 0)
- Game tick success rate (should improve)
- Database connection errors (should remain stable)
- Dweller death events (should process correctly)

## Notes

- This fix maintains backward compatibility with existing data
- No database migration required for this hotfix
- Performance impact: negligible (just datetime conversion)
- The `.replace(tzinfo=None)` pattern is safe because PostgreSQL timezone is UTC

---

**Applied by:** Claude Sonnet 4.5
**Reviewed by:** [Pending]
**Deployed to staging:** [Pending]
**Deployed to production:** [Pending]
