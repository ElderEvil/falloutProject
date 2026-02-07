# Development Plans

## Current Branch: feat/2.9.0

This document contains the active development plans for the current branch.

---

# Plan 1: v2.9.0 — Conversation Happiness + Tool-Based Dweller Suggestions

## TL;DR

> **Quick Summary**: Extend dweller chat so each exchange can immediately adjust dweller + vault happiness based on LLM sentiment (-5..+5), and (optionally) propose a primitive next action using **PydanticAI `@agent.tool`**.
>
> **Deliverables**:
> - Chat endpoints return `happiness_impact` (structured) and optional `action_suggestion`
> - Dweller happiness updates immediately (clamped 10..100) + vault happiness recalculated immediately
> - Neutral fallback on sentiment failure (chat still succeeds)
> - Frontend chat UI displays happiness impact and optional suggestion + confirm-to-apply
> - WebSocket pushes chat-scoped notifications (typing + new events) even though messages remain REST-based
>
> **Status**: ✅ COMPLETED
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Backend schemas/agents → chat endpoints apply happiness → frontend types + UI

## Success Criteria (All Met ✅)

### Final Checklist
- [x] Chat text endpoint returns structured `happiness_impact`
- [x] Voice chat JSON endpoint returns structured `happiness_impact`
- [x] Dweller happiness is updated and clamped 10..100
- [x] Vault happiness updated immediately and returned as int
- [x] Neutral fallback works when sentiment/tooling fails
- [x] Chat UI displays impact and optional suggestion; confirm executes action
- [x] No new DB persistence added for sentiment metadata
- [x] PydanticAI Gateway migration not included

---

# Plan 2: Fix Chat Action Suggestions (Latest-only + Message-ID stickiness)

## TL;DR

> **Quick Summary**: Fix chat UI so action suggestions do **not** appear on every dweller message. Suggestions must **stick to the correct message** (ID-based correlation) and only the **latest actionable** suggestion is visible.
>
> **Deliverables**:
> - Backend: chat HTTP responses include `dweller_message_id`; WebSocket `action_suggestion` payload includes `message_id`.
> - Frontend: `DwellerChat.vue` correlates WS suggestions by message id; UI shows **only latest actionable** suggestion; no duplication.
> - Tests (TDD): Extend existing backend pytest + frontend Vitest coverage to reproduce and lock the behavior.
>
> **Estimated Effort**: Medium
> **Parallel Execution**: YES (2 waves)
> **Critical Path**: Backend contract (IDs) → regenerate TS types → Frontend correlation + latest-only rendering

---

## Context

### Original Request
- Fix 2 bugs:
  1) Action suggestions appear on **every** dweller message.
  2) Desired: suggestions should either live near the send box or "stick" to the related message.

### Interview Summary (Decisions)
- **Placement**: Stick to the related message (in the message timeline), not a separate panel.
- **Visibility**: **Latest only** (only one suggestion visible at a time).
- **If newer dweller message has `null`/`no_action`**: keep showing the previous actionable suggestion until replaced/dismissed.
- **Dismiss behavior**: dismiss per message; dismissal should not globally disable suggestions.
- **Stickiness level**: **True stickiness by message id** (WS suggestion must target the originating message; not "last dweller message").
- **Test strategy**: YES (TDD). Frontend Vitest + backend pytest.

### Key Code Findings (References)
- Frontend renders suggestions in:
  - `frontend/src/modules/chat/components/DwellerChat.vue`
    - Suggestion card condition currently: `message.type === 'dweller' && message.actionSuggestion && message.actionSuggestion.action_type !== 'no_action'`
    - WebSocket handler currently updates **last dweller message** (heuristic) for `action_suggestion` events.
- Frontend types:
  - `frontend/src/modules/chat/models/chat.ts` → `ChatMessageDisplay.actionSuggestion?: ActionSuggestion | null`
  - `frontend/src/modules/chat/stores/chat.ts` exists but is a placeholder (state is component-local in `DwellerChat.vue`).
- Backend endpoints + schemas:
  - `backend/app/api/v1/endpoints/chat.py` (text + voice chat endpoints; emits WS messages)
  - `backend/app/schemas/chat.py` (`DwellerChatResponse`, `DwellerVoiceChatResponse`, `ActionSuggestion` union)
  - `backend/app/models/chat_message.py` (DB `ChatMessage.id: UUID4` exists; action suggestions are **not** persisted)
