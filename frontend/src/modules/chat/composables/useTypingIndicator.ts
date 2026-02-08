import { onUnmounted } from 'vue'
import type { useChatWebSocket } from '@/core/composables/useWebSocket'

type ChatWebSocket = ReturnType<typeof useChatWebSocket>

export function useTypingIndicator(chatWs: ChatWebSocket | null) {
  let typingTimeout: number | null = null

  const handleTyping = () => {
    if (chatWs) {
      try {
        chatWs.sendTypingIndicator(true)
      } catch (error) {
        console.error('Error sending typing indicator:', error)
      }

      if (typingTimeout) clearTimeout(typingTimeout)

      typingTimeout = window.setTimeout(() => {
        try {
          chatWs.sendTypingIndicator(false)
        } catch (error) {
          console.error('Error clearing typing indicator:', error)
        }
      }, 2000)
    }
  }

  const cleanup = () => {
    if (typingTimeout) {
      try {
        chatWs?.sendTypingIndicator(false)
      } catch (error) {
        console.error('Error clearing typing indicator:', error)
      }
      clearTimeout(typingTimeout)
      typingTimeout = null
    }
  }

  onUnmounted(cleanup)

  return {
    handleTyping,
    cleanupTyping: cleanup,
  }
}
