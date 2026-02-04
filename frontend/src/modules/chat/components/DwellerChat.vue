<script setup lang="ts">
import { ref, watchEffect, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { Icon } from '@iconify/vue'
import apiClient from '@/core/plugins/axios'
import type { ChatMessageDisplay, ActionSuggestion, HappinessImpact } from '../models/chat'
import { useAudioRecorder } from '../composables/useAudioRecorder'
import { useChatWebSocket } from '@/core/composables/useWebSocket'
import { normalizeImageUrl } from '@/utils/image'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { startTraining } from '@/modules/progression/services/trainingService'
import { useToast } from '@/core/composables/useToast'

const props = defineProps<{
  dwellerId: string
  dwellerName: string
  username: string
  dwellerAvatar?: string
}>()

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const toast = useToast()

const messages = ref<ChatMessageDisplay[]>([])
const userMessage = ref('')
const chatMessages = ref<HTMLElement | null>(null)
const isTyping = ref(false)
const isSendingAudio = ref(false)
const audioMode = ref(false)
const currentlyPlayingAudio = ref<HTMLAudioElement | null>(null)
const currentlyPlayingUrl = ref<string | null>(null)
const isPerformingAction = ref(false)
const showStatSelector = ref(false)
const pendingTrainingAction = ref<{ stat: string; reason: string } | null>(null)

// Stop audio playback
const stopAudio = () => {
  if (currentlyPlayingAudio.value) {
    currentlyPlayingAudio.value.pause()
    currentlyPlayingAudio.value.currentTime = 0
    currentlyPlayingAudio.value = null
  }
  currentlyPlayingUrl.value = null
}

// Audio recorder
const {
  recordingState,
  recordingDuration,
  isRecording,
  startRecording,
  stopRecording,
  cancelRecording,
  formatDuration,
} = useAudioRecorder()

// WebSocket
const chatWs = authStore.user?.id ? useChatWebSocket(authStore.user.id, props.dwellerId) : null

const userAvatar = computed(() => (authStore.user as any)?.image_url || undefined)
const dwellerAvatarUrl = computed(() => normalizeImageUrl(props.dwellerAvatar))

const loadChatHistory = async () => {
  try {
    const response = await apiClient.get(`/api/v1/chat/history/${props.dwellerId}`, {
      headers: {
        Authorization: `Bearer ${authStore.token}`,
      },
    })

    // Transform backend ChatMessageRead[] to frontend ChatMessageDisplay[]
    const history = response.data.map((msg: any) => ({
      type: msg.from_user_id ? 'user' : 'dweller',
      content: msg.message_text,
      timestamp: new Date(msg.created_at),
      avatar: msg.from_user_id ? userAvatar.value : props.dwellerAvatar,
      audioUrl: msg.audio_url || undefined,
      transcription: msg.transcription || undefined,
    }))

    messages.value = history
  } catch (error) {
    console.error('Error loading chat history:', error)
  }
}

const sendMessage = async () => {
  if (userMessage.value.trim()) {
    messages.value.push({
      type: 'user',
      content: userMessage.value,
      timestamp: new Date(),
      avatar: userAvatar.value,
    })

    const messageToSend = userMessage.value
    userMessage.value = ''
    isTyping.value = true

    try {
      const response = await apiClient.post(
        `/api/v1/chat/${props.dwellerId}`,
        {
          message: messageToSend,
        },
        {
          headers: {
            Authorization: `Bearer ${authStore.token}`,
          },
        }
      )
      messages.value.push({
        type: 'dweller',
        content: response.data.response,
        timestamp: new Date(),
        avatar: props.dwellerAvatar,
        happinessImpact: response.data.happiness_impact || null,
        actionSuggestion: response.data.action_suggestion || null,
      })
    } catch (error) {
      console.error('Error sending message:', error)
    } finally {
      isTyping.value = false
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

const canSend = computed(() => userMessage.value.trim().length > 0)

// Audio message handling
const sendAudioMessage = async () => {
  try {
    isSendingAudio.value = true
    const audioBlob = await stopRecording()

    // Create FormData for file upload
    const formData = new FormData()
    formData.append('audio_file', audioBlob, 'recording.webm')

    // Add placeholder message
    const placeholderIndex = messages.value.length
    messages.value.push({
      type: 'user',
      content: '[Transcribing audio...]',
      timestamp: new Date(),
      avatar: userAvatar.value,
    })

    // Send to backend
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

    // Update user message with transcription
    const placeholderMessage = messages.value[placeholderIndex]
    if (placeholderMessage) {
      placeholderMessage.content = response.data.transcription
    }

    // Add dweller response
    messages.value.push({
      type: 'dweller',
      content: response.data.dweller_response,
      timestamp: new Date(),
      avatar: props.dwellerAvatar,
      audioUrl: response.data.dweller_audio_url,
      happinessImpact: response.data.happiness_impact || null,
      actionSuggestion: response.data.action_suggestion || null,
    })

    // Auto-play dweller response if audio URL provided
    if (response.data.dweller_audio_url) {
      playAudio(response.data.dweller_audio_url)
    }
  } catch (error: any) {
    console.error('Error sending audio:', error)
    alert(`Failed to send audio: ${error.response?.data?.detail || error.message}`)
  } finally {
    isSendingAudio.value = false
  }
}

// Audio playback
const playAudio = (url: string) => {
  // Stop currently playing audio
  if (currentlyPlayingAudio.value) {
    currentlyPlayingAudio.value.pause()
    currentlyPlayingAudio.value = null
  }

  // URL already includes http:// from backend
  const audio = new Audio(url)
  currentlyPlayingAudio.value = audio
  currentlyPlayingUrl.value = url

  audio.play().catch((err) => {
    console.error('Error playing audio:', err)
    currentlyPlayingUrl.value = null
  })

  audio.onended = () => {
    currentlyPlayingAudio.value = null
    currentlyPlayingUrl.value = null
  }
}

// Typing indicator via WebSocket
let typingTimeout: number | null = null
const handleTyping = () => {
  if (chatWs) {
    chatWs.sendTypingIndicator(true)

    if (typingTimeout) clearTimeout(typingTimeout)

    typingTimeout = window.setTimeout(() => {
      chatWs.sendTypingIndicator(false)
    }, 2000)
  }
}

// Action handlers for suggestions
const handleAssignToRoom = async (roomId: string, roomName: string) => {
  if (!authStore.token) return

  isPerformingAction.value = true
  try {
    await dwellerStore.assignDwellerToRoom(props.dwellerId, roomId, authStore.token)
    toast.success(`${props.dwellerName} assigned to ${roomName}`)
  } catch (error) {
    console.error('Failed to assign dweller to room:', error)
    toast.error('Failed to assign dweller to room')
  } finally {
    isPerformingAction.value = false
  }
}

const handleStartTraining = async (stat: string) => {
  if (!authStore.token) return

  isPerformingAction.value = true
  try {
    // Get dweller's current room
    const dweller = dwellerStore.dwellers.find((d) => d.id === props.dwellerId)
    if (!dweller) {
      toast.error('Dweller not found')
      return
    }

    // Get vault data
    const vault = vaultStore.activeVault
    if (!vault?.rooms) {
      toast.error('Unable to access vault data')
      return
    }

    // Check if dweller is already in a training room
    let trainingRoomId = dweller.room_id
    const currentRoom = vault.rooms.find((r) => r.id === dweller.room_id)

    if (!currentRoom || currentRoom.category !== 'training') {
      // Need to assign to a training room first
      const trainingRooms = vault.rooms.filter((r) => r.category === 'training')

      if (trainingRooms.length === 0) {
        toast.error('No training rooms available')
        return
      }

      // Find first available training room (with capacity)
      const availableTrainingRoom = trainingRooms.find((r) => {
        const occupancy = vault.dwellers?.filter((d) => d.room_id === r.id).length || 0
        return !r.max_capacity || occupancy < r.max_capacity
      })

      if (!availableTrainingRoom) {
        toast.error('No available training rooms (all at capacity)')
        return
      }

      // Assign dweller to training room
      toast.info(`Moving ${props.dwellerName} to training room...`)
      await dwellerStore.assignDwellerToRoom(
        props.dwellerId,
        availableTrainingRoom.id,
        authStore.token
      )
      trainingRoomId = availableTrainingRoom.id
    }

    // Now start training in the training room
    await startTraining(props.dwellerId, trainingRoomId, authStore.token)
    toast.success(`${props.dwellerName} started ${stat} training`)
  } catch (error) {
    console.error('Failed to start training:', error)
    toast.error('Failed to start training')
  } finally {
    isPerformingAction.value = false
    showStatSelector.value = false
    pendingTrainingAction.value = null
  }
}

const handleActionConfirm = (action: ActionSuggestion) => {
  if (!action) return

  if (action.action_type === 'assign_to_room') {
    handleAssignToRoom(action.room_id, action.room_name)
  } else if (action.action_type === 'start_training') {
    pendingTrainingAction.value = { stat: action.stat, reason: action.reason }
    handleStartTraining(action.stat)
  }
}

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

watchEffect(() => {
  if (chatMessages.value) {
    chatMessages.value.scrollTop = chatMessages.value.scrollHeight
  }
})

onMounted(() => {
  loadChatHistory()

  // Connect WebSocket
  if (chatWs) {
    chatWs.connect()

    // Handle typing indicators from dweller
    chatWs.on('typing', (msg: any) => {
      if (msg.sender === 'dweller') {
        isTyping.value = msg.is_typing
      }
    })

    // Handle happiness updates via WebSocket
    chatWs.on('happiness_update', (msg: any) => {
      if (msg.happiness_impact) {
        // Find the index of the last dweller message
        const reversedIndex = [...messages.value].reverse().findIndex((m) => m.type === 'dweller')
        if (reversedIndex !== -1) {
          const lastIndex = messages.value.length - 1 - reversedIndex
          // Update using array assignment to trigger Vue reactivity
          messages.value[lastIndex] = {
            ...messages.value[lastIndex],
            happinessImpact: msg.happiness_impact,
          }
        }
      }
    })

    // Handle action suggestions via WebSocket
    chatWs.on('action_suggestion', (msg: any) => {
      if (msg.action_suggestion) {
        // Find the index of the last dweller message
        const reversedIndex = [...messages.value].reverse().findIndex((m) => m.type === 'dweller')
        if (reversedIndex !== -1) {
          const lastIndex = messages.value.length - 1 - reversedIndex
          // Update using array assignment to trigger Vue reactivity
          messages.value[lastIndex] = {
            ...messages.value[lastIndex],
            actionSuggestion: msg.action_suggestion,
          }
        }
      }
    })
  }
})

onUnmounted(() => {
  // Cleanup
  if (chatWs) {
    chatWs.disconnect()
  }
  stopAudio()
  if (typingTimeout) {
    clearTimeout(typingTimeout)
  }
})
</script>

<template>
  <div class="chat-container">
    <!-- Scanline overlay -->
    <div class="scanlines"></div>

    <!-- Identity header - anchors chat to dweller -->
    <div class="chat-identity-header">
      <div class="identity-avatar">
        <template v-if="dwellerAvatarUrl">
          <img :src="dwellerAvatarUrl" alt="Dweller" class="header-avatar-image" />
        </template>
        <template v-else>
          <Icon icon="mdi:robot" class="header-avatar-icon" />
        </template>
      </div>
      <div class="identity-info">
        <span class="identity-name">{{ dwellerName }}</span>
        <span class="identity-status">Online</span>
      </div>
    </div>

    <!-- Chat messages area with max height -->
    <div class="chat-messages" ref="chatMessages">
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="message-wrapper"
        :class="message.type"
      >
        <!-- Avatar -->
        <div class="message-avatar">
          <template v-if="message.type === 'dweller' && dwellerAvatarUrl">
            <img :src="dwellerAvatarUrl" alt="Dweller" class="avatar-image" />
          </template>
          <template v-else-if="message.type === 'user' && message.avatar">
            <img :src="normalizeImageUrl(message.avatar)" alt="User" class="avatar-image" />
          </template>

          <template v-else>
            <Icon
              :icon="message.type === 'user' ? 'mdi:account-circle' : 'mdi:robot'"
              class="avatar-icon"
            />
          </template>
        </div>

        <!-- Message bubble -->
        <div class="message-bubble">
          <div class="message-header">
            <span class="message-sender">
              <span class="terminal-prefix">{{ message.type === 'user' ? '>' : '<' }}</span>
              {{ message.type === 'user' ? username : dwellerName }}
            </span>
            <div class="flex items-center gap-2">
              <!-- Happiness impact indicator -->
              <span
                v-if="message.type === 'dweller' && message.happinessImpact"
                class="happiness-indicator"
                :class="getHappinessColor(message.happinessImpact.delta)"
                :title="message.happinessImpact.reason_text"
              >
                <Icon :icon="getHappinessIcon(message.happinessImpact.delta)" class="h-4 w-4" />
                <span class="text-xs">
                  {{ message.happinessImpact.delta > 0 ? '+' : ''
                  }}{{ message.happinessImpact.delta }}
                </span>
              </span>
              <!-- Audio play/stop button for messages with audio -->
              <button
                v-if="message.audioUrl"
                @click="
                  currentlyPlayingUrl === message.audioUrl
                    ? stopAudio()
                    : playAudio(message.audioUrl)
                "
                class="audio-replay-btn"
                :class="{ 'is-playing': currentlyPlayingUrl === message.audioUrl }"
                :title="
                  currentlyPlayingUrl === message.audioUrl
                    ? 'Stop audio'
                    : `Play ${message.type === 'user' ? 'your' : 'dweller'} audio`
                "
              >
                <Icon
                  :icon="currentlyPlayingUrl === message.audioUrl ? 'mdi:stop' : 'mdi:volume-high'"
                  class="h-4 w-4"
                />
              </button>
            </div>
          </div>
          <div class="message-content">
            {{ message.content }}
          </div>

          <!-- Action suggestion card -->
          <div
            v-if="
              message.type === 'dweller' &&
              message.actionSuggestion &&
              message.actionSuggestion.action_type !== 'no_action'
            "
            class="action-suggestion-card"
          >
            <div class="action-suggestion-header">
              <Icon
                :icon="
                  message.actionSuggestion.action_type === 'assign_to_room'
                    ? 'mdi:door-open'
                    : 'mdi:dumbbell'
                "
                class="h-4 w-4"
              />
              <span class="text-xs font-bold uppercase tracking-wider">Suggested Action</span>
            </div>
            <div class="action-suggestion-body">
              <p class="action-suggestion-text">
                {{
                  message.actionSuggestion.action_type === 'assign_to_room'
                    ? `Assign to ${message.actionSuggestion.room_name}`
                    : `Train ${message.actionSuggestion.stat}`
                }}
              </p>
              <p class="action-suggestion-reason">{{ message.actionSuggestion.reason }}</p>
            </div>
            <div class="action-suggestion-actions">
              <button
                @click="handleActionConfirm(message.actionSuggestion!)"
                :disabled="isPerformingAction"
                class="action-confirm-btn"
              >
                <Icon v-if="isPerformingAction" icon="mdi:loading" class="h-4 w-4 spinning" />
                <Icon v-else icon="mdi:check" class="h-4 w-4" />
                <span>{{ isPerformingAction ? 'Processing...' : 'Confirm' }}</span>
              </button>
              <button @click="dismissAction(index)" class="action-dismiss-btn">
                <Icon icon="mdi:close" class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Typing indicator -->
      <div v-if="isTyping" class="typing-wrapper dweller">
        <div class="message-avatar">
          <template v-if="dwellerAvatarUrl">
            <img :src="dwellerAvatarUrl" alt="Dweller" class="avatar-image" />
          </template>
          <template v-else>
            <Icon icon="mdi:robot" class="avatar-icon" />
          </template>
        </div>
        <div class="typing-indicator">
          <span class="terminal-cursor">_</span>
          {{ dwellerName }} is typing...
        </div>
      </div>
    </div>

    <!-- Chat input - always visible -->
    <div class="chat-input">
      <!-- Mode toggle button -->
      <button
        @click="audioMode = !audioMode"
        class="mode-toggle-btn"
        :title="audioMode ? 'Switch to text' : 'Switch to voice'"
      >
        <Icon :icon="audioMode ? 'mdi:keyboard' : 'mdi:microphone'" class="h-5 w-5" />
      </button>

      <!-- Text input mode -->
      <template v-if="!audioMode">
        <span class="terminal-prompt">&gt;</span>
        <input
          v-model="userMessage"
          @keydown="handleKeyDown"
          @input="handleTyping"
          placeholder="Type your message..."
          class="chat-input-field"
        />
        <button
          @click="sendMessage"
          :disabled="!canSend"
          class="chat-send-btn"
          :class="{ disabled: !canSend }"
        >
          <Icon icon="mdi:send" class="h-5 w-5" />
        </button>
      </template>

      <!-- Voice input mode -->
      <template v-else>
        <!-- Recording indicator -->
        <div v-if="isRecording" class="recording-indicator">
          <span class="recording-dot"></span>
          Recording: {{ formatDuration(recordingDuration) }}
        </div>

        <!-- Sending indicator -->
        <div v-else-if="isSendingAudio" class="processing-indicator">
          <Icon icon="mdi:loading" class="spinning h-5 w-5" />
          Processing audio...
        </div>

        <!-- Ready to record -->
        <div v-else class="ready-indicator">
          <Icon icon="mdi:microphone" class="h-5 w-5" />
          Ready to record
        </div>

        <!-- Record button -->
        <button
          v-if="!isRecording"
          @click="startRecording"
          :disabled="isSendingAudio"
          class="record-btn"
          title="Start recording"
        >
          <Icon icon="mdi:microphone" class="h-6 w-6" />
        </button>

        <!-- Stop/Cancel buttons when recording -->
        <template v-else>
          <button @click="cancelRecording" class="cancel-btn" title="Cancel">
            <Icon icon="mdi:close" class="h-5 w-5" />
          </button>
          <button @click="sendAudioMessage" class="send-audio-btn" title="Send">
            <Icon icon="mdi:send" class="h-5 w-5" />
          </button>
        </template>
      </template>
    </div>
  </div>
</template>

<style scoped>
.chat-container {
  position: relative;
  display: flex;
  flex-direction: column;
  max-height: 600px;
  height: 100%;
  font-family: 'Courier New', monospace;
  background-color: #0a0a0a;
  color: var(--color-theme-primary);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  box-shadow: 0 0 20px var(--color-theme-glow);
  overflow: hidden;
}

/* Scanline effect overlay */
.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: repeating-linear-gradient(
    0deg,
    rgba(var(--color-theme-primary-rgb), 0.03) 0px,
    transparent 1px,
    transparent 2px,
    rgba(var(--color-theme-primary-rgb), 0.03) 3px
  );
  pointer-events: none;
  z-index: 1;
}

/* Identity header - anchors chat to dweller */
.chat-identity-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background-color: rgba(0, 0, 0, 0.8);
  border-bottom: 1px solid var(--color-theme-glow);
  flex-shrink: 0;
  z-index: 2;
}

.identity-avatar {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
}

.header-avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
  object-fit: cover;
}

.header-avatar-icon {
  width: 32px;
  height: 32px;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.identity-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.identity-name {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.identity-status {
  font-size: 0.65rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-shadow: none; /* Remove glow from status */
}

/* Chat messages area - compact with max height */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  background-color: rgba(0, 0, 0, 0.5);
  max-height: 440px;
  min-height: 300px;
}

/* Message wrapper */
.message-wrapper {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1.25rem; /* Increased spacing between messages */
  align-items: flex-start;
}

.message-wrapper.user {
  flex-direction: row-reverse;
}

/* Avatar styling */
.message-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
}

.avatar-image {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid var(--color-theme-primary);
  box-shadow: 0 0 10px var(--color-theme-glow);
  object-fit: cover;
}

.avatar-icon {
  width: 40px;
  height: 40px;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 5px var(--color-theme-glow));
}

