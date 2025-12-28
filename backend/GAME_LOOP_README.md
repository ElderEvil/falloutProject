# Game Loop Implementation Guide

## Overview

The Fallout Shelter game loop system provides real-time vault simulation with:
- ✅ Automatic resource production and consumption
- ✅ Game state tracking (pause/resume, offline catch-up)
- ✅ Celery Beat scheduled ticks every 60 seconds
- ✅ REST API for game control
- 🔄 Incident system (models ready, integration pending)
- 🔄 Combat system (planned for next phase)

---

## Setup Instructions

### 1. Database Migration

**Create the migration:**
```bash
cd backend
alembic revision --autogenerate -m "add_game_loop_tables"
```

This will create tables for:
- `gamestate` - Vault game session tracking
- `incident` - Combat events and disasters

**Run the migration:**
```bash
alembic upgrade head
```

### 2. Start Celery Worker + Beat

The game loop requires Celery Beat to schedule periodic ticks.

**Windows (Required - Beat doesn't support combined mode):**
```bash
# Terminal 1: Worker
uv run python -m celery -A app.core.celery worker --loglevel=info --pool=solo

# Terminal 2: Beat Scheduler
uv run python -m celery -A app.core.celery beat --loglevel=info
```

**Linux/Mac Option A: Combined (Development)**
```bash
celery -A app.core.celery worker --beat --loglevel=info
```

**Linux/Mac Option B: Separate Processes (Production)**
```bash
# Terminal 1: Worker
celery -A app.core.celery worker --loglevel=info --concurrency=4

# Terminal 2: Beat Scheduler
celery -A app.core.celery beat --loglevel=info
```

**Verify Beat is Running:**
Check logs for:
```
[INFO/Beat] Scheduler: Sending due task game-tick-every-60-seconds
```

### 3. Verify Setup

**Check if game ticks are running:**
```bash
# Check Celery logs for game tick execution
# You should see logs like:
# [INFO] Starting game tick
# [INFO] Processing game tick for X vaults
# [INFO] Game tick completed: X processed, 0 errors
```

---

## API Endpoints

Base URL: `/api/v1/game`

### Pause Vault
```http
POST /api/v1/game/vaults/{vault_id}/pause
Authorization: Bearer {token}
```

**Response:**
```json
{
  "message": "Vault paused successfully",
  "vault_id": "uuid",
  "is_paused": true,
  "paused_at": "2025-12-29T12:00:00Z"
}
```

### Resume Vault
```http
POST /api/v1/game/vaults/{vault_id}/resume
Authorization: Bearer {token}
```

**Response:**
```json
{
  "message": "Vault resumed successfully",
  "vault_id": "uuid",
  "is_paused": false,
  "resumed_at": "2025-12-29T12:05:00Z"
}
```

### Get Game State
```http
GET /api/v1/game/vaults/{vault_id}/game-state
Authorization: Bearer {token}
```

**Response:**
```json
{
  "vault_id": "uuid",
  "is_active": true,
  "is_paused": false,
  "total_game_time": 3600,
  "last_tick_time": "2025-12-29T12:00:00Z",
  "offline_time": 120
}
```

### List Incidents
```http
GET /api/v1/game/vaults/{vault_id}/incidents
Authorization: Bearer {token}
```

**Response:**
```json
{
  "vault_id": "uuid",
  "incident_count": 1,
  "incidents": [
    {
      "id": "uuid",
      "type": "raider_attack",
      "status": "active",
      "room_id": "uuid",
      "difficulty": 5,
      "start_time": "2025-12-29T12:00:00Z",
      "elapsed_time": 120,
      "damage_dealt": 50,
      "enemies_defeated": 2
    }
  ]
}
```

### Get Incident Details
```http
GET /api/v1/game/vaults/{vault_id}/incidents/{incident_id}
Authorization: Bearer {token}
```

### Manual Tick (Testing)
```http
POST /api/v1/game/vaults/{vault_id}/tick
Authorization: Bearer {token}
```

**Response:**
```json
{
  "message": "Manual tick processed successfully",
  "vault_id": "uuid",
  "seconds_passed": 60,
  "updates": {
    "resources": {
      "power": 950,
      "food": 480,
      "water": 520,
      "events": {
        "production": {"power": 100, "food": 50, "water": 60},
        "consumption": {"power": 150, "food": 30, "water": 40},
        "warnings": []
      }
    },
    "incidents": {"processed": 0, "spawned": 0},
    "dwellers": {"health_updated": 0, "leveled_up": 0},
    "events": {"triggered": 0}
  }
}
```

---

## Configuration

### Game Balance Settings

**File:** `backend/app/config/game_balance.py`

**Key Constants:**
```python
# Game loop timing
TICK_INTERVAL = 60  # Seconds between ticks
MAX_OFFLINE_CATCHUP = 3600  # Max catch-up time (1 hour)

# Incident spawn rates (configurable)
INCIDENT_BASE_CHANCE = 0.003  # 0.3% per tick (rare)
INCIDENT_MAX_CHANCE = 0.05  # 5% cap

# Resource rates
BASE_PRODUCTION_RATE = 0.1  # Per SPECIAL point per second
POWER_CONSUMPTION_RATE = 0.5 / 60  # Per room size/tier/second
FOOD_CONSUMPTION_PER_DWELLER = 0.36 / 60
WATER_CONSUMPTION_PER_DWELLER = 0.36 / 60

# Thresholds
LOW_RESOURCE_THRESHOLD = 0.2  # 20% warning
CRITICAL_RESOURCE_THRESHOLD = 0.05  # 5% critical
```

**To adjust spawn rates:**
```python
# Make incidents more frequent
INCIDENT_BASE_CHANCE = 0.01  # 1% per tick

# Make incidents rarer
INCIDENT_BASE_CHANCE = 0.001  # 0.1% per tick
```

### Celery Beat Schedule

**File:** `backend/app/core/celery.py`

```python
celery_app.conf.beat_schedule = {
    'game-tick-every-60-seconds': {
        'task': 'game_tick',
        'schedule': 60.0,  # Change this to adjust tick frequency
    },
}
```

---

## How It Works

### Game Tick Flow

1. **Celery Beat** triggers `game_tick` task every 60 seconds
2. **Game Loop Service** processes all active (not paused) vaults
3. For each vault:
   - Calculate time since last tick
   - Apply catch-up (max 1 hour) if vault was offline
   - **Phase 1: Resources**
     - Calculate production (based on rooms + dweller stats)
     - Calculate consumption (rooms + dwellers)
     - Update vault resources
     - Generate warnings if resources low
   - **Phase 2: Incidents** (coming soon)
     - Process active incidents
     - Spawn new incidents (rare)
     - Apply combat damage
   - **Phase 3: Dwellers** (coming soon)
     - Regenerate health
     - Update happiness
     - Handle deaths
   - **Phase 4: Events** (coming soon)
     - Trigger random events
     - Process quest timers
4. Update game state (last_tick_time, total_game_time)
5. Commit changes to database

### Resource Calculation

**Production:**
```python
production = room.output * dweller_ability_sum * BASE_RATE * tier_multiplier * seconds
```

**Consumption:**
```python
power_consumed = room_count * size * tier * POWER_RATE * seconds
food_consumed = dweller_count * FOOD_RATE * seconds
water_consumed = dweller_count * WATER_RATE * seconds
```

**Result:**
```python
new_power = clamp(vault.power + production - consumption, 0, vault.power_max)
```

### Offline Catch-Up

When a vault hasn't been processed for a while:
1. Calculate `offline_time = now - last_tick_time`
2. Cap at `MAX_OFFLINE_CATCHUP` (1 hour)
3. Process single tick with `offline_time` seconds
4. Prevents abuse and database overload

---

## Testing

### Manual Testing via API

1. **Create a vault** (or use existing)
2. **Check game state:**
   ```bash
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v1/game/vaults/{vault_id}/game-state
   ```

3. **Trigger manual tick:**
   ```bash
   curl -X POST -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v1/game/vaults/{vault_id}/tick
   ```

4. **Check resources changed:**
   ```bash
   curl -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v1/vaults/{vault_id}
   ```

5. **Pause vault:**
   ```bash
   curl -X POST -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v1/game/vaults/{vault_id}/pause
   ```

6. **Wait 60s, verify no resource changes**

7. **Resume vault:**
   ```bash
   curl -X POST -H "Authorization: Bearer {token}" \
     http://localhost:8000/api/v1/game/vaults/{vault_id}/resume
   ```

### Automated Tests

**Create test file:** `backend/app/tests/test_game_loop.py`

```python
import pytest
from app.services.game_loop import game_loop_service

@pytest.mark.asyncio
async def test_resource_production(db_session, test_vault):
    # Create vault with power room and dwellers
    # Trigger tick
    result = await game_loop_service.process_vault_tick(
        db_session, test_vault.id
    )

    # Assert resources changed
    assert result["updates"]["resources"]["power"] > 0

@pytest.mark.asyncio
async def test_pause_resume(db_session, test_vault):
    # Pause vault
    await game_loop_service.pause_vault(db_session, test_vault.id)

    # Verify paused
    status = await game_loop_service.get_vault_status(
        db_session, test_vault.id
    )
    assert status["is_paused"] is True

    # Resume
    await game_loop_service.resume_vault(db_session, test_vault.id)
    assert status["is_paused"] is False
```

---

## Monitoring

### Check Celery Health

```bash
# View active tasks
celery -A app.core.celery inspect active

# View registered tasks
celery -A app.core.celery inspect registered

# View scheduled tasks
celery -A app.core.celery inspect scheduled
```

### Monitor Game Loop Performance

Check logs for:
- **Tick duration:** Should be < 1 second per vault
- **Error rate:** Should be 0
- **Vaults processed:** Should match active vault count

**Log example:**
```
[INFO] Processing game tick for 5 vaults
[INFO] Game tick completed: 5 processed, 0 errors, 0.87s
```

### Database Queries

```sql
-- Check game states
SELECT vault_id, is_paused, total_game_time, last_tick_time
FROM gamestate
ORDER BY last_tick_time DESC;

-- Check active incidents
SELECT vault_id, type, status, difficulty, start_time
FROM incident
WHERE status IN ('active', 'spreading')
ORDER BY start_time DESC;
```

---

## Troubleshooting

### Game Tick Not Running

**Check Celery Beat is running:**
```bash
ps aux | grep celery
```

**Check beat schedule:**
```bash
celery -A app.core.celery inspect scheduled
```

**Verify task is registered:**
```bash
celery -A app.core.celery inspect registered
# Should see 'game_tick' in the list
```

### Resources Not Updating

1. Check if vault is paused:
   ```http
   GET /api/v1/game/vaults/{vault_id}/game-state
   ```

2. Check if rooms have dwellers assigned:
   ```sql
   SELECT r.name, COUNT(d.id) as dweller_count
   FROM room r
   LEFT JOIN dweller d ON d.room_id = r.id
   WHERE r.vault_id = 'your-vault-id'
   GROUP BY r.id;
   ```

3. Check if dwellers have appropriate SPECIAL stats

### High CPU Usage

- Reduce `TICK_INTERVAL` (increase from 60s to 120s)
- Optimize vault count (limit active vaults)
- Add database indexes:
  ```sql
  CREATE INDEX idx_gamestate_vault ON gamestate(vault_id);
  CREATE INDEX idx_gamestate_active ON gamestate(is_active, is_paused);
  CREATE INDEX idx_incident_vault_status ON incident(vault_id, status);
  ```

---

## Next Steps

### Phase 2: Incident System (Ready to Implement)

Models are created, need to integrate:
1. Add incident spawning to `game_loop.py`
2. Create `incident_manager.py` service
3. Create `combat_system.py` service
4. Test incident spawning and resolution

### Phase 3: Dweller Lifecycle

1. Create `dweller_manager.py` service
2. Add health regeneration
3. Add happiness calculation
4. Add death mechanics

### Phase 4: Advanced Features

1. Wasteland exploration
2. Quest timers
3. Random events
4. WebSocket real-time updates
5. Statistics dashboard

---

## Support

**Check logs:**
- Backend: `backend/logs/`
- Celery: stdout when running worker

**Common issues:**
- Database connection errors: Check PostgreSQL is running
- Redis connection errors: Check Redis is running
- Import errors: Run `pip install -r requirements.txt`

**Need help?** Check the codebase documentation:
- `backend/app/services/game_loop.py` - Main coordinator
- `backend/app/services/resource_manager.py` - Resource calculations
- `backend/app/models/game_state.py` - Game state model
- `backend/app/config/game_balance.py` - Configuration
