# Exploration System Documentation

## Overview

The exploration system allows dwellers to venture into the wasteland to collect resources, encounter events, and gain experience. The system is built on a modular architecture with clean separation of concerns.

## Architecture

### Service Layer Structure

```
app/services/
├── exploration_service.py          # Main service API (facade)
└── exploration/                     # Modular subsystems
    ├── coordinator.py               # Orchestrates exploration lifecycle
    ├── event_generator.py           # Generates random events
    ├── combat_calculator.py         # Combat mechanics
    ├── loot_calculator.py           # Loot generation
    ├── rewards_calculator.py        # Final rewards calculation
    └── data_loader.py               # JSON data loading
```

### Key Components

#### 1. ExplorationService (`exploration_service.py`)
The main service facade that provides a clean API for exploration operations:

**Core Methods:**
- `send_dweller()` - Initiate exploration with validation
- `get_exploration_progress()` - Get current progress with calculated fields
- `complete_exploration_with_data()` - Complete and return rewards
- `recall_exploration_with_data()` - Recall early with reduced rewards
- `process_event_for_exploration()` - Generate and process events
- `generate_event()` - Generate random events (legacy)
- `process_event()` - Process events for active explorations (legacy)

**Design Pattern:** Facade + Delegation
- Provides unified interface
- Delegates to specialized modules
- Handles validation and error handling
- Returns typed Pydantic schemas

#### 2. Exploration Coordinator (`exploration/coordinator.py`)
Orchestrates the exploration lifecycle:

- `process_event()` - Generate and apply events
- `complete_exploration()` - Finalize exploration, calculate rewards
- `recall_exploration()` - Early recall with penalties
- `_handle_loot_event()` - Process loot collection
- `_apply_health_loss()` - Apply damage to dweller
- `_create_items_in_storage()` - Persist items to database

**Responsibilities:**
- Event processing workflow
- Loot distribution to vault storage
- Dweller status management
- Experience and caps distribution
- Progress tracking

#### 3. Event Generator (`exploration/event_generator.py`)
Generates random exploration events:

**Event Types:**
- **Combat** - Fight enemies, gain experience, risk health
- **Loot** - Find items and caps
- **Danger** - Environmental hazards, health loss
- **Rest** - Restore health

**Event Selection Logic:**
- Time-based cooldowns between events
- Random weighted selection
- Progress-based difficulty scaling
- SPECIAL stat influence

#### 4. Combat Calculator (`exploration/combat_calculator.py`)
Handles combat mechanics:

- `select_enemy()` - Choose appropriate enemy based on progress
- `calculate_combat_outcome()` - Determine victory/defeat and damage

**Mechanics:**
- Enemy difficulty scales with exploration progress
- Dweller stats affect combat outcomes
- Endurance reduces damage taken
- Always victory for now (simplified)

#### 5. Loot Calculator (`exploration/loot_calculator.py`)
Generates loot rewards:

- `select_random_loot()` - Choose loot type (weapon/outfit/junk)
- `select_random_weapon()` - Generate weapon with stats
- `select_random_outfit()` - Generate outfit
- `select_random_junk()` - Generate junk item
- `calculate_caps_found()` - Determine caps amount

**Mechanics:**
- Luck stat influences rarity
- Perception affects caps found
- JSON-based item definitions
- Weighted random selection

#### 6. Rewards Calculator (`exploration/rewards_calculator.py`)
Calculates final rewards:

- `calculate_exploration_rewards()` - Full rewards for completion
- `calculate_recall_rewards()` - Reduced rewards for early recall

**Reward Formula:**
- Experience = (distance × 10) + (enemies × 50)
- Caps = accumulated from loot events
- Items = collected during exploration
- Early recall = rewards × (progress_percentage / 100)

#### 7. Data Loader (`exploration/data_loader.py`)
Loads static game data from JSON:

- `load_enemies()` - Enemy definitions
- `load_event_templates()` - Event description templates
- `load_junk_items()` - Junk item pool
- `load_weapons()` - Weapon definitions
- `load_outfits()` - Outfit definitions

**Features:**
- LRU caching for performance
- Pydantic validation
- Fallback default data
- JSON file-based configuration

## Data Models

