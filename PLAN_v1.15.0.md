# Fallout Shelter v1.15.0 - Implementation Plan

> **Created**: January 22, 2026
> **Target Release**: Late February/Early March 2026
> **Estimated Effort**: 5-6 weeks (single developer)

---

## Overview

Comprehensive update addressing technical debt, UX improvements, and feature additions. Focus on stability, polish, and the death system.

---

## Phase 1: Quick Wins (Week 1) - P0

### Minor Fixes
**Effort: 2 days**

#### 1. Audio Chat Stop Button
- **File**: `frontend/src/modules/chat/components/DwellerChat.vue`
- **Task**: Add stop/pause button for audio playback in chat
- **Details**: Expose stop function for `currentlyPlayingAudio`, show button when audio playing

#### 2. Animated Glow Effect
- **File**: `frontend/src/assets/tailwind.css`
- **Task**: Replace static glow with pulsing animation
- **Implementation**:
  ```css
  @keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 10px var(--color-theme-glow); }
    50% { box-shadow: 0 0 20px var(--color-theme-glow); }
  }
  ```

#### 3. Navigation Menu Animations
- **Files**: `frontend/src/core/components/common/NavBar.vue`, `SidePanel.vue`
- **Task**: Add slide/fade transitions to menu items
- **Library**: Motion Vue (`pnpm add @vueuse/motion`)

#### 4. Unique Room Restrictions (Backend)
- **Files**: `backend/app/api/v1/endpoints/rooms.py`, `backend/app/services/vault_service.py`
- **Task**: Filter out already-built unique rooms, exclude vault door from buildable
- **Details**: Backend filtering based on `is_unique()` property

#### 5. Equipment Dialog Simplification
- **File**: `frontend/src/modules/dwellers/components/DwellerEquipment.vue`
- **Task**: Remove tabs, use single column layout
- **Additional**: Expand weapon/outfit data on FE (damage, stats, bonuses, descriptions)

#### 6. AI Button Positioning & Logic
- **Files**: `DwellerDetailView.vue`, `DwellerPanel.vue`, `DwellerBio.vue`, `DwellerAppearance.vue`
- **Task**: Show "Generate" when data missing, "Regenerate" when exists
- **Rate Limiting**: Backend throttling (max 5 AI calls/minute per user)

#### 7. Remove Appearance Tooltip
- **File**: `frontend/src/modules/dwellers/components/DwellerAppearance.vue`
- **Task**: Remove `UTooltip` from dweller image hover

### Week 1 Task Breakdown
```
[ ] Audio stop button in chat (4h)
[ ] Animated glow effect (2h)
[ ] Install Motion Vue + nav animations (4h)
[ ] Backend: Unique room filtering (6h)
[ ] Backend: Vault door removal from buildable (2h)
[ ] Frontend: Equipment dialog single column + weapon/outfit data (6h)
[ ] AI button logic + rate limiting (4h)
[ ] Remove appearance tooltip (1h)
[ ] Testing & QA for minor fixes (4h)
```

---

## Phase 2: Backend Stability (Week 2-3) - P1

### Test Coverage - Target 80%
**Effort: 1.5 weeks**

#### Priority 1: Security & Infrastructure (Week 2)
| File | Current | Target |
|------|---------|--------|
| `app/middleware/security.py` | 0% | 85% |
| `app/db/init_db.py` | 0% | 75% |
| `app/api/celery_task.py` | 0% | 70% |

#### Priority 2: Critical Services (Week 2-3)
| File | Current | Target |
|------|---------|--------|
| `app/services/incident_service.py` | 28% | 75% |
| `app/services/game_loop.py` | 54% | 80% |
| `app/services/dweller_ai.py` | 26% | 70% |
| `app/services/health_check.py` | 24% | 70% |

#### Skip/Low Priority (stable, low ROI)
- MinIO service (22% - external dependency)
- WebSocket manager (29% - complex)
- Static data loaders (working as expected)

### Datetime Deprecation Fix
**Effort: 1 day**

- Global replace: `datetime.utcnow()` → `datetime.now(timezone.utc)`
- Add import: `from datetime import timezone`
- ~50 occurrences across codebase
- Full test suite verification

### Week 2 Task Breakdown
```
[ ] Security middleware tests (8h)
[ ] DB initialization tests (6h)
[ ] Celery task tests (6h)
[ ] Incident service tests (8h)
[ ] Datetime deprecation fix (6h)
[ ] Run full test suite (2h)
```

