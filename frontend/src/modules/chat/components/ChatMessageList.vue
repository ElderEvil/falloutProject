<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { normalizeImageUrl } from '@/core/utils/image'
import type { ActionSuggestion, ChatMessageDisplay } from '../models/chat'

defineProps<{
  messages: ChatMessageDisplay[]
  dwellerName: string
  username: string
  dwellerAvatarUrl: string | null
  isTyping: boolean
  currentlyPlayingUrl: string | null
  latestActionSuggestionIndex: number
  isPerformingAction: boolean
  getHappinessColor: (delta: number) => string
  getHappinessIcon: (delta: number) => string
}>()

const emit = defineEmits<{
  playAudio: [url: string]
  stopAudio: []
  confirmAction: [action: ActionSuggestion, index: number]
  dismissAction: [index: number]
}>()
</script>

<template>
  <div
    v-for="(message, index) in messages"
    :key="message.messageId ?? index"
    class="message-wrapper"
    :class="message.type"
  >
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

    <div class="message-bubble">
      <div class="message-header">
        <span class="message-sender">
          <span class="terminal-prefix">{{ message.type === 'user' ? '>' : '<' }}</span>
          {{ message.type === 'user' ? username : dwellerName }}
        </span>
        <div class="flex items-center gap-2">
          <span
            v-if="message.type === 'dweller' && message.happinessImpact"
            class="happiness-indicator"
            :class="getHappinessColor(message.happinessImpact.delta)"
            :title="message.happinessImpact.reason_text"
          >
            <Icon :icon="getHappinessIcon(message.happinessImpact.delta)" class="h-4 w-4" />
            <span class="text-xs">
              {{ message.happinessImpact.delta > 0 ? '+' : '' }}{{ message.happinessImpact.delta }}
            </span>
          </span>
          <button
            v-if="message.audioUrl"
            class="audio-replay-btn"
            :class="{ 'is-playing': currentlyPlayingUrl === message.audioUrl }"
            :title="
              currentlyPlayingUrl === message.audioUrl
                ? 'Stop audio'
                : `Play ${message.type === 'user' ? 'your' : 'dweller'} audio`
            "
            @click="
              currentlyPlayingUrl === message.audioUrl
                ? emit('stopAudio')
                : emit('playAudio', message.audioUrl)
            "
          >
            <Icon
              :icon="currentlyPlayingUrl === message.audioUrl ? 'mdi:stop' : 'mdi:volume-high'"
              class="h-4 w-4"
            />
          </button>
        </div>
      </div>
      <div class="message-content">{{ message.content }}</div>

      <div
        v-if="
          message.type === 'dweller' &&
          message.actionSuggestion &&
          message.actionSuggestion.action_type !== 'no_action' &&
          index === latestActionSuggestionIndex
        "
        class="action-suggestion-card"
      >
        <div class="action-suggestion-header">
          <Icon
            :icon="
              message.actionSuggestion.action_type === 'assign_to_room'
                ? 'mdi:door-open'
                : message.actionSuggestion.action_type === 'start_training'
                  ? 'mdi:dumbbell'
                  : message.actionSuggestion.action_type === 'start_exploration'
                    ? 'mdi:map-marker-radius'
                    : 'mdi:arrow-u-left-top'
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
                : message.actionSuggestion.action_type === 'start_training'
                  ? `Train ${message.actionSuggestion.stat}`
                  : message.actionSuggestion.action_type === 'start_exploration'
                    ? `Explore wasteland for ${message.actionSuggestion.duration_hours}h`
                    : 'Recall from wasteland'
            }}
          </p>
          <p class="action-suggestion-reason">{{ message.actionSuggestion.reason }}</p>
        </div>
        <div class="action-suggestion-actions">
          <button
            class="action-confirm-btn"
            :disabled="isPerformingAction"
            @click="emit('confirmAction', message.actionSuggestion, index)"
          >
            <Icon v-if="isPerformingAction" icon="mdi:loading" class="h-4 w-4 spinning" />
            <Icon v-else icon="mdi:check" class="h-4 w-4" />
            <span>{{ isPerformingAction ? 'Processing...' : 'Confirm' }}</span>
          </button>
          <button class="action-dismiss-btn" @click="emit('dismissAction', index)">
            <Icon icon="mdi:close" class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  </div>

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
</template>