- Existing tests to extend:
  - Backend: `backend/app/tests/test_api/test_chat.py` (already mocks AI agent + WS manager)
  - Frontend: `frontend/tests/unit/components/chat/DwellerChat.test.ts` (already tests `.action-suggestion-card` and WS flows)

### Metis Review (Gap/Guardrail Synthesis)
- **Main risk**: WS `action_suggestion` payload has no correlation id → out-of-order events can attach to the wrong message.
- **Guardrails**:
  - Do **not** redesign chat UI or move suggestions to composer.
  - Do **not** change AI suggestion generation logic or persistence model.
  - Keep changes minimal and backwards-compatible where possible (additive fields).
  - Add handling for WS suggestion arriving before the message exists in UI (pending map).

---

## Work Objectives

### Core Objective
Ensure action suggestions:
1) never duplicate across unrelated messages,
2) attach to the correct message via message id correlation,
3) only the latest actionable suggestion is visible.

### Concrete Deliverables
- Backend:
  - Add `dweller_message_id` (UUID) to `DwellerChatResponse` and `DwellerVoiceChatResponse`.
  - Include `message_id` in WebSocket `action_suggestion` payload.
- Frontend:
  - Track `id` on `ChatMessageDisplay` for dweller messages.
  - Update WS handler to attach suggestions by `message_id`.
  - Render suggestion card only for the computed "latest actionable suggestion message".

### Definition of Done
- Backend tests pass: `cd backend && uv run pytest app/tests/test_api/test_chat.py -v`
- Frontend tests pass: `cd frontend && pnpm run test -- tests/unit/components/chat/DwellerChat.test.ts`
- Frontend typecheck passes: `cd frontend && pnpm run typecheck`

### Must NOT Have (Guardrails)
- No DB migration adding suggestion persistence.
- No new UI panel near composer.
- No broad refactors to Pinia store architecture.
- No human-in-the-loop verification steps.

---

## Verification Strategy (MANDATORY)

### Universal Rule
All verification must be agent-executed (tests + scripted QA). No "user manually checks".

### Test Decision
- **Infrastructure exists**: YES
- **Automated tests**: YES (TDD)
- **Frameworks**: Backend pytest; Frontend Vitest

### Agent-Executed QA Scenarios (E2E sanity)
These complement unit tests and ensure real UI behavior.

---

## Execution Strategy

### Parallel Execution Waves

Wave 1 (Backend contract + tests):
├── Task 1: Add backend tests (RED)
└── Task 2: Implement backend fields (GREEN) + update WS payload

Wave 2 (Frontend correlation + latest-only rendering):
├── Task 3: Regenerate TS API types (depends: Task 2)
├── Task 4: Frontend tests (RED) for latest-only + ID-based WS correlation
└── Task 5: Implement frontend fixes (GREEN) + E2E QA scenarios

Critical Path: 1 → 2 → 3 → 4 → 5

---

## TODOs

> Implementation + tests in the same task (TDD). Each task includes agent-executed QA.

### 1) Backend (TDD): Add message IDs to chat responses + WS payload

- [x] 1. Add failing backend tests for `dweller_message_id` + WS `message_id`

  **What to do (RED)**:
  - In `backend/app/tests/test_api/test_chat.py`, add/extend tests for:
    - `POST /api/v1/chat/{dweller_id}` response includes `dweller_message_id` (UUID)
    - When WS manager is called for `action_suggestion`, payload includes `message_id` matching that `dweller_message_id`
    - Same for `POST /api/v1/chat/{dweller_id}/voice` (voice chat) if applicable in tests

  **References**:
  - `backend/app/tests/test_api/test_chat.py` — existing chat endpoint tests + mocking patterns
  - `backend/app/api/v1/endpoints/chat.py` — endpoints where response + WS send occur
  - `backend/app/schemas/chat.py` — response schema types to extend

  **Acceptance Criteria (tests)**:
  - `cd backend && uv run pytest app/tests/test_api/test_chat.py -k "dweller_message_id or message_id" -v` → FAIL before implementation

  **Agent-Executed QA Scenario**:
  - Tool: Bash
  - Steps:
    1. Run: `cd backend && uv run pytest app/tests/test_api/test_chat.py -k "dweller_message_id" -v`
  - Expected: tests fail with missing field / missing WS payload key.