### Week 3 Task Breakdown (Backend + Frontend Start)
```
[ ] Game loop tests (8h)
[ ] Dweller AI tests (8h)
[ ] Health check tests (6h)
[ ] Frontend: Fix TS warnings (6h)
[ ] Frontend: Store type safety (6h)
```

---

## Phase 3: Frontend Polish (Week 3-4) - P1

### TypeScript Fixes
**Effort: 3 days**

1. **Fix Component Warnings**:
   - `UnassignedDwellers.vue`: Fix readonly computed errors
   - `RoomDetailModal.vue`: Add missing `modelValue` prop

2. **Store Type Safety**:
   - Audit Pinia stores for `any` usage
   - Add proper return types to actions/getters

3. **Strict Build**:
   - Run `pnpm run build:strict` and fix all errors

### Component Refactoring
**Effort: 4 days**

#### DwellerCard.vue (813 lines) → Extract:
- `DwellerCardHeader.vue` (avatar, name, level)
- `DwellerCardStats.vue` (SPECIAL, health, XP)
- `DwellerCardActions.vue` (buttons, menus)

#### RoomGrid.vue (814 lines) → Extract:
- `RoomGridCell.vue` (single room/empty cell logic)
- `RoomGridControls.vue` (build mode, overlay controls)

### Motion Vue Integration
**Effort: 2 days**

```bash
pnpm add @vueuse/motion
```

**Target Animations**:
- Menu hover/active states (subtle slide)
- Modal enter/exit (fade + scale)
- Toast notifications (slide-in from top)
- Room build animation (flash + glow)
- Loading skeletons (shimmer effect)

**Performance**: Keep animations under 16ms (60fps), use `will-change` sparingly

### Week 4 Task Breakdown
```
[ ] DwellerCard refactoring (8h)
[ ] RoomGrid refactoring (8h)
[ ] Motion Vue integration (6h)
[ ] Loading states (6h)
[ ] Error handling (4h)
[ ] Mobile responsiveness (4h)
```

---

## Phase 4: UX Enhancements (Week 4) - P2

### Loading States
**Effort: 2 days**

- Expand skeleton loader usage (`DwellerGridItemSkeleton.vue`)
- Consistent spinner component
- Loading overlays for async actions

### Error Handling
**Effort: 1 day**

- User-friendly error messages (map technical errors)
- Retry button for failed API calls
- Toast stacking improvements

### Mobile Responsiveness
**Effort: 1 day**

- Test room grid on mobile (touch interactions)
- Modal responsiveness check
- Navigation drawer on mobile

---

## Phase 5: Death System (Week 5) - P1

**Effort: 1 week**

### Backend Implementation

#### 1. Death State Model
```python
# Add to dweller model
is_dead: bool = Field(default=False)
death_timestamp: datetime | None = Field(default=None)
```

#### 2. Death Triggers
- Health reaches 0 (exploration, incidents)
- Radiation damage threshold
- Update game loop to check death conditions

#### 3. Revival System
```python
# backend/app/services/revival_service.py
def calculate_revival_cost(dweller_level: int) -> int:
    """Level-based cost, capped at 1000 caps."""
    base_cost = dweller_level * 50
    return min(base_cost, 1000)
```

- Endpoint: `POST /api/v1/dwellers/{id}/revive`
- Cost: Level × 50 caps, max 1000
- Auto-revival option (time-based, 24h cooldown)

### Frontend Implementation

#### 1. Death UI
- Death modal/notification
- Grayed-out dweller cards for dead dwellers
- Revival button with cost display
- Confirmation dialog before revival

#### 2. Memorial System (Optional)
- Death log/history view
- Stats: total deaths, causes

### Week 5 Task Breakdown
```
[ ] Backend: Death model changes + migration (4h)
[ ] Backend: Death triggers in game loop (6h)
[ ] Backend: Revival service + endpoint (6h)
[ ] Frontend: Death UI components (8h)
[ ] Frontend: Revival flow (4h)
[ ] Testing death system (4h)
```

---

## Phase 6: Final Polish (Week 5-6) - P3

### Accessibility (Essential Only)
**Effort: 2 days**

- Keyboard navigation for modals (Esc to close, Tab focus trap)
- ARIA labels on interactive elements
- Focus management improvements

