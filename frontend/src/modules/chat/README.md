# Chat

AI dweller conversations module. Provides real-time chat with dwellers including audio recording, typing indicators, and message history through composable-driven architecture.

## Routes

- `/dweller/:id/chat` — DwellerChatPage

## Key Files

- `components/DwellerChatPage.vue` — full-page chat view for a specific dweller
- `components/DwellerChat.vue` — reusable chat component
- `stores/chat.ts` — chat state and message management
- `composables/useAudioRecorder.ts` — audio recording composable
- `composables/useTypingIndicator.ts` — typing indicator composable
- `composables/useChatMessages.ts` — message fetching and pagination
- `models/` — chat message and conversation type definitions
