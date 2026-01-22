<script setup lang="ts">
import { ref, watchEffect, computed, onMounted, onUnmounted } from 'vue';
import { useAuthStore } from '@/modules/auth/stores/auth';
import { Icon } from '@iconify/vue';
import apiClient from '@/core/plugins/axios';
import type { ChatMessageDisplay } from '../models/chat';
import { useAudioRecorder } from '../composables/useAudioRecorder';
import { useChatWebSocket } from '@/core/composables/useWebSocket';

const props = defineProps<{
  dwellerId: string
  dwellerName: string
  username: string
  dwellerAvatar?: string
}>();

const authStore = useAuthStore();
const messages = ref<ChatMessageDisplay[]>([]);
const userMessage = ref('');
const chatMessages = ref<HTMLElement | null>(null);
const isTyping = ref(false);
const isSendingAudio = ref(false);
const audioMode = ref(false);
const currentlyPlayingAudio = ref<HTMLAudioElement | null>(null);

// Audio recorder
const {
  recordingState,
  recordingDuration,
  isRecording,
  startRecording,
  stopRecording,
  cancelRecording,
  formatDuration
} = useAudioRecorder();

// WebSocket
const chatWs = authStore.user?.id
  ? useChatWebSocket(authStore.user.id, props.dwellerId)
  : null;

const userAvatar = computed(() => (authStore.user as any)?.image_url || undefined);
const dwellerAvatarUrl = computed(() => props.dwellerAvatar ? `http://${props.dwellerAvatar}` : '');

const loadChatHistory = async () => {
  try {
    const response = await apiClient.get(
      `/api/v1/chat/history/${props.dwellerId}`,
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`
        }
      }
    );

    // Transform backend ChatMessageRead[] to frontend ChatMessageDisplay[]
    const history = response.data.map((msg: any) => ({
      type: msg.from_user_id ? 'user' : 'dweller',
      content: msg.message_text,
      timestamp: new Date(msg.created_at),
      avatar: msg.from_user_id ? userAvatar.value : props.dwellerAvatar,
      audioUrl: msg.audio_url || undefined,
      transcription: msg.transcription || undefined
    }));

    messages.value = history;
  } catch (error) {
    console.error('Error loading chat history:', error);
  }
};

const sendMessage = async () => {
  if (userMessage.value.trim()) {
    messages.value.push({
      type: 'user',
      content: userMessage.value,
      timestamp: new Date(),
      avatar: userAvatar.value
    });

    const messageToSend = userMessage.value;
    userMessage.value = '';
    isTyping.value = true;

    try {
      const response = await apiClient.post(
        `/api/v1/chat/${props.dwellerId}`,
        {
          message: messageToSend
        },
        {
          headers: {
            Authorization: `Bearer ${authStore.token}`
          }
        }
      );
      messages.value.push({
        type: 'dweller',
        content: response.data.response,
        timestamp: new Date(),
        avatar: props.dwellerAvatar
      });
    } catch (error) {
      console.error('Error sending message:', error);
    } finally {
      isTyping.value = false;
    }
  }
};

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
  // Shift+Enter allows newline (default behavior)
};

const canSend = computed(() => userMessage.value.trim().length > 0);

// Audio message handling
const sendAudioMessage = async () => {
  try {
    isSendingAudio.value = true;
    const audioBlob = await stopRecording();

    // Create FormData for file upload
    const formData = new FormData();
    formData.append('audio_file', audioBlob, 'recording.webm');

    // Add placeholder message
    const placeholderIndex = messages.value.length;
    messages.value.push({
      type: 'user',
      content: '[Transcribing audio...]',
      timestamp: new Date(),
      avatar: userAvatar.value
    });

    // Send to backend
    const response = await apiClient.post(
      `/api/v1/chat/${props.dwellerId}/voice?return_audio=false`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'multipart/form-data'
        }
      }
    );

    // Update user message with transcription
    const placeholderMessage = messages.value[placeholderIndex];
    if (placeholderMessage) {
      placeholderMessage.content = response.data.transcription;
    }

    // Add dweller response
    messages.value.push({
      type: 'dweller',
      content: response.data.dweller_response,
      timestamp: new Date(),
      avatar: props.dwellerAvatar,
      audioUrl: response.data.dweller_audio_url
    });

    // Auto-play dweller response if audio URL provided
    if (response.data.dweller_audio_url) {
      playAudio(response.data.dweller_audio_url);
    }

  } catch (error: any) {
    console.error('Error sending audio:', error);
    alert(`Failed to send audio: ${error.response?.data?.detail || error.message}`);
  } finally {
    isSendingAudio.value = false;
  }
};

// Audio playback
const playAudio = (url: string) => {
  // Stop currently playing audio
  if (currentlyPlayingAudio.value) {
    currentlyPlayingAudio.value.pause();
    currentlyPlayingAudio.value = null;
  }

  // URL already includes http:// from backend
  const audio = new Audio(url);
  currentlyPlayingAudio.value = audio;

  audio.play().catch(err => {
    console.error('Error playing audio:', err);
  });

  audio.onended = () => {
    currentlyPlayingAudio.value = null;
  };
};

// Typing indicator via WebSocket
let typingTimeout: number | null = null;
const handleTyping = () => {
  if (chatWs) {
    chatWs.sendTypingIndicator(true);

    if (typingTimeout) clearTimeout(typingTimeout);

    typingTimeout = window.setTimeout(() => {
      chatWs.sendTypingIndicator(false);
    }, 2000);
  }
};

watchEffect(() => {
  if (chatMessages.value) {
    chatMessages.value.scrollTop = chatMessages.value.scrollHeight;
  }
});

onMounted(() => {
  loadChatHistory();

  // Connect WebSocket
  if (chatWs) {
    chatWs.connect();

    // Handle typing indicators from dweller
    chatWs.on('typing', (msg: any) => {
      if (msg.sender === 'dweller') {
        isTyping.value = msg.is_typing;
      }
    });
  }
});

onUnmounted(() => {
  // Cleanup
  if (chatWs) {
    chatWs.disconnect();
  }
  if (currentlyPlayingAudio.value) {
    currentlyPlayingAudio.value.pause();
    currentlyPlayingAudio.value = null;
  }
  if (typingTimeout) {
    clearTimeout(typingTimeout);
  }
});
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
            <img :src="`http://${message.avatar}`" alt="User" class="avatar-image" />
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
            <!-- Audio replay button for messages with audio -->
            <button
              v-if="message.audioUrl"
              @click="playAudio(message.audioUrl)"
              class="audio-replay-btn"
              :title="`Play ${message.type === 'user' ? 'your' : 'dweller'} audio`"
            >
              <Icon icon="mdi:volume-high" class="h-4 w-4" />
            </button>
          </div>
          <div class="message-content">
            {{ message.content }}
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
          <button
            @click="cancelRecording"
            class="cancel-btn"
            title="Cancel"
          >
            <Icon icon="mdi:close" class="h-5 w-5" />
          </button>
          <button
            @click="sendAudioMessage"
            class="send-audio-btn"
            title="Send"
          >
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
  background-color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transform: scale(1.1);
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
  0%, 49% {
    opacity: 1;
  }
  50%, 100% {
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
  box-shadow: inset 0 0 10px rgba(var(--color-theme-primary-rgb), 0.2),
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
  0%, 100% {
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
</style>
