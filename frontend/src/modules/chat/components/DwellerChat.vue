<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import apiClient from '@/core/plugins/axios'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useProfileStore } from '@/modules/profile/stores/profile'
import { useChatWebSocket } from '@/core/composables/useWebSocket'
import { getErrorMessage } from '@/core/types/utils'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import type { ActionSuggestion } from '../models/chat'
import { useAudioRecorder } from '../composables/useAudioRecorder'
import { normalizeUnlockedPlaces, useChatMessages } from '../composables/useChatMessages'
import { useChatAudio } from '../composables/useChatAudio'
import { useTypingIndicator } from '../composables/useTypingIndicator'
import { useChatActions } from '../composables/useChatActions'
import { useSound } from '@/core/composables/useSound'
import { useToast } from '@/core/composables/useToast'
import { useMapStore } from '@/modules/map/stores/map'
import type { MapPlaceLink } from '@/modules/dwellers/models/dweller'
import ChatMessageList from './ChatMessageList.vue'

const props = defineProps<{
  dwellerId: string
  dwellerName: string
  username: string
  dwellerAvatar?: string
  vaultId?: string | null
  dwellerStatus?: string
  roomName?: string | null
}>()

const authStore = useAuthStore()
const profileStore = useProfileStore()
const mapStore = useMapStore()

const isSendingAudio = ref(false)
const audioMode = ref(false)

const userAvatarUrl = computed(() => profileStore.profile?.avatar_url ?? undefined)
const dwellerActivity = computed(() => {
  if (props.dwellerStatus === 'exploring') return 'EXPLORING'
  if (props.dwellerStatus === 'questing') return 'ON QUEST'
  if (props.roomName) {
    const activity = props.dwellerStatus === 'working' ? 'ON DUTY' : props.dwellerStatus?.toUpperCase()
    return `${activity ?? 'ON DUTY'} · ${props.roomName.toUpperCase()}`
  }
  return props.dwellerStatus && props.dwellerStatus !== 'idle' ? props.dwellerStatus.toUpperCase() : 'AVAILABLE'
})

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

const chatBudgetSummary = computed(() => {
  const stats = profileStore.aiUsageStats
  if (!stats || stats.quota_exceeded || typeof stats.quota_remaining !== 'number') return null
  return `${stats.quota_remaining.toLocaleString()} tokens remaining`
})

const placeLinks = computed(() => mapStore.locations
  .filter((location) => location.dwellers?.some((dweller) => dweller.dweller_id === props.dwellerId))
  .map((location): MapPlaceLink => ({ name: location.name, locationId: location.id })))

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
const toast = useToast()

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
  retryMessage,
  dismissAction,
  getHappinessColor,
  getHappinessIcon,
} = useChatMessages({
  dwellerId: props.dwellerId,
  dwellerAvatar: props.dwellerAvatar,
  token: authStore.token,
  userImageUrl: userAvatarUrl,
  chatWs,
})

const { currentlyPlayingUrl, stopAudio, playAudio } = useChatAudio()
const { playSound } = useSound()

const { handleTyping } = useTypingIndicator(chatWs)

const conversationStarters = computed(() =>
  messages.value.length ? [] : placeLinks.value.slice(0, 3).map(({ name }) => `What can you tell me about ${name}?`)
)
const prefillConversationStarter = (message: string) => {
  userMessage.value = message
  chatInputRef.value?.focus()
}

