<script setup lang="ts">
import { ref } from 'vue'
import { NModal, NInput, NButton, NScrollbar } from 'naive-ui'
import type { Dweller } from '../types/vault'
import { getDwellerFullName } from '../utils/dwellerUtils'

const props = defineProps<{
  modelValue: boolean
  dweller: Dweller
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const message = ref('')
const chatHistory = ref([
  { sender: 'system', text: 'ESTABLISHING COMMUNICATION LINK...' },
  { sender: 'system', text: 'CONNECTION ESTABLISHED' },
  { sender: getDwellerFullName(props.dweller), text: 'How may I be of assistance, Overseer?' }
])

const sendMessage = () => {
  if (!message.value.trim()) return

  chatHistory.value.push({ sender: 'Overseer', text: message.value })
  message.value = ''

  // Simulate dweller response
  setTimeout(() => {
    chatHistory.value.push({
      sender: getDwellerFullName(props.dweller),
      text: `I understand, Overseer. I'll continue my duties as assigned.`
    })
  }, 1000)
}
</script>

<template>
  <NModal
    :show="modelValue"
    @update:show="(value) => emit('update:modelValue', value)"
    preset="card"
    style="width: 500px"
    :title="`COMM LINK: ${getDwellerFullName(dweller).toUpperCase()}`"
    :bordered="false"
    class="chat-modal"
  >
    <div class="chat-container">
      <NScrollbar class="chat-history" trigger="none">
        <div
          v-for="(msg, index) in chatHistory"
          :key="index"
          :class="['message', msg.sender.toLowerCase()]"
        >
          <span class="sender">[{{ msg.sender.toUpperCase() }}]:</span>
          <span class="text">{{ msg.text }}</span>
        </div>
      </NScrollbar>

      <div class="chat-input">
        <NInput
          v-model:value="message"
          type="text"
          placeholder="ENTER MESSAGE"
          @keyup.enter="sendMessage"
        />
        <NButton @click="sendMessage">SEND</NButton>
      </div>
    </div>
  </NModal>
</template>

<style scoped>
.chat-modal {
  background: var(--theme-background);
  border: 2px solid var(--theme-border);
  box-shadow: var(--theme-modal-shadow);
}

.chat-modal :deep(.n-modal) {
  background: var(--theme-background);
}

.chat-modal :deep(.n-card) {
  background: var(--theme-background);
  border: 2px solid var(--theme-border);
}

.chat-modal :deep(.n-card-header) {
  border-bottom: 1px solid var(--theme-border);
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 400px;
  font-family: 'Courier New', Courier, monospace;
}

.chat-history {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.message {
  display: flex;
  gap: 8px;
  line-height: 1.4;
}

.message.system {
  color: var(--theme-text-secondary);
  font-style: italic;
}

.sender {
  color: var(--theme-text);
  white-space: nowrap;
  text-shadow: 0 0 8px var(--theme-shadow);
}

.text {
  word-break: break-word;
  color: var(--theme-text);
}

.chat-input {
  display: flex;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid var(--theme-border);
}

.chat-input :deep(.n-input) {
  flex: 1;
}

:deep(.n-scrollbar-rail) {
  background-color: var(--theme-background) !important;
}

:deep(.n-scrollbar-content) {
  background-color: var(--theme-background) !important;
}
</style>
