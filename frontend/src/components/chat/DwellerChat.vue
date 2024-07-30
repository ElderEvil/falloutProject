<script setup lang="ts">
import { ref, onMounted, onUnmounted, watchEffect } from 'vue'

const props = defineProps<{
  dwellerId: string
}>()

const socket = ref<WebSocket | null>(null)
const messages = ref<Array<{ type: 'user' | 'dweller'; content: string }>>([])
const userMessage = ref('')
const chatMessages = ref<HTMLElement | null>(null)

const connectWebSocket = () => {
  socket.value = new WebSocket(`ws://localhost:8000/ws/${props.dwellerId}`)

  socket.value.onopen = () => {
    console.log('WebSocket connected')
  }

  socket.value.onmessage = (event) => {
    messages.value.push({ type: 'dweller', content: event.data })
  }

  socket.value.onerror = (error) => {
    console.error('WebSocket error:', error)
  }

  socket.value.onclose = () => {
    console.log('WebSocket disconnected')
    setTimeout(connectWebSocket, 5000) // Attempt to reconnect after 5 seconds
  }
}

const sendMessage = () => {
  if (socket.value && socket.value.readyState === WebSocket.OPEN && userMessage.value.trim()) {
    socket.value.send(userMessage.value)
    messages.value.push({ type: 'user', content: userMessage.value })
    userMessage.value = ''
  }
}

watchEffect(() => {
  if (chatMessages.value) {
    chatMessages.value.scrollTop = chatMessages.value.scrollHeight
  }
})

onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  if (socket.value) {
    socket.value.close()
  }
})
</script>

<template>
  <div class="chat-container">
    <div class="chat-messages" ref="chatMessages">
      <div v-for="(message, index) in messages" :key="index" :class="message.type">
        {{ message.content }}
      </div>
    </div>
    <div class="chat-input">
      <input v-model="userMessage" @keyup.enter="sendMessage" placeholder="Type your message..." />
      <button @click="sendMessage">Send</button>
    </div>
  </div>
</template>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.chat-messages {
  flex-grow: 1;
  overflow-y: auto;
  padding: 1rem;
}

.chat-input {
  display: flex;
  padding: 1rem;
}

.chat-input input {
  flex-grow: 1;
  margin-right: 1rem;
}

.user {
  text-align: right;
  color: blue;
}

.dweller {
  text-align: left;
  color: green;
}
</style>
