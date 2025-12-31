import { defineStore } from 'pinia'

/**
 * Chat Store
 *
 * NOTE: Chat functionality currently uses direct API calls from components
 * (see DwellerChat.vue and DwellerChatPage.vue in Phase 5A).
 *
 * This store is currently unused but kept for potential future enhancements:
 * - Message caching
 * - Chat history persistence
 * - Unread message tracking
 * - Multi-chat session management
 *
 * For now, chat components manage their own state locally.
 */
export const useChatStore = defineStore('chat', () => {
  // Placeholder for future chat state management
  return {}
})
