<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import apiClient from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useChatWebSocket } from '@/core/composables/useWebSocket'
import { getErrorMessage } from '@/core/types/utils'
import { normalizeImageUrl } from '@/core/utils/image'
import type { ActionSuggestion } from '../models/chat'
import { useAudioRecorder } from '../composables/useAudioRecorder'
import { useChatMessages } from '../composables/useChatMessages'
import { useChatAudio } from '../composables/useChatAudio'
import { useTypingIndicator } from '../composables/useTypingIndicator'
import { useChatActions } from '../composables/useChatActions'
import { useSound } from '@/core/composables/useSound'
import { useMapStore } from '@/modules/map/stores/map'
import { useToast } from '@/core/composables/useToast'
import ChatMessageList from './ChatMessageList.vue'

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
const { playSound } = useSound()

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
    const message = getErrorMessage(error, 'Unable to send audio message')
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

<template>
  <div class="chat-container">
    <div class="scanlines"></div>
    <div class="chat-identity-header">
      <div class="identity-avatar">
        <img
          v-if="dwellerAvatarUrl"
          :src="dwellerAvatarUrl"
          alt="Dweller"
          class="header-avatar-image"
        />
        <Icon v-else icon="mdi:robot" class="header-avatar-icon" />
      </div>
      <div class="identity-info">
        <span class="identity-name">{{ dwellerName }}</span>
        <span class="identity-status">Online</span>
      </div>
    </div>

    <div ref="chatMessages" class="chat-messages">
      <ChatMessageList
        :messages="messages"
        :dweller-name="dwellerName"
        :username="username"
        :dweller-avatar-url="dwellerAvatarUrl"
        :is-typing="isTyping"
        :currently-playing-url="currentlyPlayingUrl"
        :latest-action-suggestion-index="latestActionSuggestionIndex"
        :is-performing-action="isPerformingAction"
        :get-happiness-color="getHappinessColor"
        :get-happiness-icon="getHappinessIcon"
        @play-audio="playAudio"
        @stop-audio="stopAudio"
        @confirm-action="handleActionConfirm"
        @dismiss-action="dismissAction"
      />
    </div>

    <div v-if="isQuotaExceeded" class="chat-input quota-exceeded">
      <div class="quota-blocked-message">
        <Icon icon="mdi:alert-circle" class="quota-icon" />
        <div class="quota-text">
          <span class="quota-title">Monthly quota exceeded</span>
          <span class="quota-reset">Resets on {{ resetDate }}</span>
        </div>
        <button class="quota-profile-btn" @click="goToProfile">View Profile</button>
      </div>
    </div>

    <div v-else class="chat-input">
      <button
        class="mode-toggle-btn"
        :title="audioMode ? 'Switch to text' : 'Switch to voice'"
        @click="audioMode = !audioMode"
      >
        <Icon :icon="audioMode ? 'mdi:keyboard' : 'mdi:microphone'" class="h-5 w-5" />
      </button>
      <template v-if="!audioMode">
        <span class="terminal-prompt">&gt;</span>
        <input
          ref="chatInputRef"
          v-model="userMessage"
          class="chat-input-field"
          placeholder="Type your message..."
          @input="handleTyping"
          @beforeinput="playSound('typeKey')"
        />
        <button
          class="chat-send-btn"
          :class="{ disabled: !canSend }"
          :disabled="!canSend"
          @click="handleSendMessage"
        >
          <Icon icon="mdi:send" class="h-5 w-5" />
        </button>
      </template>
      <template v-else>
        <div v-if="isRecording" class="recording-indicator">
          <span class="recording-dot"></span>
          Recording: {{ formatDuration(recordingDuration) }}
        </div>
        <div v-else-if="isSendingAudio" class="processing-indicator">
          <Icon icon="mdi:loading" class="spinning h-5 w-5" />
          Processing audio...
        </div>
        <div v-else class="ready-indicator">
          <Icon icon="mdi:microphone" class="h-5 w-5" />
          Ready to record
        </div>
        <button
          v-if="!isRecording"
          class="record-btn"
          title="Start recording"
          :disabled="isSendingAudio"
          @click="startRecording"
        >
          <Icon icon="mdi:microphone" class="h-6 w-6" />
        </button>
        <template v-else>
          <button class="cancel-btn" title="Cancel" @click="cancelRecording">
            <Icon icon="mdi:close" class="h-5 w-5" />
          </button>
          <button class="send-audio-btn" title="Send" @click="sendAudioMessage">
            <Icon icon="mdi:send" class="h-5 w-5" />
          </button>
        </template>
      </template>
    </div>
  </div>
</template>

<style src="./DwellerChat.css"></style>