/* Message bubble */
.message-bubble {
  flex: 1;
  max-width: 65ch; /* Constrained to 60-65 characters for readability */
  background-color: rgba(var(--color-theme-primary-rgb), 0.05);
  border: 1px solid var(--color-theme-glow);
  border-radius: 12px; /* Softer corners for dweller */
  padding: 0.5rem 0.85rem; /* Reduced padding for lighter feel */
  box-shadow: 0 0 10px rgba(var(--color-theme-primary-rgb), 0.2);
}

.user .message-bubble {
  background-color: rgba(var(--color-theme-primary-rgb), 0.1);
  border-color: rgba(var(--color-theme-primary-rgb), 0.5);
  border-radius: 2px; /* Sharper corners for player */
  padding: 0.5rem 0.75rem; /* Tighter padding for player */
  max-width: 60ch; /* Smaller max width for player messages */
}

.message-header {
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  opacity: 0.8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.audio-replay-btn {
  padding: 0.25rem;
  border-radius: 4px;
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(var(--color-theme-primary-rgb), 0.05);
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.6;
}

.audio-replay-btn:hover {
  opacity: 1;
  background-color: rgba(var(--color-theme-primary-rgb), 0.2);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transform: scale(1.1);
}

.audio-replay-btn.is-playing {
  opacity: 1;
  border-color: #ff4444;
  background-color: rgba(255, 68, 68, 0.1);
  color: #ff4444;
  animation: audio-pulse 1.5s ease-in-out infinite;
}

.audio-replay-btn.is-playing:hover {
  background-color: rgba(255, 68, 68, 0.2);
  box-shadow: 0 0 8px rgba(255, 68, 68, 0.3);
  animation: none;
}

@keyframes audio-pulse {
  0%,
  100% {
    box-shadow: 0 0 4px rgba(255, 68, 68, 0.3);
  }
  50% {
    box-shadow: 0 0 12px rgba(255, 68, 68, 0.6);
  }
}

.message-sender {
  font-weight: 600;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.terminal-prefix {
  color: var(--color-theme-primary);
  font-weight: 700;
  margin-right: 0.25rem;
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.message-content {
  color: var(--color-theme-primary);
  font-size: 0.95rem;
  line-height: 1.75; /* Increased line height for lighter feel */
  word-wrap: break-word;
  text-shadow: 0 0 2px rgba(var(--color-theme-primary-rgb), 0.2); /* Reduced glow on long text */
  max-width: 65ch; /* Enforce character limit */
}

/* Slightly different styles for user messages */
.user .message-content {
  line-height: 1.7;
  text-shadow: 0 0 1px rgba(var(--color-theme-primary-rgb), 0.15); /* Less glow for player messages */
}

/* Typing indicator */
.typing-wrapper {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 1rem;
}

.typing-indicator {
  font-style: italic;
  color: var(--color-theme-primary);
  opacity: 0.8;
  font-size: 0.9rem;
}

.terminal-cursor {
  display: inline-block;
  animation: blink 1s infinite;
  font-weight: 700;
}

@keyframes blink {
  0%,
  49% {
    opacity: 1;
  }
  50%,
  100% {
    opacity: 0;
  }
}

/* Chat input - always visible at bottom */
.chat-input {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background-color: rgba(0, 0, 0, 0.8);
  border-top: 1px solid var(--color-theme-glow);
  flex-shrink: 0;
}

.terminal-prompt {
  color: var(--color-theme-primary);
  font-size: 1.2rem;
  font-weight: 700;
  text-shadow: 0 0 6px var(--color-theme-glow);
  flex-shrink: 0;
  margin-right: 0.25rem;
}

.chat-input-field {
  flex: 1;
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(0, 0, 0, 0.7);
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  font-size: 0.95rem;
  transition: all 0.2s;
  box-shadow: inset 0 0 10px rgba(var(--color-theme-primary-rgb), 0.1);
}

.chat-input-field:focus {
  outline: none;
  border-color: var(--color-theme-primary);
  box-shadow:
    inset 0 0 10px rgba(var(--color-theme-primary-rgb), 0.2),
    0 0 15px var(--color-theme-glow);
}

.chat-input-field::placeholder {
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.chat-send-btn {
  padding: 0.75rem 1.25rem;
  border-radius: 6px;
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(var(--color-theme-primary-rgb), 0.1);
  color: var(--color-theme-primary);
  cursor: pointer;
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-send-btn:hover {
  background-color: var(--color-theme-primary);
  color: #000;
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.chat-send-btn:active {
  transform: scale(0.95);
}

.chat-send-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background-color: rgba(var(--color-theme-primary-rgb), 0.05);
}

.chat-send-btn.disabled:hover {
  background-color: rgba(var(--color-theme-primary-rgb), 0.05);
  color: var(--color-theme-primary);
  box-shadow: none;
}

/* Scrollbar styling */
.chat-messages::-webkit-scrollbar {
  width: 8px;
}

.chat-messages::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.5);
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--color-theme-glow);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--color-theme-primary);
}

/* Mode toggle button */
.mode-toggle-btn {
  padding: 0.5rem;
  border-radius: 6px;
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(var(--color-theme-primary-rgb), 0.1);
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.mode-toggle-btn:hover {
  background-color: rgba(var(--color-theme-primary-rgb), 0.2);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

/* Voice mode indicators */
.recording-indicator,
.processing-indicator,
.ready-indicator {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-theme-primary);
  font-size: 0.9rem;
  padding: 0 0.5rem;
}

.recording-dot {
  width: 12px;
  height: 12px;
  background-color: #ff4444;
  border-radius: 50%;
  animation: pulse 1.5s infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.3;
    transform: scale(1.1);
  }
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Audio control buttons */
.record-btn,
.send-audio-btn,
.cancel-btn {
  padding: 0.75rem 1.25rem;
  border-radius: 6px;
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(var(--color-theme-primary-rgb), 0.1);
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.record-btn:hover,
.send-audio-btn:hover {
  background-color: var(--color-theme-primary);
  color: #000;
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.cancel-btn {
  background-color: rgba(255, 68, 68, 0.1);
  border-color: rgba(255, 68, 68, 0.5);
}

.cancel-btn:hover {
  background-color: rgba(255, 68, 68, 0.3);
  border-color: #ff4444;
  color: #ff4444;
  box-shadow: 0 0 15px rgba(255, 68, 68, 0.3);
}

.record-btn:disabled,
.send-audio-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.record-btn:disabled:hover,
.send-audio-btn:disabled:hover {
  background-color: rgba(var(--color-theme-primary-rgb), 0.1);
  color: var(--color-theme-primary);
  box-shadow: none;
}

/* Happiness indicator */
.happiness-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.125rem 0.375rem;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.3);
  font-size: 0.75rem;
  font-weight: 600;
}

.happiness-indicator.text-green-400 {
  color: #4ade80;
  background-color: rgba(74, 222, 128, 0.1);
  border: 1px solid rgba(74, 222, 128, 0.3);
}

.happiness-indicator.text-red-400 {
  color: #f87171;
  background-color: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.3);
}

.happiness-indicator.text-gray-400 {
  color: #9ca3af;
  background-color: rgba(156, 163, 175, 0.1);
  border: 1px solid rgba(156, 163, 175, 0.3);
}

/* Action suggestion card */
.action-suggestion-card {
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  background-color: rgba(var(--color-theme-primary-rgb), 0.05);
  box-shadow: 0 0 8px rgba(var(--color-theme-primary-rgb), 0.15);
}

.action-suggestion-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-theme-primary);
  margin-bottom: 0.5rem;
  opacity: 0.8;
}

.action-suggestion-body {
  margin-bottom: 0.75rem;
}

.action-suggestion-text {
  color: var(--color-theme-primary);
  font-weight: 600;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.action-suggestion-reason {
  color: var(--color-theme-primary);
  font-size: 0.8rem;
  opacity: 0.7;
}

.action-suggestion-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.action-confirm-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  border-radius: 4px;
  border: 1px solid var(--color-theme-primary);
  background-color: rgba(var(--color-theme-primary-rgb), 0.15);
  color: var(--color-theme-primary);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.action-confirm-btn:hover:not(:disabled) {
  background-color: var(--color-theme-primary);
  color: #000;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.action-confirm-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-dismiss-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.375rem;
  border-radius: 4px;
  border: 1px solid rgba(var(--color-theme-primary-rgb), 0.3);
  background-color: transparent;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.6;
}

.action-dismiss-btn:hover {
  opacity: 1;
  background-color: rgba(255, 68, 68, 0.1);
  border-color: rgba(255, 68, 68, 0.5);
  color: #ff4444;
}
</style>