### Exploration Model
```python
class Exploration(BaseModel):
    id: UUID4
    vault_id: UUID4
    dweller_id: UUID4
    status: ExplorationStatus  # ACTIVE, COMPLETED, RECALLED
    duration: int  # hours
    start_time: datetime
    end_time: datetime | None

    # Progress tracking
    total_distance: int
    total_caps_found: int
    enemies_encountered: int

    # Dweller stats snapshot
    dweller_strength: int
    dweller_perception: int
    dweller_endurance: int
    dweller_luck: int
    # ... other SPECIAL stats

    # Event history (JSONB)
    events: list[dict]  # Event log
    loot_collected: list[dict]  # Items found
```

### Pydantic Schemas

#### Event Schemas
```python
CombatEventSchema:
    type: "combat"
    description: str
    health_loss: int
    enemy: str
    victory: bool

LootEventSchema:
    type: "loot"
    description: str
    loot: LootSchema

DangerEventSchema:
    type: "danger"
    description: str
    health_loss: int

RestEventSchema:
    type: "rest"
    description: str
    health_restored: int
```

#### Item Schemas
```python
WeaponSchema:
    name: str
    rarity: str
    value: int
    weapon_type: str
    weapon_subtype: str
    stat: str
    damage_min: int
    damage_max: int

OutfitSchema:
    name: str
    rarity: str
    value: int
    outfit_type: str

JunkSchema:
    name: str
    rarity: str
    value: int
```

#### Rewards Schema
```python
RewardsSchema:
    caps: int
    items: list[dict]
    experience: int
    distance: int
    enemies_defeated: int
    events_encountered: int
    progress_percentage: int | None
    recalled_early: bool | None
```

## API Endpoints

### POST /api/v1/explorations/send
Send a dweller on exploration.

**Request:**
```json
{
  "dweller_id": "uuid",
  "duration": 4
}
```

**Response:** `ExplorationRead`

### GET /api/v1/explorations/{id}/progress
Get current exploration progress.

**Response:**
```json
{
  "id": "uuid",
  "status": "ACTIVE",
  "progress_percentage": 45,
  "time_remaining_seconds": 7200,
  "elapsed_time_seconds": 5400,
  "events": [...],
  "loot_collected": [...]
}
```

### POST /api/v1/explorations/{id}/complete
Complete an exploration and collect rewards.

**Response:**
```json
{
  "exploration": {...},
  "rewards_summary": {
    "caps": 250,
    "items": [...],
    "experience": 300,
    "distance": 15,
    "enemies_defeated": 3,
    "events_encountered": 8
  }
}
```

### POST /api/v1/explorations/{id}/recall
Recall a dweller early (reduced rewards).

**Response:** Same as complete, with `recalled_early: true` and `progress_percentage`

### POST /api/v1/explorations/{id}/generate_event
Manually trigger event generation (testing/debugging).

**Response:** Updated `ExplorationRead`

## Game Mechanics

### Event Generation Timing
- Minimum interval: 10 minutes between events
- Events generate based on: `MIN_EVENT_INTERVAL + random(0, exploration_duration * 0.1)`
- Auto-completion when duration expires

### Progress Calculation
- Linear time-based: `elapsed_time / total_duration * 100`
- Used for difficulty scaling and reward calculation

### Difficulty Scaling
- Enemy strength scales with progress (0% → 100%)
- Higher progress = tougher enemies
- Formula: `available_enemies = [e for e in enemies if e.difficulty <= max(1, int(progress * 5))]`

### Stat Influence

**Luck:**
- Better loot rarity (weights shift toward Rare/Legendary)
- More caps found
- Multiplier: 0.5x (Luck 1) to 2.0x (Luck 10)

**Perception:**
- More caps found
- Formula: `base_caps * (1 + perception * 0.1)`

**Endurance:**
- Reduces damage taken in combat
- Formula: `damage = max(1, enemy_damage - endurance * 2)`

**Strength/Agility/Intelligence:**
- Captured in snapshot, not currently affecting mechanics
- Reserved for future combat calculations

### Dweller Status Management
When exploration starts:
- Status → `EXPLORING`

When exploration ends (complete or recall):
- If dweller has `room_id`:
  - Production room → `WORKING`
  - Training room → `TRAINING`
  - Living quarters → `IDLE`
- If no `room_id` → `IDLE`

## Configuration

Game configuration in `app/core/game_config.py`:

