# Test Coverage Analysis & Optimization Plan

## Current State

| Metric | Value |
|--------|-------|
| **Overall Coverage** | 70.93% |
| **Total Tests** | 933 passed, 1 skipped |
| **Execution Time** | 4:24 (264 seconds) |
| **Target Coverage** | 80%+ |
| **Gap to Target** | ~9% (~1,200 lines) |

## Coverage Distribution

| Category | Files | Missing Lines | Avg Coverage |
|----------|-------|---------------|--------------|
| Critical (services) | 52 | 1,773 | ~65% |
| Important (endpoints, CRUD) | 49 | 1,157 | ~60% |
| Low Priority (CLI, scripts) | 6 | 333 | 0% |
| Skip (utils, models, etc.) | 102 | 658 | ~85% |

## Top Coverage Gaps (By Impact)

### Critical Services (1,773 missing lines)

| File | Current | Missing | Priority |
|------|---------|---------|----------|
| `services/open_ai.py` | 36.9% | 135 | HIGH |
| `services/health_check.py` | 31.5% | 113 | HIGH |
| `services/dweller_assignment_service.py` | 40.8% | 87 | HIGH |
| `services/pregen_service.py` | 0.0% | 82 | SKIP |
| `services/objective_assignment_service.py` | 23.8% | 80 | HIGH |
| `services/dweller_ai.py` | 60.5% | 75 | MEDIUM |
| `services/chat_service.py` | 55.9% | 63 | MEDIUM |
| `services/vault_service.py` | 68.8% | 98 | MEDIUM |
| `services/game_loop.py` | 66.8% | 133 | MEDIUM |
| `services/exploration/coordinator.py` | 79.9% | 59 | LOW |

### Important Endpoints/CRUD (1,157 missing lines)

| File | Current | Missing | Priority |
|------|---------|---------|----------|
| `crud/room.py` | 48.0% | 103 | HIGH |
| `api/v1/endpoints/debug.py` | 32.1% | 76 | LOW |
| `crud/item_base.py` | 53.7% | 76 | MEDIUM |
| `crud/base.py` | 48.0% | 66 | LOW |
| `crud/dweller.py` | 69.8% | 61 | MEDIUM |
| `api/v1/endpoints/dweller.py` | 59.6% | 55 | MEDIUM |
| `api/v1/endpoints/training.py` | 40.3% | 43 | HIGH |
| `api/v1/endpoints/relationship.py` | 46.8% | 41 | HIGH |
| `api/v1/endpoints/user.py` | 54.9% | 41 | MEDIUM |

### Low Priority (CLI/Scripts) - SKIP

| File | Current | Missing | Reason |
|------|---------|---------|--------|
| `scripts/migrate_quest_data.py` | 0.0% | 128 | One-time migration |
| `cli/main.py` | 0.0% | 62 | CLI tool |
| `cli/migrations/cli.py` | 0.0% | 44 | Migration CLI |
| `cli/app/dweller_bios.py` | 0.0% | 37 | CLI tool |
| `cli/app/pregen_dwellers.py` | 0.0% | 34 | CLI tool |
| `cli/app/manage.py` | 0.0% | 28 | CLI tool |

## Optimization Recommendations

### 1. Speed Optimizations (Expected: 40-50% faster)

#### A. Parallel Execution with pytest-xdist

```bash
# Install
uv add --group dev pytest-xdist

# Run tests in parallel
uv run pytest -n auto

# Expected: 4:24 → ~2:30 (40% faster)
```

#### B. Test Categorization with Markers

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Fast unit tests (< 100ms each)",
    "integration: Integration tests with database",
    "slow: Tests taking > 1 second",
    "e2e: End-to-end workflow tests",
]
```

```bash
# Fast feedback loop (unit tests only)
uv run pytest -m unit -q  # ~30 seconds

# Full suite (CI)
uv run pytest -q  # ~2:30 with xdist
```

#### C. Session-Scoped Fixtures Where Possible

```python
# Instead of per-test engine
@pytest_asyncio.fixture
async def engine():
    ...

