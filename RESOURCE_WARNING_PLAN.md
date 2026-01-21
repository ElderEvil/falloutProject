# Resource Warning UI Implementation Plan

**Task**: Resource Warning UI - Toast notifications for low resources (< 20% warning, < 10% critical), power outage effects
**Priority**: P1 (High) - Current Sprint: Post-Deployment Polish
**Source**: ROADMAP.md line 83-84
**Date**: January 18, 2026

## 🎯 Objective

Implement a comprehensive resource warning system that alerts players when vault resources are running low, with visual feedback for critical situations like power outages.

## 📋 Task Breakdown

### Phase 1: Analysis & Design (Tasks 1-2)

#### Task 1: Analyze existing resource system and current UI implementation
**Status**: Pending
**Estimated Time**: 2 hours

**Investigation Areas:**
- Current resource models in `backend/app/models/`
- Existing resource management endpoints in `backend/app/api/v1/endpoints/`
- Frontend resource stores and components
- Current toast notification system implementation
- Power system integration with room operations

**Key Questions:**
- What resources need monitoring? (power, water, food, bottle caps, etc.)
- How are resources currently tracked and updated?
- What's the existing notification infrastructure?
- How does power outage currently affect the vault?

#### Task 2: Design toast notification system for low resource warnings
**Status**: Pending
**Estimated Time**: 1 hour

**Design Specifications:**
- **Warning Levels**:
  - < 20%: Yellow warning toast
  - < 10%: Red critical toast
  - Power outage: Special red toast with outage icon
- **Toast Behavior**:
  - Auto-dismiss after 10 seconds (except critical)
  - Can be manually dismissed
  - Rate limiting: Max 1 toast per resource type per 30 seconds
  - Stacking: Multiple resource warnings stack vertically
- **Visual Design**:
  - Terminal-themed with appropriate colors
  - Resource icons (power, water, food, caps)
  - Current percentage displayed
  - Action button for quick resource management

### Phase 2: Backend Implementation (Task 3)

#### Task 3: Implement backend resource monitoring and warning thresholds
**Status**: Pending
**Estimated Time**: 4 hours

**Implementation Steps:**
1. **Create Resource Warning Service** (`backend/app/services/resource_warning.py`)
   - Monitor resource levels against thresholds
   - Generate warning events
   - Handle power outage detection

2. **Add Warning Endpoints** (`backend/app/api/v1/endpoints/resources.py`)
   - GET `/resources/warnings` - Current warning status
   - POST `/resources/warnings/acknowledge` - Dismiss warnings
   - WebSocket integration for real-time updates

3. **Database Updates** (if needed)
   - Add warning tracking table
   - Store last warning timestamps for rate limiting

4. **Background Tasks**
   - Celery task for periodic resource checking
   - Power outage monitoring

### Phase 3: Frontend Implementation (Task 4)

#### Task 4: Create frontend resource warning UI components
**Status**: Pending
**Estimated Time**: 6 hours

**Components to Create:**
1. **ResourceWarningToast** (`frontend/src/components/ui/ResourceWarningToast.vue`)
   - Terminal-themed warning toast
   - Resource-specific icons and colors
   - Dismiss functionality
   - Action buttons for resource management

2. **ResourceWarningStore** (`frontend/src/stores/resourceWarning.ts`)
   - Pinia store for warning state
   - WebSocket integration
   - Rate limiting and deduplication

3. **ResourceWarningManager** (`frontend/src/composables/useResourceWarnings.ts`)
   - Composable for warning logic
   - Toast display management
   - Integration with existing toast system

### Phase 4: Advanced Features (Tasks 5-6)

#### Task 5: Implement power outage effects and visual indicators
**Status**: Pending
**Estimated Time**: 3 hours

**Power Outage Effects:**
- **Visual Indicators**:
  - Red flashing border around vault view
  - Power icon overlay on affected rooms
  - Darkened room tiles without power

- **Functional Effects**:
  - Room production stops
  - Existing warning toasts become more prominent
  - Special power outage modal option

#### Task 6: Add WebSocket real-time resource updates
**Status**: Pending
**Estimated Time**: 2 hours

**WebSocket Integration:**
- Extend existing WebSocket system for resource updates
- Real-time warning notifications
- Efficient update batching to prevent spam

### Phase 5: Testing & Documentation (Tasks 7-8)

#### Task 7: Write tests for resource warning system
**Status**: Pending
**Estimated Time**: 3 hours

**Test Coverage:**
- **Backend Tests**:
  - Resource warning service logic
  - Threshold calculations
  - Endpoint responses
  - WebSocket message handling

- **Frontend Tests**:
  - Toast component rendering
  - Store state management
  - Composable functionality
  - Integration with resource system

#### Task 8: Update documentation and run quality checks
**Status**: Pending
**Estimated Time**: 1 hour

**Documentation Updates:**
- Update README.md with new features
- Add API documentation for warning endpoints
- Update frontend component documentation

**Quality Checks:**
- Run backend: `uv run ruff check . && uv run pytest app/tests/`
- Run frontend: `pnpm run lint && pnpm test`
- Verify code coverage thresholds

## 🔧 Technical Requirements

### Backend Dependencies
- FastAPI WebSocket support (already implemented)
- Celery for background tasks (already implemented)
- Redis for rate limiting (already implemented)

### Frontend Dependencies
- Pinia for state management (already implemented)
- Vue 3 Composition API (already implemented)
- Existing UI component system (UToast, etc.)

### Integration Points
- Existing resource management system
- Current toast notification system
- Power/room management integration
- WebSocket infrastructure

## 🚀 Success Criteria

1. **Functional Requirements**:
   - Resource warnings trigger at correct thresholds (20%, 10%)
   - Toast notifications display properly with correct styling
   - Power outage effects are visually distinct
   - Real-time updates work via WebSocket
   - Rate limiting prevents spam

2. **Quality Requirements**:
   - Backend test coverage >80% for new code
   - Frontend test coverage >70% for new code
   - No linting errors
   - Performance impact minimal

3. **UX Requirements**:
   - Warnings are informative but not annoying
   - Critical situations get appropriate attention
   - Interface remains responsive during warnings
   - Terminal theme consistency maintained

## 📊 Timeline Estimation

**Total Estimated Time**: 22 hours
**Planned Duration**: 3-4 days

**Daily Breakdown:**
- **Day 1**: Tasks 1-2 (Analysis & Design) + Task 3 (Backend service)
- **Day 2**: Task 3 completion + Task 4 (Frontend components)
- **Day 3**: Task 4 completion + Task 5 (Power outage effects)
- **Day 4**: Tasks 6-8 (WebSocket, tests, documentation)

## 🚨 Potential Risks & Mitigations

### Risk 1: Performance impact from frequent resource checking
**Mitigation**: Use efficient database queries, implement caching, limit check frequency

### Risk 2: Toast notification spam during resource crises
**Mitigation**: Implement smart rate limiting, group similar warnings, priority-based display

### Risk 3: WebSocket connection issues affecting real-time updates
**Mitigation**: Robust reconnection logic, fallback to polling, proper error handling

### Risk 4: Integration conflicts with existing resource system
**Mitigation**: Careful analysis of existing code, incremental implementation, thorough testing

## 🎯 Next Steps

1. Begin with Task 1: Analyze existing resource system
2. Review and refine this plan based on findings
3. Implement incrementally with frequent testing
4. Regular progress updates and plan adjustments

---

**This plan will be updated as implementation progresses and new insights are discovered.**
