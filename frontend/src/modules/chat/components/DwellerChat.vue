<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import apiClient from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useChatWebSocket } from '@/core/composables/useWebSocket'
import { normalizeImageUrl } from '@/core/utils/image'
import type { ActionSuggestion } from '../models/chat'
import { useAudioRecorder } from '../composables/useAudioRecorder'
import { useChatMessages } from '../composables/useChatMessages'
import { useChatAudio } from '../composables/useChatAudio'
import { useTypingIndicator } from '../composables/useTypingIndicator'
import { useChatActions } from '../composables/useChatActions'
import { useMapStore } from '@/modules/map/stores/map'
import { useToast } from '@/core/composables/useToast'

const router = useRouter()

const props = defineProps<{
  dwellerId: string
  dwellerName: string
  username: string
  dwellerAvatar?: string
  vaultId?: string | null
}>()

const authStore = useAuthStore()
const profileStore = useProfileStore()

const isSendingAudio = ref(false)
const audioMode = ref(false)

// Quota exceeded state
const isQuotaExceeded = computed(() => profileStore.quotaExceeded)
const resetDate = computed(() => {
  const resetDateStr = profileStore.aiUsageStats?.reset_date || ''
  if (!resetDateStr) return 'soon'
  const [year, month, day] = resetDateStr.split('-')
  const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day))
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
})

const goToProfile = () => {
  router.push('/profile')
}

const {
  recordingState,
  recordingDuration,
  isRecording,
  startRecording,
  stopRecording,
  cancelRecording,
  formatDuration,
} = useAudioRecorder()

const userId = computed(() => authStore.user?.id || '')
const chatWs = useChatWebSocket(userId.value, props.dwellerId, authStore.token)

const {
  messages,
  userMessage,
  chatMessages,
  chatInputRef,
  isTyping,
  userAvatar,
  dwellerAvatarUrl,
  canSend,
  latestActionSuggestionIndex,
  loadChatHistory,
  sendMessage,
  dismissAction,
  getHappinessColor,
  getHappinessIcon,
} = useChatMessages({
  dwellerId: props.dwellerId,
  dwellerAvatar: props.dwellerAvatar,
  token: authStore.token,
  userImageUrl: (authStore.user as any)?.image_url,
  chatWs,
})

const { currentlyPlayingUrl, stopAudio, playAudio } = useChatAudio()

const { handleTyping } = useTypingIndicator(chatWs)

const { isPerformingAction, handleActionConfirm, refreshAfterChat } = useChatActions({
  dwellerId: props.dwellerId,
  dwellerName: props.dwellerName,
  messages,
  vaultId: props.vaultId,
})

const mapStore = useMapStore()
const toast = useToast()
const initialUnlockedCount = ref<number | null>(null)

watch(
  () => mapStore.unlockedPlacesCount,
  (newCount) => {
    if (initialUnlockedCount.value === null) {
      initialUnlockedCount.value = newCount
      return
    }
    const previousCount = initialUnlockedCount.value
    if (newCount > previousCount) {
      const unlockedDelta = newCount - previousCount
      const pluralSuffix = unlockedDelta > 1 ? 's' : ''
      toast.success(`New location uncovered! (${unlockedDelta} place${pluralSuffix})`)
    }
    initialUnlockedCount.value = newCount
  }
)

const handleSendMessage = async () => {
  await sendMessage()
  refreshAfterChat()
}

// Register WebSocket event handlers during setup
chatWs.on('typing', (msg: any) => {
  if (msg.sender === 'dweller') {
    isTyping.value = msg.is_typing
  }
})

chatWs.on('happiness_update', (msg: any) => {
  if (msg.happiness_impact && msg.message_id) {
    const messageIndex = messages.value.findIndex((m) => m.messageId === msg.message_id)
    if (messageIndex !== -1) {
      messages.value[messageIndex] = {
        ...messages.value[messageIndex],
        happinessImpact: msg.happiness_impact,
      }
    }
  }
})

chatWs.on('action_suggestion', (msg: any) => {
  if (msg.message_id && msg.action_suggestion) {
    const messageIndex = messages.value.findIndex((m) => m.messageId === msg.message_id)
    if (messageIndex !== -1) {
      messages.value[messageIndex] = {
        ...messages.value[messageIndex],
        actionSuggestion: msg.action_suggestion,
      }
    }
  }
})

// Reactively connect/disconnect WebSocket when userId changes
watch(
  userId,
  (id) => {
    if (id) {
      chatWs.connect()
    } else {
      chatWs.disconnect()
    }
  },
  { immediate: true }
)

const sendAudioMessage = async () => {
  try {
    isSendingAudio.value = true
    const audioBlob = await stopRecording()

    const formData = new FormData()
    formData.append('audio_file', audioBlob, 'recording.webm')

    const placeholderIndex = messages.value.length
    messages.value.push({
      type: 'user',
      content: '[Transcribing audio...]',
      timestamp: new Date(),
      avatar: userAvatar.value,
    })

    const response = await apiClient.post(
      `/api/v1/chat/${props.dwellerId}/voice?return_audio=false`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'multipart/form-data',
        },
      }
    )

    const placeholderMessage = messages.value[placeholderIndex]
    if (placeholderMessage) {
      placeholderMessage.content = response.data.transcription
    }

    messages.value.push({
      type: 'dweller',
      content: response.data.dweller_response,
      messageId: response.data.dweller_message_id,
      timestamp: new Date(),
      avatar: props.dwellerAvatar,
      audioUrl: response.data.dweller_audio_url,
      happinessImpact: response.data.happiness_impact || null,
      actionSuggestion: response.data.action_suggestion || null,
    })

    if (response.data.dweller_audio_url) {
      playAudio(response.data.dweller_audio_url)
    }

    refreshAfterChat()
  } catch (error: unknown) {
    const message =
      (error as { response?: { data?: { detail?: string } }; message?: string }).response?.data
        ?.detail ??
      (error as { message?: string }).message ??
      'Unable to send audio message'
    toast.error(`Failed to send audio: ${message}`)
  } finally {
    isSendingAudio.value = false
  }
}

onMounted(() => {
  loadChatHistory()
})

onUnmounted(() => {
  if (chatWs) {
    chatWs.disconnect()
  }
  stopAudio()
})
</script>

<template src="./DwellerChat.template.html"></template>

<style src="./DwellerChat.css" scoped></style>