### Documentation
**Effort: 1 day**

- Update ROADMAP.md with v1.15.0
- Update CHANGELOG.md
- Document Motion Vue usage patterns
- API docs for death/revival endpoints

### Performance Optimization
**Effort: 2 days**

- Database query audit (check N+1 in dweller relationships)
- Add indexes if missing
- Frontend: Lazy load dweller images
- Room grid rendering optimization

### Week 6 Task Breakdown
```
[ ] Performance optimization (6h)
[ ] Accessibility improvements (6h)
[ ] Documentation updates (4h)
[ ] Integration testing (6h)
[ ] Bug fixes from testing (8h)
[ ] Release preparation (4h)
```

---

## Phase 7: DevOps & Tooling - P2

### ty Type Checker Integration
**Effort: 4 hours**

#### Setup
Add `ty` to CI pipeline for stricter type checking than mypy/pyright.

#### Configuration (`backend/ty.toml`)
```toml
[tool.ty]
python-version = "3.13"

# Exclusions - files with known issues or external dependencies
exclude = [
    "alembic/",
    "locust/",
    "app/tests/",
    "__pycache__/",
]
```

#### Usage
```bash
# Run locally
cd backend
uv run ty check app/

# With exclusions
uv run ty check app/ --exclude "app/tests/" --exclude "alembic/"
```

#### CI Integration
Add to `.github/workflows/backend-ci.yml`:
```yaml
- name: Run type checker (ty)
  working-directory: backend
  run: |
    uv run ty check app/ \
      --exclude "app/tests/" \
      --exclude "alembic/" \
      --exclude "locust/"
```

#### Known Exclusions (to fix incrementally)
- `app/api/celery_task.py` - Celery typing issues
- `app/db/init_db.py` - SQLModel type inference
- `app/tests/` - Test mocking complexity
- `alembic/` - Auto-generated migrations
- `locust/` - Load testing scripts

### Locust Performance Testing CI
**Effort: 4 hours**

#### Weekly Performance Test Workflow
Create `.github/workflows/performance.yml`:
```yaml
name: Weekly Performance Tests

on:
  schedule:
    # Run every Sunday at 2 AM UTC (if code changed)
    - cron: '0 2 * * 0'
  workflow_dispatch:  # Manual trigger

jobs:
  check-changes:
    runs-on: ubuntu-latest
    outputs:
      has_changes: ${{ steps.check.outputs.has_changes }}
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
      - name: Check for code changes in last week
        id: check
        run: |
          LAST_WEEK=$(date -d '7 days ago' +%Y-%m-%d)
          CHANGES=$(git log --since="$LAST_WEEK" --oneline -- backend/ | wc -l)
          if [ "$CHANGES" -gt 0 ]; then
            echo "has_changes=true" >> $GITHUB_OUTPUT
          else
            echo "has_changes=false" >> $GITHUB_OUTPUT
          fi

  performance-test:
    needs: check-changes
    if: needs.check-changes.outputs.has_changes == 'true' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:18
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: fallout_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v5

      - name: Install uv
        uses: astral-sh/setup-uv@v7
        with:
          enable-cache: true

      - name: Set up Python
        working-directory: backend
        run: uv python install

      - name: Install dependencies
        working-directory: backend
        run: uv sync --locked --all-extras

      - name: Setup test environment
        working-directory: backend
        run: |
          cp .env.example .env
          echo "POSTGRES_SERVER=localhost" >> .env
          echo "POSTGRES_DB=fallout_test" >> .env

      - name: Run database migrations
        working-directory: backend
        run: uv run alembic upgrade head

      - name: Start API server
        working-directory: backend
        run: |
          uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
          sleep 10  # Wait for server to start

      - name: Run Locust performance tests
        working-directory: backend
        run: |
          uv run locust -f locust/locustfile.py \
            --host http://localhost:8000 \
            --users 20 \
            --spawn-rate 5 \
            --run-time 5m \
            --headless \
            --html locust-report.html \
            --csv locust-results \
            --only-summary

      - name: Upload performance report
        uses: actions/upload-artifact@v4
        with:
          name: performance-report-${{ github.run_number }}
          path: |
            backend/locust-report.html
            backend/locust-results*.csv
          retention-days: 30

      - name: Check performance thresholds
        working-directory: backend
        run: |
          # Parse CSV and check P95 response times
          P95=$(tail -1 locust-results_stats.csv | cut -d',' -f10)
          if [ "$P95" -gt 2000 ]; then
            echo "⚠️ P95 response time ($P95 ms) exceeds threshold (2000ms)"
            exit 1
          fi
          echo "✅ P95 response time: ${P95}ms (threshold: 2000ms)"
```

