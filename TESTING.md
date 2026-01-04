# Testing Documentation

## Overview

This document covers our testing strategy, recent fixes, known issues, and test coverage for the Fallout Shelter
project.

## Recent Fixes & Root Causes

### 1. Cascade Delete Issues (Fixed in #87)

**Problem**: Orphaned records when parent entities were deleted

- Chat messages remained when dwellers were deleted
- Relationship records orphaned when dwellers removed
- Pregnancy records persisted after dweller deletion

**Root Cause**: Missing `ondelete="CASCADE"` in SQLAlchemy foreign key relationships

**Solution**: Added cascade deletes in migrations:

- `2026_01_03_0051af809b0_add_cascade_delete_to_chat_messages.py`
- `2026_01_03_0052_0e741_add_cascade_delete_to_all_foreign_keys.py`

**Files Modified**:

- `backend/app/models/chat_message.py`
- `backend/app/models/dweller.py`
- `backend/app/models/incident.py`

**Test Coverage Needed**: Add tests to verify cascade behavior

### 2. Objective Validation Errors (Fixed in #86)

**Problem**: ValidationError on objective creation - challenge text exceeded 32 character limit

**Root Cause**: Database schema constraint not matching data file content

**Solution**:

- Shortened challenge texts in `backend/app/data/objectives/assign.json`
- Example: "Assign 3 dwellers to work" → "Assign workers"

**Files Modified**:

- `backend/app/data/objectives/assign.json`
- `backend/app/data/objectives/basic_objectives.json`

**Test Coverage**:

- ✅ Added in `backend/app/tests/test_utils/test_seed_objectives.py` (256 lines)
- ✅ Added in `backend/app/tests/test_crud/test_objective.py` (216 lines)

### 3. Session Isolation in Incident Tests

**Problem**: Tests failing due to SQLAlchemy session isolation - dwellers created in fixtures not visible to service
queries

**Root Cause**: Async session transaction boundaries not properly managed in test fixtures

**Current Status**:

- TODO comment in `backend/app/tests/test_services/test_incident_service.py:3-6`
- Partial workaround: Commit dwellers in fixture before returning

**Solution Needed**:

- Investigate proper transaction/session handling in async tests
- Consider using nested transactions or session scopes
- May need to refactor fixture dependency chain

### 4. N+1 Query Problems in Game Loop (Identified - Not Fixed)

**Problem**: Game loop endpoints have nested loops with database queries inside each iteration

**Root Cause**: ORM lazy loading causing multiple queries per iteration

**Locations**:

#### `_process_dwellers` (backend/app/services/game_loop.py:316-379)

```python
for dweller in dwellers:
    # Fetches room individually for each dweller
    room_query = select(Room).where(Room.id == dweller.room_id)
    room_result = await db_session.execute(room_query)
```

**Impact**: If vault has 50 dwellers → 51 queries (1 for dwellers + 50 for rooms)

#### `_process_breeding` (backend/app/services/game_loop.py:495-591)

```python
for i, dweller1 in enumerate(room_dweller_list):
    for dweller2 in room_dweller_list[i + 1:]:
        # Creates/fetches relationship for each pair
        relationship = await relationship_service.get_or_create_relationship(...,,
```

**Impact**: O(n²) relationship queries per room

#### `_process_incidents` (backend/app/services/game_loop.py:439-493)

```python
for incident in active_incidents:
    result = await incident_service.process_incident(...)
    await db_session.refresh(incident)
```

**Impact**: Multiple queries per incident

**Solution Strategy**:

- Use `selectinload()` for eager loading relationships
- Batch relationship queries using `IN` clause
- Pre-fetch all rooms in single query before loop
- Consider caching frequently accessed data

## Test Coverage Summary

### Backend Tests (36 test files)

#### ✅ Well-Tested Areas

