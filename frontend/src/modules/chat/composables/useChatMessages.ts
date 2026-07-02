import { ref, computed, watch, nextTick, type Ref } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import apiClient from '@/core/plugins/axios'
import type { useChatWebSocket } from '@/core/composables/useWebSocket'
import { handleStoreError } from '@/core/utils/errorHandler'
import { normalizeImageUrl } from '@/utils/image'
import type { ChatMessageDisplay } from '@/modules/chat/models/chat'

export interface UseChatMessagesOptions {
  dwellerId: string
  dwellerAvatar?: string
  token: Ref<string | null> | string | null
  userImageUrl?: string
  chatWs?: ReturnType<typeof useChatWebSocket>
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

  const loadChatHistory = async () => {
    try {
      const response = await apiClient.get(`/api/v1/chat/history/${options.dwellerId}`, {
        headers: {
          Authorization: `Bearer ${getToken()}`,
        },
      })

      const history = response.data.map((msg: any) => ({
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

      messages.value = history
    } catch (error) {
      handleStoreError(error, 'Error loading chat history')
    }
  }

  const sendMessage = async () => {
    if (userMessage.value.trim()) {
      const isWsConnected = options.chatWs?.state.value === 'connected'
      const messageToSend = userMessage.value

      if (isWsConnected) {
        messages.value.push({
          type: 'user',
          content: messageToSend,
          timestamp: new Date(),
          avatar: userAvatar.value,
        })
        userMessage.value = ''
        isTyping.value = true
      } else {
        console.warn('WebSocket not connected, skipping optimistic update')
      }

      try {
        const response = await apiClient.post(
          `/api/v1/chat/${options.dwellerId}`,
          {
            message: messageToSend,
          },
          {
            headers: {
              Authorization: `Bearer ${getToken()}`,
            },
          }
        )
        messages.value.push({
          type: 'dweller',
          content: response.data.response,
          messageId: response.data.dweller_message_id,
          timestamp: new Date(),
          avatar: options.dwellerAvatar,
          happinessImpact: response.data.happiness_impact || null,
          actionSuggestion: response.data.action_suggestion || null,
        })
      } catch (error) {
        handleStoreError(error, 'Error sending message')
        // Mark the optimistic user message as failed
        if (messages.value.length > 0) {
          const lastMsg = messages.value[messages.value.length - 1]
          if (lastMsg.type === 'user') {
            lastMsg.content = '[Failed to send] ' + lastMsg.content
          }
        }
      } finally {
        if (isWsConnected) {
          isTyping.value = false
        }
      }
    }
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
    // Shift+Enter allows newline (default behavior)
  }

  const chatInputRef = ref<HTMLInputElement | null>(null)

  onKeyStroke(
    'Enter',
    (e) => {
      if (!e.shiftKey) {
        e.preventDefault()
        sendMessage()
      }
      // Shift+Enter allows newline (default behavior)
    },
    { target: chatInputRef }
  )

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
    const msg = messages.value[messageIndex]
    if (msg) {
      msg.actionSuggestion = null
    }
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
  watch(messages, async () => {
    await nextTick()
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })

  return {
    // State
    messages,
    userMessage,
    chatMessages,
    chatInputRef,
    isTyping,
    userAvatar,
    dwellerAvatarUrl,
    canSend,
    latestActionSuggestionIndex,

    // Methods
    loadChatHistory,
    sendMessage,
    handleKeyDown,
    dismissAction,
    getHappinessColor,
    getHappinessIcon,
  }
}