#### Task Breakdown
```
[ ] Create ty.toml configuration (1h)
[ ] Add ty check to backend-ci.yml (1h)
[ ] Fix critical ty errors or add exclusions (2h)
[ ] Create performance.yml workflow (2h)
[ ] Test workflow with manual trigger (1h)
[ ] Document ty usage in AGENTS.md (1h)
```

---

## Technical Notes

### Equipment Data Enhancement
```typescript
// frontend/src/modules/combat/models/equipment.ts
interface Weapon {
  id: string
  name: string
  damage: number          // ADD
  damage_type: string     // ADD (energy, ballistic, melee)
  fire_rate: number       // ADD
  special_bonus?: Record<string, number> // ADD
  description?: string    // ADD
}

interface Outfit {
  id: string
  name: string
  defense: number         // ADD
  radiation_resist: number // ADD
  special_bonus: Record<string, number> // ADD
  description?: string    // ADD
}
```

### AI Rate Limiting
```python
# backend/app/api/v1/endpoints/dwellers.py
from fastapi_guard import RateLimiter

@router.post("/{dweller_id}/generate-info")
@RateLimiter(max_calls=5, window=60)  # 5 calls per minute
async def generate_dweller_info(...):
    ...
```

### Motion Vue Example
```vue
<template>
  <div
    v-motion
    :initial="{ opacity: 0, y: -20 }"
    :enter="{ opacity: 1, y: 0 }"
    :leave="{ opacity: 0, y: -20 }"
  >
    <RoomCard />
  </div>
</template>
```

---

## Testing Checklist

### Before Release
- [ ] All 321+ backend tests passing
- [ ] All 88+ frontend tests passing
- [ ] `pnpm run build:strict` passes
- [ ] Backend coverage ≥ 80%
- [ ] No TypeScript errors
- [ ] No deprecation warnings
- [ ] `uv run ty check` passes (with exclusions)
- [ ] Locust performance test P95 < 2000ms
- [ ] Manual testing: Death system end-to-end
- [ ] Manual testing: Unique room filtering
- [ ] Manual testing: Equipment dialog
- [ ] Manual testing: AI generation + rate limiting
- [ ] Mobile testing on real device
- [ ] Cross-browser check (Chrome, Firefox)

---

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Death system breaks game loop | Comprehensive tests, feature flag for gradual rollout |
| Motion Vue performance issues | Disable animations on low FPS detection |
| Backend test coverage time overrun | Focus on critical paths only (security, game loop, incidents) |
| Equipment data missing on backend | Check API response, add migration if needed |
| Unique room filtering edge cases | Test with multiple vaults, different room types |

---

## Success Metrics

- [ ] Backend coverage: 67% → 80%+
- [ ] 0 TypeScript strict build errors
- [ ] 0 datetime deprecation warnings
- [ ] All 7 minor fixes complete
- [ ] Death system functional
- [ ] Smooth animations (no jank)
- [ ] Equipment dialog improved UX
- [ ] AI rate limiting working
- [ ] ty type checker integrated in CI
- [ ] Weekly Locust performance tests running

---

## Out of Scope (Future v1.16+)

- Sound effects system
- Full WCAG 2.1 AA compliance
- Memorial/graveyard detailed view
- Virtual scrolling for dweller lists
- Crafting system
- Pet system

---

## Decision Log

| Question | Decision |
|----------|----------|
| Animation library | Motion Vue |
| Sound effects | Future (v1.16+) |
| Death revival cost | Level × 50 caps, max 1000 |
| Unique room filtering | Backend handles filtering |
| Equipment dialog layout | Single column |
| Animation performance budget | 60fps target, don't overuse |
| AI generation buttons | "Generate" when missing, "Regenerate" when exists + rate limiting |
| Test coverage target | 80% (cover essentials) |
| ty type checker | Integrate with exclusions for problematic files |
| Locust CI | Weekly runs, only if code changed |

---

*Plan approved: January 22, 2026*
