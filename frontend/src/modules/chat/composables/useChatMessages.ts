import { ref, computed, nextTick, readonly, type Ref } from 'vue'
import { watchDebounced, onKeyStroke } from '@vueuse/core'
import * as http from '@/core/plugins/httpClient'
import { normalizeImageUrl } from '@/utils/image'
import type { ChatMessageDisplay } from '@/modules/chat/models/chat'
import type { ChatMessageRead } from '@/core/types/api.generated'
import type { useChatWebSocket } from '@/core/composables/useWebSocket'

export interface UseChatMessagesOptions {
  dwellerId: string
  dwellerAvatar?: string
  token: Ref<string | null> | string | null
  userImageUrl?: string
  chatWs: ReturnType<typeof useChatWebSocket> | null
}

export function useChatMessages(options: UseChatMessagesOptions) {
  const messages = ref<ChatMessageDisplay[]>([])
  const userMessage = ref('')
  const chatMessages = ref<HTMLElement | null>(null)
  const isTyping = ref(false)

  const getToken = () =>
    typeof options.token === 'string' || options.token === null
      ? options.token
      : options.token?.value

  const userAvatar = computed(() => options.userImageUrl || undefined)
  const dwellerAvatarUrl = computed(() => normalizeImageUrl(options.dwellerAvatar))

  const canSend = computed(() => userMessage.value.trim().length > 0)

  const addMessage = (msg: ChatMessageDisplay) => {
    messages.value.push(msg)
  }

  const updateMessage = (index: number, partial: Partial<ChatMessageDisplay>) => {
    if (messages.value[index]) {
      messages.value[index] = { ...messages.value[index], ...partial }
    }
  }

  const clearMessages = () => {
    messages.value = []
  }

  const loadChatHistory = async () => {
    try {
      const history = await http.apiGet<ChatMessageRead[]>(
        `/api/v1/chat/history/${options.dwellerId}`,
        {
          headers: {
            Authorization: `Bearer ${getToken()}`,
          },
        }
      )

      const mapped = history.map((msg) => ({
        type: msg.from_user_id ? 'user' : 'dweller',
        content: msg.message_text,
        messageId: msg.id || undefined,
        timestamp: new Date(msg.created_at),
        avatar: msg.from_user_id ? userAvatar.value : options.dwellerAvatar,
        audioUrl: msg.audio_url || undefined,
        transcription: msg.transcription || undefined,
        happinessImpact:
          msg.happiness_delta !== null && msg.happiness_delta !== undefined
            ? {
                delta: msg.happiness_delta,
                reason_text: msg.happiness_reason || '',
              }
            : undefined,
      }))

      messages.value = mapped
    } catch (error) {
      console.error('Error loading chat history:', error)
    }
  }

  const sendMessage = async () => {
    const content = userMessage.value.trim()
    if (!content) return

    const tempId = `temp-${Date.now()}`
    addMessage({
      type: 'user',
      content,
      messageId: tempId,
      timestamp: new Date(),
      avatar: userAvatar.value,
    })

    userMessage.value = ''
    isTyping.value = true

    try {
      if (options.chatWs) {
        options.chatWs.sendMessage(content)
      } else {
        console.error('WebSocket not available for sending message')
      }
    } catch (error) {
      console.error('Error sending message:', error)
    }
  }

  // Find the latest actionable suggestion (most recent dweller message with a valid action)
  const latestActionSuggestionIndex = computed(() => {
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (
        msg.type === 'dweller' &&
        msg.actionSuggestion &&
        msg.actionSuggestion.action_type !== 'no_action'
      ) {
        return i
      }
    }
    return -1
  })

  const dismissAction = (messageIndex: number) => {
    updateMessage(messageIndex, { actionSuggestion: null })
  }

  // Get happiness impact color based on delta
  const getHappinessColor = (delta: number): string => {
    if (delta > 0) return 'text-green-400'
    if (delta < 0) return 'text-red-400'
    return 'text-gray-400'
  }

  // Get happiness icon based on delta
  const getHappinessIcon = (delta: number): string => {
    if (delta > 0) return 'mdi:emoticon-happy'
    if (delta < 0) return 'mdi:emoticon-sad'
    return 'mdi:emoticon-neutral'
  }

  // Auto-scroll to bottom
  watchDebounced(
    messages,
    () => {
      nextTick(() => {
        if (chatMessages.value) {
          if (typeof chatMessages.value.scrollTo === 'function') {
            chatMessages.value.scrollTo({
              top: chatMessages.value.scrollHeight,
              behavior: 'smooth',
            })
          } else {
            chatMessages.value.scrollTop = chatMessages.value.scrollHeight
          }
        }
      })
    },
    { debounce: 50, deep: true }
  )

  // Enter key sends message (Shift+Enter allows newline)
  onKeyStroke('Enter', (e) => {
    if (!e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  })

  return {
    // State
    messages: readonly(messages),
    userMessage,
    chatMessages,
    isTyping,
    userAvatar,
    dwellerAvatarUrl,
    canSend,
    latestActionSuggestionIndex,

    // Methods
    loadChatHistory,
    sendMessage,
    addMessage,
    updateMessage,
    clearMessages,
    dismissAction,
    getHappinessColor,
    getHappinessIcon,
  }
}
