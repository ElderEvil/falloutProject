# Manual Testing Plan - v2.3.0 (P0 + P1)

> **Version:** 2.3.0
> **Features:** Storage Validation + Pregnancy Debug
> **Date:** 2026-01-24

## Prerequisites

### 1. Environment Setup
```bash
cd backend

# Copy and configure debug settings
cp .env.example .env

# Enable breeding debug mode for P1 tests
# Edit .env and set:
BREEDING_DEBUG_ENABLED=true
BREEDING_DEBUG_LOG_CONCEPTION_CHECKS=true
BREEDING_DEBUG_INSTANT_PREGNANCY=false
BREEDING_DEBUG_GUARANTEED_CONCEPTION=false

# Start services
docker-compose up -d db redis
uv run alembic upgrade head
uv run fastapi dev main.py
```

### 2. Get Auth Token
```bash
# Login as superuser
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=YOUR_SUPERUSER_EMAIL&password=YOUR_SUPERUSER_PASSWORD"

# Save the access_token from response
export TOKEN="your_access_token_here"
```

### 3. Create Test Data
```bash
# Create a vault (if needed)
curl -X POST "http://localhost:8000/api/v1/vaults" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"number": 999}'

# Save vault_id from response
export VAULT_ID="your_vault_id_here"
```

---

## P0: Storage Validation Testing

### Test 1: Get Storage Space Info (Basic)

**Objective:** Verify storage space endpoint returns correct data

**Steps:**
```bash
# Get storage space for vault
curl -X GET "http://localhost:8000/api/v1/storage/vault/$VAULT_ID/space" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "vault_id": "...",
  "used_space": 0,
  "max_space": 50,
  "available_space": 50,
  "utilization_percentage": 0.0
}
```

**Verification:**
- [ ] `used_space` matches number of items in storage (weapons + outfits + junk)
- [ ] `available_space` = `max_space` - `used_space`
- [ ] `utilization_percentage` = (`used_space` / `max_space`) * 100

---

### Test 2: Storage Space with Existing Items

**Objective:** Verify used_space calculation is accurate

**Steps:**
```bash
# 1. Add some items to storage via exploration or manually
# For quick test, use database:
uv run python -c "
import asyncio
from app.db.session import async_session_maker
from app import crud

async def add_items():
    async with async_session_maker() as db:
        # Add 5 weapons to storage
        for i in range(5):
            await crud.weapon.create(db, obj_in={
                'name': f'Test Weapon {i}',
                'damage': 10,
                'rarity': 'common',
                'storage_id': 'YOUR_STORAGE_ID'
            })
        await db.commit()

asyncio.run(add_items())
"

# 2. Check storage space again
curl -X GET "http://localhost:8000/api/v1/storage/vault/$VAULT_ID/space" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "used_space": 5,
  "max_space": 50,
  "available_space": 45,
  "utilization_percentage": 10.0
}
```

**Verification:**
- [ ] `used_space` increased by 5
- [ ] `available_space` decreased by 5
- [ ] Percentage calculated correctly

---

### Test 3: Exploration with Storage Limits

**Objective:** Verify exploration respects storage limits and prioritizes rare items

**Setup:**
```bash
# 1. Fill storage almost to capacity (e.g., 48/50)
# 2. Create a dweller for exploration
curl -X POST "http://localhost:8000/api/v1/dwellers" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vault_id": "'$VAULT_ID'",
    "first_name": "Explorer",
    "last_name": "Test",
    "gender": "male"
  }'

export DWELLER_ID="dweller_id_from_response"
```