# Use session-scoped engine
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    ...
```

### 2. Coverage Improvements (Expected: 70.93% → 82%+)

#### Phase 1: High-Impact Services (+5% coverage, ~670 lines)

Focus on services with highest missing lines:

| Service | Missing Lines | Test Strategy |
|---------|---------------|---------------|
| `open_ai.py` | 135 | Mock external API calls |
| `health_check.py` | 113 | Mock database/service checks |
| `dweller_assignment_service.py` | 87 | Unit tests with mocked DB |
| `objective_assignment_service.py` | 80 | Unit tests with mocked DB |
| `dweller_ai.py` | 75 | Mock AI service calls |
| `chat_service.py` | 63 | Mock AI service, test message flow |

**Estimated time:** 4-6 hours
**Coverage gain:** +5% (70.93% → 76%)

#### Phase 2: CRUD & Endpoints (+3% coverage, ~400 lines)

| Module | Missing Lines | Test Strategy |
|--------|---------------|---------------|
| `crud/room.py` | 103 | Test all CRUD operations |
| `crud/item_base.py` | 76 | Test inheritance patterns |
| `endpoints/training.py` | 43 | API tests with mocked services |
| `endpoints/relationship.py` | 41 | API tests with mocked services |

**Estimated time:** 3-4 hours
**Coverage gain:** +3% (76% → 79%)

#### Phase 3: Remaining Gaps (+2% coverage, ~200 lines)

Fill smaller gaps across multiple files.

**Estimated time:** 2-3 hours
**Coverage gain:** +2% (79% → 81%)

### 3. Test Organization

#### A. Separate Test Types

```
app/tests/
├── unit/           # Fast, no DB, mocked deps
│   ├── services/
│   └── crud/
├── integration/    # DB tests, real services
│   ├── api/
│   └── services/
├── e2e/           # Full workflow tests
└── conftest.py    # Shared fixtures
```

#### B. Run Tests Selectively

```bash
# Quick feedback (development)
uv run pytest -m unit -q

# Pre-commit (unit + integration)
uv run pytest -m "unit or integration" -q

# Full suite (CI/nightly)
uv run pytest -q
```

### 4. Fixture Optimization

#### A. Use StaticPool for SQLite Tests

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    return create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,  # Shared connection
    )
```

#### B. Transaction Rollback Isolation

```python
@pytest_asyncio.fixture
async def db_session(engine):
    async with engine.connect() as conn:
        txn = await conn.begin()
        async with AsyncSession(bind=conn, join_transaction_mode="create_savepoint") as session:
            yield session
        await txn.rollback()  # No cleanup needed
```

#### C. Cache Static Test Data

```python
# conftest.py
@pytest.fixture(scope="session")
def static_data():
    return load_test_data()  # Load once per session
```

## Implementation Plan

### Week 1: Speed Optimizations

- [ ] Add pytest-xdist dependency
- [ ] Add test markers (unit, integration, slow, e2e)
- [ ] Optimize session-scoped fixtures
- [ ] Run parallel tests, verify no flakiness
- **Expected result:** 4:24 → ~2:30

### Week 2: Coverage Phase 1 (High-Impact Services)

- [ ] Write tests for `open_ai.py` (mock external API)
- [ ] Write tests for `health_check.py` (mock DB checks)
- [ ] Write tests for `dweller_assignment_service.py`
- [ ] Write tests for `objective_assignment_service.py`
- **Expected result:** 70.93% → 76%

### Week 3: Coverage Phase 2 (CRUD & Endpoints)

- [ ] Write tests for `crud/room.py`
- [ ] Write tests for `crud/item_base.py`
- [ ] Write tests for `endpoints/training.py`
- [ ] Write tests for `endpoints/relationship.py`
- **Expected result:** 76% → 79%

### Week 4: Coverage Phase 3 & Polish

- [ ] Fill remaining gaps
- [ ] Verify no flaky tests
- [ ] Update CI configuration
- **Expected result:** 79% → 82%

## Success Metrics

| Metric | Current | Target | Strategy |
|--------|---------|--------|----------|
| Coverage | 70.93% | 82%+ | Focus on high-impact services |
| Test Speed | 4:24 | < 2:30 | pytest-xdist + fixture optimization |
| Flaky Tests | Unknown | 0 | Transaction rollback isolation |
| Test Categories | None | 4 markers | unit, integration, slow, e2e |

## Files to Exclusion from Coverage (Low Value)

```toml
# pyproject.toml
[tool.coverage.run]
omit = [
    "app/cli/*",           # CLI tools
    "app/scripts/*",       # One-time migrations
    "app/admin/auth.py",   # Admin-only
    "app/api/tasks.py",    # Background tasks (test separately)
    "app/services/pregen_service.py",  # One-time data generation
]
```

This will increase apparent coverage by ~2% without writing tests.
