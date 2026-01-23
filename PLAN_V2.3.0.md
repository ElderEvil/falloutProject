# v2.3.0 Implementation Plan - Backend Stability & Testing

**Target Release:** February 2026
**Current Coverage:** 46.05% → **Target:** 80%
**Priority:** Backend stability, bug fixes, testability

---

## 🎯 Priorities

1. **P0** - Fix exploration item storage bug (blocking)
2. **P1** - Add pregnancy debug options (testability)
3. **P1** - Increase test coverage 46% → 80% (quality)
4. **P4** - datetime.utcnow() deprecation (deferred to future release)

---

## P0: Fix Exploration Item Storage Bug

### Problem
Items generated during exploration may exceed vault storage limits. No validation in Coordinator._transfer_loot_to_storage() before creating Weapon/Outfit/Junk objects.

**Impact:** Storage overflow, data inconsistency, player confusion

### Root Cause
Exploration Flow:
1. EventGenerator generates loot events
2. LootCalculator selects items, adds to exploration.loot_collected (JSON)
3. Coordinator._transfer_loot_to_storage() creates DB objects
   - NO storage.max_space validation
   - NO logging for transfer failures

### Files
- backend/app/services/exploration/coordinator.py - _transfer_loot_to_storage()
- backend/app/models/storage.py - Storage model with max_space
- backend/app/models/exploration.py - loot_collected field

### Implementation

#### 1. Add storage validation
File: backend/app/services/exploration/coordinator.py
- Add _count_storage_items() method
- Check current_items + new_items <= max_space before transfer
- Prioritize rare items if overflow (legendary > rare > uncommon > common)
- Log warnings for dropped items

#### 2. Add storage API endpoint
File: backend/app/api/v1/endpoints/storage.py
- GET /vault/{vault_id}/space - return current/max/available/utilization_pct

#### 3. Add logging
Files: coordinator.py, event_generator.py, loot_calculator.py
- Item generation events (what, quantity, rarity)
- Storage validation (pass/fail, overflow amount)
- Transfer success/failure per item
- Caps deposited

#### 4. Tests
File: backend/app/tests/test_services/test_exploration_coordinator.py (new)
- test_transfer_respects_storage_limits
- test_transfer_prioritizes_rare_items
- test_transfer_logs_overflow_warning
- test_transfer_handles_missing_storage

File: backend/app/tests/test_api/test_storage.py (new)
- test_get_storage_space_info

### Acceptance
- Storage validation prevents overflow
- Rare items prioritized when limited
- Logging for all transfer operations
- API endpoint for storage info
- Tests 95%+ coverage
- No regressions in existing tests

---

## P1: Pregnancy Debug Options & Logging

### Problem
Hard to test pregnancy system:
- Base conception: 2% per 60s tick (very low)
- Requires: partners in living quarters, adult, partnered
- No debug options
- No logging for failed attempts

**Impact:** Cannot validate mechanics, unknown failure reasons

### Current State
File: backend/app/services/breeding_service.py
- process_breeding_opportunities() - 2% base, affinity/100 with relationship
- No logging for failures

File: backend/app/core/game_config.py
- BREEDING_CONCEPTION_CHANCE_PER_TICK = 0.02 (2%)
- BREEDING_PREGNANCY_DURATION_SECONDS = 10800 (3 hours)
- BREEDING_CHILD_GROWTH_DURATION_SECONDS = 10800 (3 hours)

### Implementation

#### 1. Add debug config
File: backend/app/core/game_config.py
- BREEDING_DEBUG_MODE (bool, default False)
- BREEDING_DEBUG_FORCE_CONCEPTION (bool)
- BREEDING_DEBUG_INSTANT_PREGNANCY (bool)
- BREEDING_DEBUG_INSTANT_GROWTH (bool)
- BREEDING_DEBUG_CONCEPTION_RATE (float, 1.0 in debug mode)

#### 2. Add logging
File: backend/app/services/breeding_service.py
- Log eligible couples count
- Log skip reasons (dead, pregnant, not in quarters)
- Log conception chance calculation
- Log conception roll (success/fail)

#### 3. Add admin endpoints
File: backend/app/api/v1/endpoints/pregnancy.py
- POST /force-conception - admin only, debug mode only
- POST /{pregnancy_id}/accelerate - advance by N hours

#### 4. Tests
File: backend/app/tests/test_services/test_breeding_service.py
- Conception with affinity rates
- Conception with 2% base rate
- Failed conception logging
- Debug mode force conception
- Debug mode instant timers
- Child SPECIAL inheritance (50% parents)

File: backend/app/tests/test_api/test_pregnancy.py
- Force conception (admin only)
- Accelerate pregnancy (debug only)
- 403 for non-admin
- 400 when debug disabled

### Env Vars
Add to .env.example:
```env
BREEDING_DEBUG_MODE=false
BREEDING_DEBUG_FORCE_CONCEPTION=false
BREEDING_DEBUG_INSTANT_PREGNANCY=false
BREEDING_DEBUG_INSTANT_GROWTH=false
BREEDING_DEBUG_CONCEPTION_RATE=1.0
```

### Acceptance
- Debug config in .env.example
- Comprehensive logging for attempts
- Admin endpoints for testing
- Tests 85%+ coverage
- Documentation in AGENTS.md

---

## P1: Test Coverage 46% → 80%

