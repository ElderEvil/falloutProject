import { onUnmounted, getCurrentInstance } from 'vue'
import type { useChatWebSocket } from '@/core/composables/useWebSocket'
import { useToast } from '@/core/composables/useToast'

type ChatWebSocket = ReturnType<typeof useChatWebSocket>

export function useTypingIndicator(chatWs: ChatWebSocket | null) {
  const toast = useToast()
  let typingTimeout: number | null = null

  const handleTyping = () => {
    if (chatWs) {
      try {
        chatWs.sendTypingIndicator(true)
      } catch {
        toast.warning('Typing status could not be sent')
      }

      if (typingTimeout) clearTimeout(typingTimeout)

      typingTimeout = window.setTimeout(() => {
        try {
          chatWs.sendTypingIndicator(false)
        } catch {
          toast.warning('Typing status could not be updated')
        }
      }, 2000)
    }
  }

  const cleanup = () => {
    if (typingTimeout) {
      try {
        chatWs?.sendTypingIndicator(false)
      } catch {
        toast.warning('Typing status could not be updated')
      }
      clearTimeout(typingTimeout)
      typingTimeout = null
    }
  }

  // Only register onUnmounted if inside a Vue component
  if (getCurrentInstance()) {
    onUnmounted(cleanup)
  }

  return {
    handleTyping,
    cleanupTyping: cleanup,
  }
}