**Steps:**
```bash
# 1. Start exploration
curl -X POST "http://localhost:8000/api/v1/exploration/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dweller_id": "'$DWELLER_ID'",
    "duration_hours": 0.1
  }'

export EXPLORATION_ID="exploration_id_from_response"

# 2. Wait for exploration to finish (or manually complete via debug)

# 3. Complete exploration
curl -X POST "http://localhost:8000/api/v1/exploration/$EXPLORATION_ID/complete" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Behavior:**
- [ ] Response includes `overflow_items` array with items that didn't fit
- [ ] `transferred_items` contains only items that fit (max 2 items)
- [ ] Legendary/Rare items are transferred before Common items
- [ ] Storage `used_space` doesn't exceed `max_space`

**Logs to Check:**
```bash
# Look for these log entries in backend console:
INFO: Storage transfer: 2 items transferred, 3 overflow items (storage full)
INFO: Transferred items by rarity: legendary=1, rare=1
WARNING: Storage overflow: 3 items could not be stored (legendary=0, rare=0, common=3)
```

---

### Test 4: Storage Full Scenario

**Objective:** Verify behavior when storage is completely full

**Setup:**
```bash
# Fill storage to 100% capacity (50/50 items)
```

**Steps:**
```bash
# Try to complete an exploration with loot
curl -X POST "http://localhost:8000/api/v1/exploration/$EXPLORATION_ID/complete" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "rewards": {
    "transferred_items": [],
    "overflow_items": [
      {"name": "Item 1", "rarity": "common", "type": "weapon"},
      {"name": "Item 2", "rarity": "rare", "type": "outfit"}
    ],
    "caps_earned": 100,
    "xp_earned": 50
  }
}
```

**Verification:**
- [ ] All loot items are in `overflow_items`
- [ ] No items transferred to storage
- [ ] Caps and XP still awarded
- [ ] Log shows: `WARNING: Storage overflow: X items could not be stored`

---

### Test 5: Rarity Priority Verification

**Objective:** Verify rare items are prioritized over common items

**Setup:**
```bash
# Set storage capacity to 48/50 (2 spaces available)
# Prepare exploration with mixed loot: 1 legendary, 2 rare, 3 common
```

**Steps:**
```bash
# Complete exploration with mixed rarity loot
curl -X POST "http://localhost:8000/api/v1/exploration/$EXPLORATION_ID/complete" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Transfer Order:**
1. [ ] 1 Legendary item transferred first
2. [ ] 1 Rare item transferred second (fills storage to 50/50)
3. [ ] Remaining items (1 rare + 3 common) in overflow

**Verification:**
```bash
# Check storage contents
curl -X GET "http://localhost:8000/api/v1/storage/$VAULT_ID/items" \
  -H "Authorization: Bearer $TOKEN"

# Verify last 2 items added are legendary and rare
```

---

## P1: Pregnancy Debug Features Testing

### Test 6: Debug Mode Configuration

**Objective:** Verify debug config loads correctly

**Steps:**
```bash
# 1. Check current config
curl -X GET "http://localhost:8000/api/v1/health" \
  -H "Authorization: Bearer $TOKEN"

# 2. In backend console, you should see logs on startup:
# INFO: Game configuration loaded successfully
# Check that BREEDING_DEBUG_ENABLED=true is loaded
```

**Verification:**
- [ ] Backend starts without errors
- [ ] Config values loaded from .env

---

### Test 7: Force Conception (Debug Disabled)

**Objective:** Verify endpoint returns 403 when debug mode disabled

**Setup:**
```bash
# Edit .env: BREEDING_DEBUG_ENABLED=false
# Restart backend
```

**Steps:**
```bash
# Create two adult dwellers (male and female)
curl -X POST "http://localhost:8000/api/v1/dwellers" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vault_id": "'$VAULT_ID'",
    "first_name": "Jane",
    "gender": "female",
    "age_group": "adult"
  }'

export MOTHER_ID="female_dweller_id"

curl -X POST "http://localhost:8000/api/v1/dwellers" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vault_id": "'$VAULT_ID'",
    "first_name": "John",
    "gender": "male",
    "age_group": "adult"
  }'

export FATHER_ID="male_dweller_id"

# Try to force conception
curl -X POST "http://localhost:8000/api/v1/pregnancies/debug/force-conception?mother_id=$MOTHER_ID&father_id=$FATHER_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "detail": "Debug mode is not enabled. Set BREEDING_DEBUG_ENABLED=true"
}
```

**Verification:**
- [ ] Returns 403 status code
- [ ] Error message indicates debug mode requirement

---

### Test 8: Force Conception (Debug Enabled)

**Objective:** Verify forced conception works when debug enabled

**Setup:**
```bash
# Edit .env: BREEDING_DEBUG_ENABLED=true
# Restart backend
```

**Steps:**
```bash
# Force conception between two dwellers
curl -X POST "http://localhost:8000/api/v1/pregnancies/debug/force-conception?mother_id=$MOTHER_ID&father_id=$FATHER_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "id": "pregnancy_id",
  "mother_id": "female_dweller_id",
  "father_id": "male_dweller_id",
  "conceived_at": "2026-01-24T...",
  "due_at": "2026-01-24T...",
  "status": "pregnant",
  "progress_percentage": 0.0,
  "time_remaining_seconds": 10800,
  "is_due": false
}
```

**Verification:**
- [ ] Returns 200 status
- [ ] Pregnancy created with correct parents
- [ ] `due_at` is ~3 hours in future (default pregnancy duration)
- [ ] Backend logs: `INFO: DEBUG force-conception triggered`

---

### Test 9: Force Conception Validation

**Objective:** Verify endpoint validates gender/age/existing pregnancy