- [x] 2. Implement backend contract changes (GREEN)

  **What to do**:
  - Update `backend/app/schemas/chat.py`:
    - Add `dweller_message_id: UUID4` (or `UUID`) to `DwellerChatResponse` and `DwellerVoiceChatResponse`.
  - Update `backend/app/api/v1/endpoints/chat.py`:
    - Capture return value of `chat_message_crud.create_message()` for the **dweller response** message.
    - Include `dweller_message_id` in the HTTP response.
    - Include `message_id` in the WS `action_suggestion` payload.
  - Voice chat path:
    - Ensure the dweller response message id is available where the WS message is sent (may require returning it from `conversation_service.process_audio_message()` or otherwise capturing it).

  **Must NOT do**:
  - Do not change DB schema; do not persist action suggestions.
  - Do not rename existing response fields; additive only.

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
    - Reason: Cross-cutting backend contract + tests, but not algorithmically complex.
  - Skills: (none required)

  **Acceptance Criteria**:
  - `cd backend && uv run pytest app/tests/test_api/test_chat.py -v` → PASS
  - Verified: WS payload for action suggestions contains `message_id` and matches HTTP `dweller_message_id` in test assertions.

  **Agent-Executed QA Scenario**:
  - Tool: Bash
  - Steps:
    1. Run: `cd backend && uv run pytest app/tests/test_api/test_chat.py -v`
    2. Confirm tests covering the new fields pass.
  - Evidence: Pytest output captured in terminal logs.

### 2) Frontend (TDD): Correlate suggestions by message id + show latest-only

- [x] 3. Regenerate frontend API types after backend change

  **What to do**:
  - Run backend (so OpenAPI is available) and regenerate types:
    - `cd frontend && pnpm run types:generate`

  **References**:
  - Repo guardrail: after backend API changes, regenerate frontend API types.

  **Acceptance Criteria**:
  - `cd frontend && pnpm run types:generate` → completes successfully
  - Generated types include `dweller_message_id` for chat responses (verify in `frontend/src/core/types/api.generated.ts`).

  **Agent-Executed QA Scenario**:
  - Tool: Bash
  - Steps:
    1. Ensure backend dev server is running on `http://localhost:8000`.
    2. Run: `cd frontend && pnpm run types:generate`
  - Expected: command exits 0.

- [ ] 4. Add failing frontend tests for latest-only + ID-based WS stickiness

  **What to do (RED)**:
  - In `frontend/tests/unit/components/chat/DwellerChat.test.ts`, add tests to assert:
    1) **Latest-only rendering**: only ONE `.action-suggestion-card` exists even if multiple messages have suggestions.
    2) **Keep previous actionable**: if a new dweller message arrives with `actionSuggestion: null` (or `no_action`), the last actionable suggestion remains visible.
    3) **WS correlation by id**: when WS emits `{ type: 'action_suggestion', message_id: <id>, action_suggestion: {...} }`, only the message with that id receives the suggestion.
    4) **Out-of-order WS event**: emit suggestion for message A after message B exists; ensure only message A updates.

  **References**:
  - `frontend/src/modules/chat/components/DwellerChat.vue` — current behavior + selectors
  - `frontend/tests/unit/components/chat/DwellerChat.test.ts` — existing mocks for axios + WS handlers
  - `.action-suggestion-card`, `.message-wrapper` selectors used in existing tests

  **Acceptance Criteria (tests)**:
  - `cd frontend && pnpm run test -- tests/unit/components/chat/DwellerChat.test.ts` → FAIL before implementation (new assertions fail)

  **Agent-Executed QA Scenario**:
  - Tool: Bash
  - Steps:
    1. Run: `cd frontend && pnpm run test -- tests/unit/components/chat/DwellerChat.test.ts`
  - Expected: new tests fail, confirming bug reproduction.