**Quest System** (Added in #85):

- `test_crud/test_quest.py`: 224 lines, 7 comprehensive tests
- `test_utils/test_seed_quests.py`: 259 lines
- Backend API endpoints covered

**Objective System** (Added in #86):

- `test_crud/test_objective.py`: 216 lines
- `test_utils/test_seed_objectives.py`: 256 lines

**Core CRUD Operations**:

- ✅ Dweller CRUD
- ✅ Vault CRUD
- ✅ Room CRUD
- ✅ User CRUD
- ✅ Outfit CRUD
- ✅ Weapon CRUD

**Services**:

- ✅ Breeding service (`test_services/test_breeding_service.py`)
- ✅ Wasteland service (`test_services/test_wasteland_service.py`)
- ✅ Training service (`test_services/test_training_service.py`)
- ✅ Leveling service (`test_services/test_leveling_service.py`)
- ✅ Relationship service (`test_services/test_relationship_service.py`)
- ⚠️ Incident service (`test_services/test_incident_service.py`) - Has session issues
- ✅ Game loop exploration (`test_services/test_game_loop_exploration.py`)

**API Endpoints**:

- ✅ Auth & Login
- ✅ Dweller endpoints
- ✅ Vault endpoints
- ✅ Room endpoints
- ✅ Radio endpoints
- ✅ Pregnancy endpoints
- ✅ Relationship endpoints

#### ❌ Missing Test Coverage

**Happiness Service** (Added in #87):

- File: `backend/app/services/happiness_service.py` (394 lines)
- No tests yet for:
    - Happiness calculation algorithm
    - Modifier application (work, relationship, resource shortage)
    - Vault-wide happiness updates
    - Integration with game loop

**Notification Service** (Added in #83):

- File: `backend/app/services/notification_service.py` (245 lines)
- No dedicated test file
- WebSocket integration untested

**Cascade Delete Behavior**:

- No tests verifying orphan prevention
- Need tests for:
    - Dweller deletion → cascade to relationships
    - Dweller deletion → cascade to pregnancies
    - Dweller deletion → cascade to chat messages
    - Dweller deletion → cascade to incidents

**Game Loop Integration**:

- Individual phase tests exist
- Missing integration tests for:
    - Phase interaction effects
    - Cross-phase data consistency
    - Error recovery between phases

### Frontend Tests

#### ✅ Well-Tested Areas

**Quest System** (Added in #86):

- `frontend/tests/unit/stores/quest.test.ts`: 299 lines, 15 tests
- `frontend/tests/unit/views/QuestsView.test.ts`: 419 lines, 11 tests

#### ❌ Missing Test Coverage

**Relationship Components**:

- `ChildrenList.vue` (290 lines) - No tests
- `RelationshipList.vue` updates - Needs tests for new filtering

**Happiness Display**:

- DwellerCard happiness display - No tests

**WebSocket Integration**:

- Chat real-time updates - No tests
- Notification real-time updates - No tests

## Testing Strategy

### Unit Tests

- Test individual functions and methods in isolation
- Use mocks for external dependencies
- Cover edge cases and error conditions

### Integration Tests

- Test service interactions
- Verify database transactions
- Test game loop phase interactions

### API Tests

- Test HTTP endpoints
- Verify request/response formats
- Test authentication and authorization

### Frontend Component Tests

- Test Vue component rendering
- Test user interactions
- Test store integration

## Running Tests

### Backend

```bash
cd backend
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest --cov                    # With coverage
pytest -k "test_quest"          # Run specific tests
```

### Frontend

```bash
cd frontend
npm test                        # Run all tests
npm test -- --coverage          # With coverage
npm test QuestsView.test.ts     # Run specific file
```

## Coverage Goals

- **Backend**: Maintain >80% coverage
- **Frontend**: Maintain >70% coverage
- **Critical paths**: 100% coverage (authentication, data deletion, resource management)

## Known Issues

1. **Incident Service Tests**: Session isolation issues need investigation
2. **Performance**: Game loop N+1 queries need optimization
3. **WebSocket**: Real-time features need integration tests
4. **Cascade Deletes**: Need verification tests post-fix

## Next Steps

1. ✅ Document current state (this file)
2. Add happiness service tests
3. Add cascade delete verification tests
4. Fix game loop N+1 queries
5. Add WebSocket integration tests
6. Resolve incident service session issues
7. Add frontend relationship component tests

## Test Data & Fixtures

### Backend Fixtures (in `backend/app/tests/conftest.py`)

- `async_session`: Async database session
- `vault`: Test vault instance
- `dweller_data`: Factory data for dweller creation
- `room`: Test room
- `room_with_dwellers`: Pre-populated room

### Frontend Test Utilities

- Mock stores
- Mock API responses
- Component mounting helpers

## Continuous Integration

Tests run automatically on:

- Every pull request
- Every push to master
- Nightly builds

CI enforces:

- All tests must pass
- No decrease in coverage
- Linting must pass
