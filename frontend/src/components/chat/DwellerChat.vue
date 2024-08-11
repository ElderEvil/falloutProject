<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import apiClient from '@/plugins/axios'

const props = defineProps<{
  dwellerId: string
  dwellerName: string
  username: string
}>()

const messages = ref<Array<{ type: 'user' | 'dweller'; content: string }>>([])
const userMessage = ref('')
const chatMessages = ref<HTMLElement | null>(null)
const isTyping = ref(false)

const sendMessage = async () => {
  if (userMessage.value.trim()) {
    messages.value.push({ type: 'user', content: userMessage.value })
    isTyping.value = true
    try {
      const response = await apiClient.post(`/api/v1/chat/${props.dwellerId}`, {
        message: userMessage.value
      })
      messages.value.push({ type: 'dweller', content: response.data.response })
    } catch (error) {
      console.error('Error sending message:', error)
    } finally {
      isTyping.value = false
    }
    userMessage.value = ''
  }
}

watchEffect(() => {
  if (chatMessages.value) {
    chatMessages.value.scrollTop = chatMessages.value.scrollHeight
  }
})
</script>

<template>
  <div class="chat-container">
    <div class="chat-messages" ref="chatMessages">
      <div v-for="(message, index) in messages" :key="index" :class="message.type">
        <div class="message-label">{{ message.type === 'user' ? username : dwellerName }}</div>
        <div class="message-content">
          {{ message.content }}
        </div>
      </div>
      <div v-if="isTyping" class="typing-indicator">{{ dwellerName }} is typing...</div>
    </div>
    <div class="chat-input">
      <input v-model="userMessage" @keyup.enter="sendMessage" placeholder="Type your message..." />
      <button @click="sendMessage">Send</button>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=VT323&display=swap');

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  justify-content: space-between;
  font-family: 'VT323', monospace;
  background-color: #0a0a0a;
  color: #33ff00;
  padding: 1rem;
}

.chat-messages {
  flex-grow: 1;
  overflow-y: auto;
  padding: 1rem;
  background-color: #1a1a1a;
  border: 2px solid #33ff00;
  border-radius: 10px;
}

.chat-input {
  display: flex;
  padding: 1rem 0;
  background-color: #0a0a0a;
  border-top: 2px solid #33ff00;
  margin-top: 1rem;
}

.chat-input input {
  flex-grow: 1;
  margin-right: 1rem;
  padding: 10px;
  border-radius: 5px;
  border: 1px solid #33ff00;
  background-color: #1a1a1a;
  color: #33ff00;
  font-family: 'VT323', monospace;
  font-size: 1.2rem;
}

.chat-input button {
  padding: 10px 20px;
  border-radius: 5px;
  border: 1px solid #33ff00;
  background-color: #1a1a1a;
  color: #33ff00;
  cursor: pointer;
  font-family: 'VT323', monospace;
  font-size: 1.2rem;
  transition: all 0.3s ease;
}

.chat-input button:hover {
  background-color: #33ff00;
  color: #0a0a0a;
}

.user,
.dweller {
  margin-bottom: 1rem;
  max-width: 75%;
}

.user {
  margin-left: auto;
}

.dweller {
  margin-right: auto;
}

.message-label {
  font-size: 0.9rem;
  margin-bottom: 0.2rem;
  opacity: 0.8;
}

.message-content {
  background-color: #2a2a2a;
  color: #33ff00;
  border: 1px solid #33ff00;
  border-radius: 5px;
  padding: 10px 15px;
  font-size: 1.2rem;
  line-height: 1.4;
  word-wrap: break-word;
}

.typing-indicator {
  font-style: italic;
  color: #33ff00;
  margin: 5px 0;
  padding-left: 10px;
  opacity: 0.8;
}

/* Typing animation with ellipsis */
.typing-indicator::after {
  content: ' ';
  animation: ellipsis 1.25s infinite;
}

@keyframes ellipsis {
  0% {
    content: ' ';
  }
  33% {
    content: '.';
  }
  66% {
    content: '..';
  }
  100% {
    content: '...';
  }
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 10px;
}

::-webkit-scrollbar-track {
  background: #0a0a0a;
}

::-webkit-scrollbar-thumb {
  background: #33ff00;
  border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
  background: #29cc00;
}
</style>
