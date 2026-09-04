<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { UButton } from '@/core/components/ui'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerPlacesBadge from '@/modules/dwellers/components/DwellerPlacesBadge.vue'
import type { ActionSuggestion, ChatMessageDisplay, MapDiscovery } from '../models/chat'
import type { MapPlaceLink } from '@/modules/dwellers/models/dweller'

defineProps<{
  messages: ChatMessageDisplay[]
  vaultId?: string | null
  placeLinks?: MapPlaceLink[]
  dwellerName: string
  username: string
  dwellerAvatarUrl: string | null
  userAvatarUrl: string | null
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
  retryMessage: [index: number]
}>()

const mapDiscoveryTitle = (places: MapDiscovery[]) =>
  `Map intel: ${places.map((place) => place.name).join(', ')} unlocked`

const mapPlaceHref = (vaultId: string | null | undefined, locationId: string) =>
  vaultId ? `/vault/${vaultId}/map?place=${locationId}` : undefined

const actionIcon = (action: ActionSuggestion) => {
  switch (action.action_type) {
    case 'assign_to_room':
      return 'mdi:door-open'
    case 'start_training':
      return 'mdi:dumbbell'
    case 'start_exploration':
      return 'mdi:map-marker-radius'
    case 'recall_exploration':
      return 'mdi:arrow-u-left-top'
    case 'request_stimpak':
      return 'mdi:medical-bag'
    case 'request_radaway':
      return 'mdi:radiation'
    case 'no_action':
      return 'mdi:help-circle-outline'
  }
}

const actionLabel = (action: ActionSuggestion) => {
  switch (action.action_type) {
    case 'assign_to_room':
      return `Assign to ${action.room_name}`
    case 'start_training':
      return `Train ${action.stat}`
    case 'start_exploration':
      return `Explore wasteland for ${action.duration_hours}h`
    case 'recall_exploration':
      return 'Recall from wasteland'
    case 'request_stimpak':
      return 'Give Stimpak'
    case 'request_radaway':
      return 'Give RadAway'
    case 'no_action':
      return 'No action'
  }
}

const actionConfirmLabel = (action: ActionSuggestion, isPerformingAction: boolean) =>
  isPerformingAction
    ? 'Processing...'
    : action.action_type === 'request_stimpak'
      ? 'Give Stimpak'
      : action.action_type === 'request_radaway'
        ? 'Give RadAway'
        : 'Confirm'

const messageContentSegments = (
  content: string,
  type: ChatMessageDisplay['type'],
  placeLinks: MapPlaceLink[] | undefined
) => {
  if (type !== 'dweller' || !placeLinks?.length) return [{ text: content }]

  const lookup = new Map(placeLinks.map((place) => [place.name.toLowerCase(), place.locationId]))
  const pattern = [...placeLinks]
    .sort((a, b) => b.name.length - a.name.length)
    .map((place) => place.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')
  const matches = [...content.matchAll(new RegExp(pattern, 'gi'))]
  if (!matches.length) return [{ text: content }]

  const segments: { text: string; locationId?: string }[] = []
  let cursor = 0
  for (const match of matches) {
    const index = match.index ?? 0
    if (index > cursor) segments.push({ text: content.slice(cursor, index) })
    segments.push({ text: match[0], locationId: lookup.get(match[0].toLowerCase()) })
    cursor = index + match[0].length
  }
  if (cursor < content.length) segments.push({ text: content.slice(cursor) })
  return segments
}
</script>

<template>
  <div
    v-for="(message, index) in messages"
    :key="message.messageId ?? index"
    class="message-wrapper"
    :class="message.type"
  >
    <div class="message-avatar">
      <DwellerPortrait
        v-if="message.type === 'dweller'"
        :thumbnail-url="dwellerAvatarUrl"
        :alt="dwellerName"
        image-class="avatar-image"
        fallback-class="avatar-icon"
      />
      <DwellerPortrait
        v-else
        :image-url="userAvatarUrl"
        :alt="username"
        image-class="avatar-image"
        fallback-class="avatar-icon"
        fallback-icon="mdi:account-circle"
      />
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
          <DwellerPlacesBadge
            v-if="message.type === 'dweller' && message.unlockedPlaces?.length"
            class="map-discovery-indicator happiness-indicator text-theme-primary"
            :count="message.unlockedPlaces.length"
            :title="mapDiscoveryTitle(message.unlockedPlaces)"
          />
          <button
            v-if="message.audioUrl"
            class="audio-replay-btn"
            :class="{ 'is-playing': currentlyPlayingUrl === message.audioUrl }"
            :title="
              currentlyPlayingUrl === message.audioUrl
                ? 'Stop audio'
                : `Play ${message.type === 'user' ? 'your' : 'dweller'} audio`
            "
            :aria-label="
              currentlyPlayingUrl === message.audioUrl
                ? 'Stop audio playback'
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
      <div class="message-content">
        <template v-for="(segment, segmentIndex) in messageContentSegments(message.content, message.type, placeLinks)" :key="segmentIndex">
          <a
            v-if="segment.locationId && vaultId"
            class="chat-place-link"
            :href="mapPlaceHref(vaultId, segment.locationId)"
          >{{ segment.text }}</a>
          <span v-else>{{ segment.text }}</span>
        </template>
      </div>

      <div
        v-if="message.type === 'dweller' && message.unlockedPlaces?.length"
        class="map-discovery-links"
      >
        <Icon icon="mdi:map-outline" class="h-4 w-4 shrink-0" />
        <span class="map-discovery-label">Map intel:</span>
        <template v-for="(place, placeIndex) in message.unlockedPlaces" :key="place.locationId">
          <span v-if="placeIndex" aria-hidden="true">·</span>
          <a
            v-if="vaultId"
            class="map-discovery-link"
            :href="mapPlaceHref(vaultId, place.locationId)"
          >{{ place.name }}</a>
          <span v-else>{{ place.name }}</span>
        </template>
      </div>

      <div v-if="message.error" class="message-error" role="alert" aria-live="polite">
        <Icon icon="mdi:alert-circle-outline" class="message-error-icon" />
        <span>{{ message.error }}</span>
        <UButton
          v-if="message.type === 'user'"
          variant="ghost"
          size="xs"
          @click="emit('retryMessage', index)"
        >
          Retry
        </UButton>
      </div>

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
            :icon="actionIcon(message.actionSuggestion)"
            class="h-4 w-4"
          />
          <span class="text-xs font-bold uppercase tracking-wider">Suggested Action</span>
        </div>
        <div class="action-suggestion-body">
          <p class="action-suggestion-text">
            {{ actionLabel(message.actionSuggestion) }}
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
            <span>{{ actionConfirmLabel(message.actionSuggestion, isPerformingAction) }}</span>
          </button>
          <button class="action-dismiss-btn" aria-label="Dismiss suggested action" @click="emit('dismissAction', index)">
            <Icon icon="mdi:close" class="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  </div>

  <div v-if="isTyping" class="typing-wrapper dweller">
    <div class="message-avatar">
      <DwellerPortrait
        :thumbnail-url="dwellerAvatarUrl"
        :alt="dwellerName"
        image-class="avatar-image"
        fallback-class="avatar-icon"
      />
    </div>
    <div class="typing-indicator">
      <span class="terminal-cursor">_</span>
      {{ dwellerName }} is typing...
    </div>
  </div>
</template>
