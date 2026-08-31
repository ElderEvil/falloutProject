import { ref, computed, watch, nextTick, toValue, type MaybeRefOrGetter, type Ref } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import apiClient from '@/core/plugins/axios'
import type { useChatWebSocket } from '@/core/composables/useWebSocket'
import { handleStoreError } from '@/core/utils/errorHandler'
import { normalizeImageUrl } from '@/core/utils/image'
import { useSound } from '@/core/composables/useSound'
import type { ChatMessageDisplay, MapDiscovery } from '@/modules/chat/models/chat'

export interface UseChatMessagesOptions {
  dwellerId: string
  dwellerAvatar?: string
  token: Ref<string | null> | string | null
  userImageUrl?: MaybeRefOrGetter<string | undefined>
  chatWs?: ReturnType<typeof useChatWebSocket>
}

export const normalizeUnlockedPlaces = (places: unknown): MapDiscovery[] =>
  Array.isArray(places)
    ? places
        .filter(
          (place): place is { location_id: string; name: string } =>
            typeof place === 'object' &&
            place !== null &&
            typeof place.location_id === 'string' &&
            typeof place.name === 'string'
        )
        .map((place) => ({ locationId: place.location_id, name: place.name }))
    : []

export function useChatMessages(options: UseChatMessagesOptions) {
  const messages = ref<ChatMessageDisplay[]>([])
  const userMessage = ref('')
  const chatMessages = ref<HTMLElement | null>(null)
  const isTyping = ref(false)

  // Streaming state: the dweller message being built from token events, and
  // the resolver that settles sendMessage once the stream completes.
  let streamingIndex: number | null = null
  let sendResolver: (() => void) | null = null

  // Chat feedback sounds: a single-message append is a live receive (sends are
  // covered by the per-keystroke typewriter); bulk appends are history loads
  // and stay silent. The sync flush lets loadChatHistory suppress the watcher
  // while it replaces the whole list.
  const { playSound } = useSound()
  let suppressMessageSound = false
  watch(
    () => messages.value.length,
    (newLen, oldLen) => {
      if (suppressMessageSound || newLen - oldLen !== 1) return
      const last = messages.value[newLen - 1]
      if (last?.type === 'dweller') playSound('messageReceive')
    },
    { flush: 'sync' }
  )

  const getToken = () =>
    typeof options.token === 'string' || options.token === null
      ? options.token
      : options.token?.value

  const userAvatar = computed(() => toValue(options.userImageUrl) ?? null)
  const dwellerAvatarUrl = computed(() => normalizeImageUrl(options.dwellerAvatar))

  const canSend = computed(() => userMessage.value.trim().length > 0)

  const markUserMessageFailed = (error?: string) => {
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg && lastMsg.type === 'user') {
      lastMsg.error = error
    }
  }

  if (options.chatWs) {
    options.chatWs.on('token', (msg: any) => {
      if (streamingIndex === null) {
        messages.value.push({
          type: 'dweller',
          content: '',
          timestamp: new Date(),
        })
        streamingIndex = messages.value.length - 1
      }
      const streamingMsg = messages.value[streamingIndex]
      if (streamingMsg) {
        streamingMsg.content = msg.replace ? (msg.text ?? '') : streamingMsg.content + (msg.text ?? '')
      }
    })

    options.chatWs.on('done', (msg: any) => {
      if (streamingIndex !== null) {
        const streamingMsg = messages.value[streamingIndex]
        if (streamingMsg) {
          streamingMsg.content = msg.response_text || streamingMsg.content
          streamingMsg.messageId = msg.dweller_message_id
          streamingMsg.happinessImpact = msg.happiness_impact || null
          streamingMsg.actionSuggestion = msg.action_suggestion || null
          streamingMsg.unlockedPlaces = normalizeUnlockedPlaces(msg.unlocked_places)
        }
        streamingIndex = null
      }
      isTyping.value = false
      sendResolver?.()
      sendResolver = null
    })

    options.chatWs.on('error', (msg: any) => {
      const detail = (typeof msg?.detail === 'string' ? msg.detail : undefined) ?? 'Failed to send'
      if (streamingIndex !== null) {
        const streamingMsg = messages.value[streamingIndex]
        if (streamingMsg && streamingMsg.type === 'dweller') {
          streamingMsg.error = detail
        }
        streamingIndex = null
      } else {
        markUserMessageFailed(detail)
      }
      isTyping.value = false
      sendResolver?.()
      sendResolver = null
    })
  }

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

      suppressMessageSound = true
      messages.value = history
      // History replaced the list; re-arm the sound watcher afterwards.
      suppressMessageSound = false
    } catch (error) {
      handleStoreError(error, 'Error loading chat history')
    }
  }

  const sendMessage = async () => {
    if (userMessage.value.trim()) {
      const isWsConnected = options.chatWs?.state.value === 'connected'
      const messageToSend = userMessage.value
      userMessage.value = ''

      messages.value.push({
        type: 'user',
        content: messageToSend,
        timestamp: new Date(),
      })
      isTyping.value = true

      if (isWsConnected && options.chatWs) {
        options.chatWs.sendMessage(messageToSend)
        await new Promise<void>((resolve) => {
          sendResolver = resolve
        })
        return
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
          happinessImpact: response.data.happiness_impact || null,
          unlockedPlaces: normalizeUnlockedPlaces(response.data.unlocked_places),
          actionSuggestion: response.data.action_suggestion || null,
        })
      } catch (error) {
        const reason = handleStoreError(error, 'Error sending message')
        markUserMessageFailed(reason)
      } finally {
        isTyping.value = false
      }
    }
  }

  const chatInputRef = ref<HTMLInputElement | null>(null)

  onKeyStroke(
    'Enter',
    (e) => {
      if (!e.shiftKey) {
        e.preventDefault()
        void sendMessage()
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
    dismissAction,
    getHappinessColor,
    getHappinessIcon,
  }
}