**Test 9a: Wrong Gender**
```bash
# Try to force conception with two males
curl -X POST "http://localhost:8000/api/v1/pregnancies/debug/force-conception?mother_id=$FATHER_ID&father_id=$FATHER_ID" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 400 error "Mother must be female"
```

**Test 9b: Already Pregnant**
```bash
# Try to force conception again with same mother
curl -X POST "http://localhost:8000/api/v1/pregnancies/debug/force-conception?mother_id=$MOTHER_ID&father_id=$FATHER_ID" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 400 error "Mother is already pregnant"
```

**Test 9c: Child Dweller**
```bash
# Create a child dweller
curl -X POST "http://localhost:8000/api/v1/dwellers" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name": "Kid", "gender": "female", "age_group": "child", "vault_id": "'$VAULT_ID'"}'

export CHILD_ID="child_dweller_id"

# Try to force conception with child
curl -X POST "http://localhost:8000/api/v1/pregnancies/debug/force-conception?mother_id=$CHILD_ID&father_id=$FATHER_ID" \
  -H "Authorization: Bearer $TOKEN"

# Expected: 400 error "Mother must be adult"
```

**Verification:**
- [ ] All validation errors return 400 status
- [ ] Error messages are descriptive

---

### Test 10: Accelerate Pregnancy

**Objective:** Verify pregnancy can be instantly completed via debug endpoint

**Setup:**
```bash
# Use pregnancy from Test 8 (should not be due yet)
export PREGNANCY_ID="pregnancy_id_from_test_8"

# Verify pregnancy is not due
curl -X GET "http://localhost:8000/api/v1/pregnancies/$PREGNANCY_ID" \
  -H "Authorization: Bearer $TOKEN"

# Should show: "is_due": false
```

**Steps:**
```bash
# Accelerate pregnancy to be due immediately
curl -X POST "http://localhost:8000/api/v1/pregnancies/$PREGNANCY_ID/debug/accelerate" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "id": "pregnancy_id",
  "mother_id": "...",
  "father_id": "...",
  "conceived_at": "2026-01-24T10:00:00",
  "due_at": "2026-01-24T09:59:59",
  "status": "pregnant",
  "progress_percentage": 100.0,
  "time_remaining_seconds": 0,
  "is_due": true
}
```

**Verification:**
- [ ] Returns 200 status
- [ ] `is_due` changed from false to true
- [ ] `progress_percentage` = 100.0
- [ ] `time_remaining_seconds` = 0
- [ ] Backend logs: `INFO: DEBUG pregnancy accelerated`

---

### Test 11: Deliver Accelerated Baby

**Objective:** Verify accelerated pregnancy can be delivered immediately

**Steps:**
```bash
# Deliver the accelerated pregnancy
curl -X POST "http://localhost:8000/api/v1/pregnancies/$PREGNANCY_ID/deliver" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "pregnancy_id": "...",
  "child_id": "...",
  "message": "Baby [Name] [LastName] has been born!"
}
```

**Verification:**
- [ ] Baby delivered successfully
- [ ] Child dweller created with `age_group: "child"`
- [ ] Pregnancy status changed to "delivered"
- [ ] Child has `parent_1_id` and `parent_2_id` set

```bash
# Verify child exists
curl -X GET "http://localhost:8000/api/v1/dwellers?vault_id=$VAULT_ID" \
  -H "Authorization: Bearer $TOKEN"

# Check for newly created child dweller
```

---

### Test 12: Debug Instant Pregnancy Mode

**Objective:** Verify instant pregnancy config creates due pregnancies

**Setup:**
```bash
# Edit .env:
BREEDING_DEBUG_ENABLED=true
BREEDING_DEBUG_INSTANT_PREGNANCY=true

# Restart backend
```

**Steps:**
```bash
# Create new couple
curl -X POST "http://localhost:8000/api/v1/dwellers" -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name": "Mary", "gender": "female", "age_group": "adult", "vault_id": "'$VAULT_ID'"}'
export MOTHER2_ID="..."

curl -X POST "http://localhost:8000/api/v1/dwellers" -H "Authorization: Bearer $TOKEN" \
  -d '{"first_name": "Bob", "gender": "male", "age_group": "adult", "vault_id": "'$VAULT_ID'"}'
export FATHER2_ID="..."

# Force conception
curl -X POST "http://localhost:8000/api/v1/pregnancies/debug/force-conception?mother_id=$MOTHER2_ID&father_id=$FATHER2_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected Response:**
```json
{
  "id": "...",
  "is_due": true,
  "progress_percentage": 100.0,
  "time_remaining_seconds": 0
}
```

**Verification:**
- [ ] Pregnancy created and immediately due
- [ ] Can deliver right away without accelerate
- [ ] Backend logs: `INFO: DEBUG instant pregnancy enabled - due immediately`

---

### Test 13: Debug Guaranteed Conception

**Objective:** Verify guaranteed conception mode always succeeds

**Setup:**
```bash
# Edit .env:
BREEDING_DEBUG_ENABLED=true
BREEDING_DEBUG_GUARANTEED_CONCEPTION=true
BREEDING_DEBUG_LOG_CONCEPTION_CHECKS=true