```python
exploration:
  min_event_interval: 600  # 10 minutes
  distance_per_hour: 5
  base_xp_per_km: 10
  enemy_xp_bonus: 50
  luck_multiplier_min: 0.5
  luck_multiplier_max: 2.0
  rarity_common_base: 70.0
  rarity_rare_base: 25.0
  rarity_legendary_base: 5.0
```

## Data Files

Static game data in `app/data/exploration/`:

- `enemies.json` - Enemy definitions
- `event_templates.json` - Event description templates
- `junk_items.json` - Junk item pool
- `weapons.json` - Weapon definitions
- `outfits.json` - Outfit definitions

**Example enemy:**
```json
{
  "name": "Radroach",
  "difficulty": 1,
  "min_damage": 5,
  "max_damage": 10
}
```

## Testing

### Test Files
- `test_wasteland_service.py` - Service layer tests
- `test_game_loop_exploration.py` - Integration tests with game loop
- `test_exploration_status.py` - Dweller status lifecycle tests

### Test Coverage
- Event generation logic
- Combat calculations
- Loot distribution
- Rewards calculation
- Status transitions
- Error handling

### Running Tests
```bash
cd backend
uv run pytest app/tests/test_services/test_wasteland_service.py -v
uv run pytest app/tests/test_services/test_game_loop_exploration.py -v
```

## Best Practices

### Service Layer
1. **Always use the service methods** - Don't bypass the service layer
2. **Handle ValueErrors** - Service methods raise ValueError for business logic errors
3. **Use typed schemas** - All service methods return Pydantic schemas
4. **Convert schemas to dicts for JSON** - Use `.model_dump()` before storing in database

### Adding New Event Types
1. Create schema in `schemas/exploration_event.py`
2. Add generation logic in `event_generator.py`
3. Add processing logic in `coordinator.py`
4. Update union type `ExplorationEvent`
5. Add tests

### Adding New Item Types
1. Define in appropriate JSON file
2. Create schema in `schemas/exploration_event.py`
3. Add selection logic in `loot_calculator.py`
4. Add creation logic in `coordinator.py`
5. Add tests

## Common Issues

### JSONB Mutation Not Tracked
**Problem:** Changes to `events` or `loot_collected` not persisting

**Solution:** Use `flag_modified()` after modifying JSONB fields
```python
from sqlalchemy import orm
exploration.events.append(event)
orm.attributes.flag_modified(exploration, "events")
```

### Pydantic Schema Serialization
**Problem:** Can't store Pydantic objects directly in database

**Solution:** Convert to dict with `.model_dump()`
```python
loot_dict = event.loot.model_dump()
exploration.add_event(..., loot=loot_dict)
```

### Import Errors
**Problem:** Circular imports or missing dependencies

**Solution:** Import from `exploration_service`, not submodules
```python
# Correct
from app.services.exploration_service import exploration_service

# Avoid (internal use only)
from app.services.exploration.coordinator import exploration_coordinator
```

## Future Enhancements

### Planned Features
- [ ] Combat defeat scenarios (dweller can lose)
- [ ] Equipment durability and breakage
- [ ] Special encounters (rare events)
- [ ] Exploration difficulty levels
- [ ] Team explorations (multiple dwellers)
- [ ] Location-specific loot tables
- [ ] Weather effects
- [ ] Time-of-day mechanics
- [ ] Dweller perks affecting exploration

### Potential Improvements
- [ ] Event streaming/websockets for real-time updates
- [ ] More complex AI for event selection
- [ ] Branching event chains
- [ ] Story-driven exploration missions
- [ ] Reputation system with wasteland factions
- [ ] Settlements and safe zones

## Changelog

### 2026-01-09
- ✅ Complete Pydantic schema migration
- ✅ Service layer refactoring (moved logic from endpoints)
- ✅ Renamed `WastelandService` → `ExplorationService`
- ✅ Renamed `wasteland_service` → `exploration_service`
- ✅ Fixed `game_loopmax_offline_catchup` typo bug
- ✅ Fixed `JunkTypeEnum.MISC` → `JunkTypeEnum.VALUABLES`
- ✅ Added `.model_dump()` for schema serialization
- ✅ Added `flag_modified()` for JSONB tracking
- ✅ All tests passing (19 passed, 1 skipped)

### Previous
- Modular refactoring from monolithic wasteland_service
- Event-based architecture
- JSON-based configuration
- SPECIAL stats influence mechanics