- [ ] 5. Implement frontend fixes (GREEN): ID-based attach + latest-only display

  **What to do**:
  - Update `frontend/src/modules/chat/models/chat.ts`:
    - Add `id?: string` (or `id?: UUID string`) to `ChatMessageDisplay`.
  - Update `frontend/src/modules/chat/components/DwellerChat.vue`:
    1) When pushing a new dweller message from HTTP response, set `id = response.data.dweller_message_id`.
    2) Update WS handler for `action_suggestion`:
       - Require `message_id` in payload.
       - Find message by `id === message_id` and update only that message's `actionSuggestion`.
       - If message not found yet, store in a `pendingSuggestionsById` map and apply when the message arrives.
    3) Implement **latest-only rendering**:
       - Compute `latestActionableSuggestionMessageId` = last message in timeline where:
         - `actionSuggestion` exists AND `action_type !== 'no_action'`.
       - Only render suggestion card when `message.id === latestActionableSuggestionMessageId`.
       - Keep previous actionable visible when newer message has null/no_action (the computed value naturally remains the previous id).
       - Dismiss per message: set that message's `actionSuggestion = null`; recompute latest actionable; older actionable may become visible.
    4) Fix potential Vue keying issues:
       - Change `:key="index"` to `:key="message.id ?? index"` (additive, safe).

  **Must NOT do**:
  - Don't move suggestions to composer.
  - Don't add Pinia refactor.

  **Recommended Agent Profile**:
  - Category: `unspecified-high`
    - Reason: Cross-cutting UI state + WS correlation + tests.
  - Skills:
    - `playwright` (for E2E QA scenarios)
    - (Skills evaluated but omitted: `frontend-ui-ux` — not a redesign task)

  **Acceptance Criteria**:
  - Unit tests:
    - `cd frontend && pnpm run test -- tests/unit/components/chat/DwellerChat.test.ts` → PASS
    - `cd frontend && pnpm run typecheck` → PASS
  - UI logic:
    - In DOM, at most one `.action-suggestion-card` is visible at any time.
    - WS `action_suggestion` updates only the message matching `message_id`.

  **Agent-Executed QA Scenarios (Playwright)**:

  Scenario: Only latest actionable suggestion is visible
    Tool: Playwright (playwright skill)
    Preconditions:
      - Infra running (Postgres/Redis)
      - Backend running: `uv run fastapi dev main.py` on `http://localhost:8000`
      - Frontend running: `pnpm run dev` on `http://localhost:5173`
      - Dweller chat route is: `/dweller/:id/chat` (from `frontend/src/modules/chat/routes/index.ts`)
      - You have a valid `dwellerId` UUID (from seed/test data)
    Steps:
      1. Navigate to: `http://localhost:5173/dweller/{dwellerId}/chat`
      2. Wait for: `.chat-container` visible
      3. Fill: `.chat-input-field` → "Message 1"
      4. Click: `.chat-send-btn`
      5. Wait for: `.message-wrapper.dweller` count >= 1
      6. Assert: `.action-suggestion-card` count == 1
      7. Fill: `.chat-input-field` → "Message 2"
      8. Click: `.chat-send-btn`
      9. Wait for: `.message-wrapper.dweller` count >= 2
      10. Assert: `.action-suggestion-card` count == 1
      11. Screenshot: `.sisyphus/evidence/task-5-latest-only.png`
    Expected Result: Only one suggestion card visible; corresponds to latest actionable suggestion.

  Scenario: New message with no suggestion keeps previous visible
    Tool: Playwright (playwright skill)
    Preconditions: same as above
    Steps:
      1. Precondition check: `.action-suggestion-card` count == 1
      2. Fill: `.chat-input-field` → "Message with no action"
      3. Click: `.chat-send-btn`
      4. Wait for: `.message-wrapper.dweller` count increases by 1
      5. Assert: `.action-suggestion-card` count == 1
      6. Screenshot: `.sisyphus/evidence/task-5-keep-previous.png`
    Expected Result: previous actionable suggestion remains visible.

  Scenario: WS suggestion updates correct message (out-of-order)
    Tool: Playwright (playwright skill)
    Preconditions: same as above
    Steps:
      1. Send two messages quickly to create two dweller replies.
      2. Wait for WS suggestion for the first reply to arrive after the second reply exists.
      3. Assert: suggestion appears only on the correct (first) message *or* if latest-only policy hides it, ensure it does not incorrectly attach to the wrong message and the computed latest still behaves.
      4. Screenshot: `.sisyphus/evidence/task-5-ws-correlation.png`
    Expected Result: No mis-association; suggestion correlates by `message_id`.

---

## Commit Strategy (Optional)
- No git actions unless explicitly requested.
- If committing, prefer 2 commits:
  1) `fix(chat): add message_id to chat responses/ws` (backend + tests)
  2) `fix(chat): correlate suggestions by id; show latest only` (frontend + tests)

---

## Success Criteria

### Verification Commands
```bash
cd backend && uv run pytest app/tests/test_api/test_chat.py -v
cd frontend && pnpm run test -- tests/unit/components/chat/DwellerChat.test.ts
cd frontend && pnpm run typecheck
```

### Final Checklist
- [x] Backend returns `dweller_message_id` on chat + voice chat endpoints
- [x] WebSocket `action_suggestion` includes `message_id`
- [ ] Frontend stores message id and updates suggestions by id
- [ ] Only the latest actionable suggestion is visible
- [ ] All tests pass
