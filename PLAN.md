# Development Plans

## Current Branch: feat/2.9.0

This document contains the active development plans for the current branch.

---

# Plan: Fix Chat Action Suggestions — Frontend Latest-only + ID-based WS Stickiness

## Status: In Progress (Backend done ✅, Frontend remaining)

Backend contract is complete (`dweller_message_id` in HTTP responses, `message_id` in WS payloads). Frontend work remains.

---

## Remaining TODOs

### 1) Add failing frontend tests for latest-only + ID-based WS stickiness

- In `frontend/tests/unit/components/chat/DwellerChat.test.ts`, add tests to assert:
  1) **Latest-only rendering**: only ONE `.action-suggestion-card` exists even if multiple messages have suggestions.
  2) **Keep previous actionable**: if a new dweller message arrives with `actionSuggestion: null` (or `no_action`), the last actionable suggestion remains visible.
  3) **WS correlation by id**: when WS emits `{ type: 'action_suggestion', message_id: <id>, action_suggestion: {...} }`, only the message with that id receives the suggestion.
  4) **Out-of-order WS event**: emit suggestion for message A after message B exists; ensure only message A updates.

### 2) Implement frontend fixes: ID-based attach + latest-only display

- Update `frontend/src/modules/chat/models/chat.ts`:
  - Add `id?: string` to `ChatMessageDisplay`.
- Update `frontend/src/modules/chat/components/DwellerChat.vue`:
  1) Set `id = response.data.dweller_message_id` on new dweller messages.
  2) WS `action_suggestion` handler: require `message_id`, find message by id, update only that message.
  3) Compute `latestActionableSuggestionMessageId` — only render suggestion card for that message.
  4) Change `:key="index"` to `:key="message.id ?? index"`.

### Guardrails
- Don't move suggestions to composer.
- Don't add Pinia refactor.
- No DB migration for suggestion persistence.

---

## Verification Commands

```bash
cd frontend && pnpm run test -- tests/unit/components/chat/DwellerChat.test.ts
cd frontend && pnpm run typecheck
```

## Checklist

- [x] Backend returns `dweller_message_id` on chat + voice chat endpoints
- [x] WebSocket `action_suggestion` includes `message_id`
- [ ] Frontend stores message id and updates suggestions by id
- [ ] Only the latest actionable suggestion is visible
- [ ] All tests pass