const { isPerformingAction, handleActionConfirm, refreshAfterChat } = useChatActions({
  dwellerId: props.dwellerId,
  dwellerName: props.dwellerName,
  messages,
  vaultId: props.vaultId,
})

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
      audioUrl: response.data.dweller_audio_url,
      happinessImpact: response.data.happiness_impact || null,
      actionSuggestion: response.data.action_suggestion || null,
      unlockedPlaces: normalizeUnlockedPlaces(response.data.unlocked_places),
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
  if (props.vaultId && authStore.token) {
    void mapStore.fetchMap(props.vaultId, authStore.token)
  }
  if (!profileStore.hasProfile) {
    profileStore.fetchProfile().catch(() => {
      // Already reported by the store (handleStoreError); chat falls back to the icon avatar.
    })
  }
  if (!profileStore.aiUsageStats) {
    profileStore.fetchAIUsage().catch(() => {
      // Chat remains usable when the optional budget readout is unavailable.
    })
  }
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
        <DwellerPortrait
          :thumbnail-url="dwellerAvatarUrl"
          :alt="dwellerName"
          image-class="header-avatar-image"
          fallback-class="header-avatar-icon"
        />
      </div>
      <div class="identity-info">
        <span class="identity-name">{{ dwellerName }}</span>
        <span class="identity-status">{{ dwellerActivity }}</span>
      </div>
    </div>

    <div ref="chatMessages" class="chat-messages">
      <div
        v-if="conversationStarters.length"
        class="mb-5 flex flex-wrap gap-2 border-b border-theme-primary/15 pb-4"
        aria-label="Conversation starters"
      >
        <p class="w-full text-xs tracking-[0.12em] text-theme-primary/60">VAULT-TEC PROMPTS</p>
        <button
          v-for="starter in conversationStarters"
          :key="starter"
          type="button"
          class="conversation-starter border border-theme-primary/35 bg-theme-primary/5 px-2.5 py-1.5 text-left text-xs text-theme-primary transition-colors hover:bg-theme-primary/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
          @click="prefillConversationStarter(starter)"
        >
          {{ starter }}
        </button>
      </div>
      <ChatMessageList
        :messages="messages"
        :vault-id="vaultId"
        :place-links="placeLinks"
        :dweller-name="dwellerName"
        :username="username"
        :dweller-avatar-url="dwellerAvatarUrl"
        :user-avatar-url="userAvatar"
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
        @retry-message="retryMessage"
      />
    </div>

    <div v-if="chatBudgetSummary" class="chat-budget-status flex items-center justify-between gap-3 border-t border-theme-primary/15 bg-surface-sunken px-4 py-2 text-xs text-theme-primary/70" role="status">
      <span class="flex items-center gap-1.5">
        <Icon icon="mdi:robot-outline" class="h-4 w-4 text-theme-primary/70" />
        {{ chatBudgetSummary }}
      </span>
      <RouterLink to="/profile" class="text-theme-primary underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary">
        Usage details
      </RouterLink>
    </div>

    <div v-if="isQuotaExceeded" class="chat-input quota-exceeded">
      <div class="quota-blocked-message">
        <Icon icon="mdi:alert-circle" class="quota-icon" />
        <div class="quota-text">
          <span class="quota-title">Monthly quota exceeded</span>
          <span class="quota-reset">Resets on {{ resetDate }}</span>
        </div>
        <RouterLink to="/profile" class="quota-profile-btn">View Profile</RouterLink>
      </div>
    </div>

    <div v-else class="chat-input">
      <button
        class="mode-toggle-btn"
        :title="audioMode ? 'Switch to text' : 'Switch to voice'"
        :aria-label="audioMode ? 'Switch to text input' : 'Switch to voice input'"
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
          aria-label="Send message"
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
          aria-label="Start recording"
          :disabled="isSendingAudio"
          @click="startRecording"
        >
          <Icon icon="mdi:microphone" class="h-6 w-6" />
        </button>
        <template v-else>
          <button class="cancel-btn" title="Cancel" aria-label="Cancel recording" @click="cancelRecording">
            <Icon icon="mdi:close" class="h-5 w-5" />
          </button>
          <button class="send-audio-btn" title="Send recording" aria-label="Send recording" @click="sendAudioMessage">
            <Icon icon="mdi:send" class="h-5 w-5" />
          </button>
        </template>
      </template>
    </div>
  </div>
</template>

<style src="./DwellerChat.css"></style>