### Current
- Overall: 46.05%
- Test files: 40+, 500+ tests
- Low areas: exploration_service (26%), game_loop (18%), incident_service (32%), auth API (28%)

### Gaps

#### Services (Priority 1)

| Service | Current | Target | Gap |
|---------|---------|--------|-----|
| exploration_service | 26.39% | 85% | +58.61% |
| game_loop | 18.45% | 80% | +61.55% |
| incident_service | 31.84% | 80% | +48.16% |
| happiness_service | 69.61% | 85% | +15.39% |
| training_service | 73.91% | 85% | +11.09% |

#### API Endpoints (Priority 2)

| Endpoint | Current | Target | Gap |
|----------|---------|--------|-----|
| auth | 28.32% | 80% | +51.68% |
| game_control | 27.20% | 80% | +52.80% |
| pregnancy | 33.96% | 80% | +46.04% |
| training | 35.71% | 80% | +44.29% |
| relationship | 29.67% | 80% | +50.33% |

### Strategy

#### 1. Add service tests
Files: test_services/test_exploration_service.py, test_game_loop.py, test_incident_service.py, test_happiness_service.py
- Full flow tests (send → events → recall → loot transfer)
- Error cases (dead dweller, invalid state)
- Edge cases (empty loot, storage full)

#### 2. Expand API tests
Files: test_api/test_auth.py, test_game_control.py, test_pregnancy.py, test_training.py
- Error responses (400, 401, 403, 404, 422, 500)
- Edge cases (invalid IDs, malformed data)
- Permission checks (user vs admin, ownership)
- Validation errors

#### 3. Mock slow ops
Problem: datetime manipulation, sleep() slow tests
Solution: pytest-freezegun or mock datetime.now()
Files: test_death_service.py, test_game_loop.py
- Mock time instead of timedelta subtraction

#### 4. Remove redundant tests
Candidates:
- Duplicate CRUD tests (covered by service tests)
- Simple tests (model `__repr__`)
- Integration tests duplicating unit tests
Target: -50 tests

#### 5. Increase granularity
Break monolithic tests into focused units:
- test_game_loop_processes_tick → test_triggers_breeding_check, test_generates_incidents, etc.
- Mock dependencies for isolation

### Optimization

#### Parallel execution
File: pyproject.toml
```toml
[tool.pytest.ini_options]
addopts = ["-n", "auto", "--dist", "loadgroup"]
```

#### Coverage thresholds
File: pyproject.toml
```toml
[tool.coverage.report]
fail_under = 70
[tool.coverage.run]
branch = true
parallel = true
```

### Timeline

#### Phase 1: Services (Week 1)

- exploration_service: 26% → 85% (+150 tests)
- game_loop: 18% → 80% (+120 tests)
- incident_service: 32% → 80% (+100 tests)

#### Phase 2: API (Week 2)

- auth: 28% → 80% (+80 tests)
- game_control: 27% → 80% (+60 tests)
- pregnancy: 34% → 80% (+50 tests)
- training: 36% → 80% (+50 tests)

#### Phase 3: Optimize (Week 3)

- Mock slow datetime ops
- Remove redundant tests (-50)
- Enable parallel execution
- Set CI thresholds

**Estimate:** +610 new, -50 removed = +560 net (1060 total)

### Acceptance
- Overall coverage ≥ 80%
- All services ≥ 75%
- All API endpoints ≥ 75%
- Test suite <3min (parallel)
- CI fails if <70%
- No tests >1s

---

## P4: datetime.utcnow() Deprecation (Deferred)

### Rationale
- Only 3 usages (1 prod, 2 tests)
- Not breaking until Python 3.14
- Low priority vs bugs/coverage
- Simple mechanical refactor

### Future
When addressed:
- Replace datetime.utcnow() → datetime.now(timezone.utc)
- Files: death_service.py (1), test_death_service.py (2)
- Add linter rule

**Deferred to:** v2.4.0+

---

## Summary

### Effort

| Task | Priority | Effort | Impact |
|------|----------|--------|--------|
| Fix exploration storage | P0 | 8h | High - prevents corruption |
| Pregnancy debug | P1 | 6h | High - enables testing |
| Coverage 46% → 80% | P1 | 40h | High - quality |
| datetime.utcnow() | P4 | 1h | Low - not urgent |

**Total:** ~54h (excluding deferred)

### Dependencies
1. Fix exploration bug before adding tests
2. Add pregnancy debug before pregnancy tests
3. Coverage can run parallel with bugs

### Metrics
- 0 storage overflow bugs
- Pregnancy testable <1min (debug)
- Coverage ≥80% on new PRs
- Test suite <3min

---

## Decisions Made

1. **Storage overflow:** ✅ DECIDED
   - NO auto-expand
   - Show dialogue window for user to manually collect dweller + goods
   - User chooses what to take when storage full

2. **Pregnancy debug access:** ✅ DECIDED
   - Simple admin UI (admin-only access)
   - Backend endpoints + basic UI for admins to force/accelerate

3. **Coverage targets:** 80% overall (per-module TBD later)

## Remaining Questions

1. **Test performance:**
   - <3min achievable with 1000+ tests?
   - DB isolation (rollback vs fresh)?
   - pytest-asyncio optimization needed?

2. **CI/CD:**
   - Coverage decrease blocks merges?
   - Generate coverage badge?
   - Publish HTML to GitHub Pages?

---

*Plan created: 2026-01-23*
*Target release: v2.3.0 (February 2026)*