# Restart backend
```

**Steps:**
```bash
# 1. Create couple with partners set and place in living quarters
# 2. Manually trigger conception check (via game tick or Celery task)
# 3. Check backend logs
```

**Expected Logs:**
```
INFO: DEBUG conception check
  extra: {
    "dweller_id": "...",
    "partner_id": "...",
    "conception_chance": 1.0,
    "roll": 0.XX,
    "success": true,
    "debug_guaranteed": true
  }
INFO: Conception with 100% chance: Mother=..., Father=...
```

**Verification:**
- [ ] All eligible couples conceive
- [ ] Conception chance shown as 1.0 (100%)
- [ ] Logs show `debug_guaranteed: true`

---

### Test 14: Debug Conception Logging

**Objective:** Verify detailed conception logs when enabled

**Setup:**
```bash
# Edit .env:
BREEDING_DEBUG_ENABLED=true
BREEDING_DEBUG_LOG_CONCEPTION_CHECKS=true
BREEDING_DEBUG_GUARANTEED_CONCEPTION=false

# Restart backend
```

**Steps:**
```bash
# Trigger conception check with multiple couples in living quarters
# Watch backend logs
```

**Expected Logs:**
```
INFO: DEBUG conception check
  extra: {
    "dweller_id": "abc-123",
    "partner_id": "def-456",
    "dweller_gender": "male",
    "partner_gender": "female",
    "affinity": 85,
    "conception_chance": 0.85,
    "roll": 0.72,
    "success": true,
    "debug_guaranteed": false
  }

INFO: DEBUG conception check
  extra: {
    "dweller_id": "ghi-789",
    "partner_id": "jkl-012",
    "conception_chance": 0.65,
    "roll": 0.82,
    "success": false,
    "debug_guaranteed": false
  }
```

**Verification:**
- [ ] Each couple checked is logged
- [ ] Shows affinity, chance, roll result
- [ ] Success/failure clearly indicated
- [ ] Helps debug why conception isn't happening

---

## Test Summary Checklist

### P0 - Storage Validation
- [ ] Test 1: Basic storage space endpoint works
- [ ] Test 2: Used space calculation is accurate
- [ ] Test 3: Exploration respects storage limits
- [ ] Test 4: Full storage prevents all transfers
- [ ] Test 5: Rare items prioritized over common

### P1 - Pregnancy Debug
- [ ] Test 6: Debug config loads from .env
- [ ] Test 7: Force conception blocked when debug disabled
- [ ] Test 8: Force conception works when debug enabled
- [ ] Test 9: Force conception validates inputs (gender/age/existing)
- [ ] Test 10: Accelerate pregnancy makes it immediately due
- [ ] Test 11: Accelerated pregnancy can be delivered
- [ ] Test 12: Instant pregnancy mode creates due pregnancies
- [ ] Test 13: Guaranteed conception mode always succeeds
- [ ] Test 14: Conception logging shows detailed checks

---

## Troubleshooting

### Storage Tests Failing
```bash
# Check storage exists
curl -X GET "http://localhost:8000/api/v1/storage/vault/$VAULT_ID" \
  -H "Authorization: Bearer $TOKEN"

# Manually sync used_space
uv run python -c "
import asyncio
from app.db.session import async_session_maker
from app.crud.storage import update_used_space

async def sync():
    async with async_session_maker() as db:
        await update_used_space(db, 'YOUR_STORAGE_ID')

asyncio.run(sync())
"
```

### Pregnancy Tests Failing
```bash
# Check debug config is loaded
uv run python -c "
from app.core.game_config import game_config
print(f'Debug enabled: {game_config.breeding.debug_enabled}')
print(f'Debug log checks: {game_config.breeding.debug_log_conception_checks}')
"

# Clear test pregnancies
curl -X DELETE "http://localhost:8000/api/v1/pregnancies/$PREGNANCY_ID" \
  -H "Authorization: Bearer $TOKEN"
```

### Can't Access Debug Endpoints (403)
- Verify you're using **superuser** token (not regular user)
- Check `BREEDING_DEBUG_ENABLED=true` in `.env`
- Restart backend after env changes

---

*Testing Complete!*
