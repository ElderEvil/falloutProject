<script setup lang="ts">
import { ref, watchEffect, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { Icon } from '@iconify/vue'
import apiClient from '@/plugins/axios'
import type { ChatMessageDisplay } from '@/models/chat'

const props = defineProps<{
  dwellerId: string
  dwellerName: string
  username: string
  dwellerAvatar?: string
}>()

const authStore = useAuthStore()
const messages = ref<ChatMessageDisplay[]>([])
const userMessage = ref('')
const chatMessages = ref<HTMLElement | null>(null)
const isTyping = ref(false)

const userAvatar = computed(() => authStore.user?.avatar_url)
const dwellerAvatarUrl = computed(() => props.dwellerAvatar ? `http://${props.dwellerAvatar}` : '')

const sendMessage = async () => {
  if (userMessage.value.trim()) {
    messages.value.push({
      type: 'user',
      content: userMessage.value,
      timestamp: new Date(),
      avatar: userAvatar.value
    })

    const messageToSend = userMessage.value
    userMessage.value = ''
    isTyping.value = true

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
      )
      messages.value.push({
        type: 'dweller',
        content: response.data.response,
        timestamp: new Date(),
        avatar: props.dwellerAvatar
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

watchEffect(() => {
  if (chatMessages.value) {
    chatMessages.value.scrollTop = chatMessages.value.scrollHeight
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
      <span class="terminal-prompt">&gt;</span>
      <input
        v-model="userMessage"
        @keydown="handleKeyDown"
        placeholder="Type your message... (Shift+Enter for newline)"
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
  color: #00ff00;
  border: 2px solid #00ff00;
  border-radius: 8px;
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
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
    rgba(0, 255, 0, 0.03) 0px,
    transparent 1px,
    transparent 2px,
    rgba(0, 255, 0, 0.03) 3px
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
  border-bottom: 1px solid rgba(0, 255, 0, 0.3);
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
  border: 2px solid #00ff00;
  box-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
  object-fit: cover;
}

.header-avatar-icon {
  width: 32px;
  height: 32px;
  color: #00ff00;
  filter: drop-shadow(0 0 4px rgba(0, 255, 0, 0.5));
}

.identity-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.identity-name {
  font-size: 1rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.6);
}

.identity-status {
  font-size: 0.65rem;
  color: rgba(0, 255, 0, 0.5);
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
  border: 2px solid #00ff00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
  object-fit: cover;
}

.avatar-icon {
  width: 40px;
  height: 40px;
  color: #00ff00;
  filter: drop-shadow(0 0 5px rgba(0, 255, 0, 0.5));
}

/* Message bubble */
.message-bubble {
  flex: 1;
  max-width: 65ch; /* Constrained to 60-65 characters for readability */
  background-color: rgba(0, 255, 0, 0.05);
  border: 1px solid rgba(0, 255, 0, 0.3);
  border-radius: 12px; /* Softer corners for dweller */
  padding: 0.5rem 0.85rem; /* Reduced padding for lighter feel */
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
}

.user .message-bubble {
  background-color: rgba(0, 255, 0, 0.1);
  border-color: rgba(0, 255, 0, 0.5);
  border-radius: 2px; /* Sharper corners for player */
  padding: 0.5rem 0.75rem; /* Tighter padding for player */
  max-width: 60ch; /* Smaller max width for player messages */
}

.message-header {
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  opacity: 0.8;
}

.message-sender {
  font-weight: 600;
  text-shadow: 0 0 4px rgba(0, 255, 0, 0.5);
}

.terminal-prefix {
  color: #00ff00;
  font-weight: 700;
  margin-right: 0.25rem;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.8);
}

.message-content {
  color: #00ff00;
  font-size: 0.95rem;
  line-height: 1.75; /* Increased line height for lighter feel */
  word-wrap: break-word;
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.2); /* Reduced glow on long text */
  max-width: 65ch; /* Enforce character limit */
}

/* Slightly different styles for user messages */
.user .message-content {
  line-height: 1.7;
  text-shadow: 0 0 1px rgba(0, 255, 0, 0.15); /* Less glow for player messages */
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
  color: #00ff00;
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
  border-top: 1px solid rgba(0, 255, 0, 0.3);
  flex-shrink: 0;
}

.terminal-prompt {
  color: #00ff00;
  font-size: 1.2rem;
  font-weight: 700;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.8);
  flex-shrink: 0;
  margin-right: 0.25rem;
}

.chat-input-field {
  flex: 1;
  padding: 0.75rem;
  border-radius: 6px;
  border: 1px solid #00ff00;
  background-color: rgba(0, 0, 0, 0.7);
  color: #00ff00;
  font-family: 'Courier New', monospace;
  font-size: 0.95rem;
  transition: all 0.2s;
  box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.1);
}

.chat-input-field:focus {
  outline: none;
  border-color: #00ff00;
  box-shadow:
    inset 0 0 10px rgba(0, 255, 0, 0.2),
    0 0 15px rgba(0, 255, 0, 0.4);
}

.chat-input-field::placeholder {
  color: rgba(0, 255, 0, 0.5);
}

.chat-send-btn {
  padding: 0.75rem 1.25rem;
  border-radius: 6px;
  border: 1px solid #00ff00;
  background-color: rgba(0, 255, 0, 0.1);
  color: #00ff00;
  cursor: pointer;
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-send-btn:hover {
  background-color: #00ff00;
  color: #000;
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.6);
}

.chat-send-btn:active {
  transform: scale(0.95);
}

.chat-send-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background-color: rgba(0, 255, 0, 0.05);
}

.chat-send-btn.disabled:hover {
  background-color: rgba(0, 255, 0, 0.05);
  color: #00ff00;
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
  background: rgba(0, 255, 0, 0.5);
  border-radius: 4px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 255, 0, 0.7);
}
</style>
