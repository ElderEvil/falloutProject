# Architectural Decisions

## Test Structure
- Backend: API integration tests (not unit tests) - tests full HTTP → DB flow
- Frontend: Component unit tests with mocked services
- Junk pricing: Assert exact values (2/50/200), not just non-zero
- Scrap randomness: Don't mock random.random(), just verify junk created

## Test Location
- Frontend tests: Co-located in `src/modules/*/__tests__/` (NOT `tests/unit/`)
- Backend tests: Existing structure in `backend/app/tests/test_api/`

## Coverage Targets
- Backend: >80% for storage/weapon/outfit/junk modules
- Frontend: >15% overall (establishing baseline)
