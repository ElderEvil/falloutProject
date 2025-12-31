<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import DwellerStatusBadge from './DwellerStatusBadge.vue'
import UTooltip from '@/components/ui/UTooltip.vue'
import type { DwellerShort } from '@/models/dweller'

interface Props {
  dweller: DwellerShort
  roomName?: string | null
  generatingAI?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'generate-ai'): void
  (e: 'room-click'): void
}>()

const getImageUrl = (imagePath: string) => {
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}

const healthPercentage = computed(() => {
  if (!props.dweller.max_health) return 0
  return (props.dweller.health / props.dweller.max_health) * 100
})
</script>

<template>
  <div class="dweller-grid-item" @click="emit('click')">
    <!-- Thumbnail / Avatar -->
    <div class="thumbnail-container">
      <template v-if="dweller.thumbnail_url">
        <img
          :src="getImageUrl(dweller.thumbnail_url)"
          alt="Dweller Thumbnail"
          class="thumbnail-image"
        />
      </template>
      <template v-else>
        <div class="thumbnail-placeholder">
          <Icon icon="mdi:account-circle" class="placeholder-icon" />
        </div>

        <!-- Generate AI Button -->
        <UTooltip text="Generate AI portrait" position="top">
          <button
            @click.stop="emit('generate-ai')"
            class="ai-generate-button"
            :disabled="generatingAI"
          >
            <Icon
              :icon="generatingAI ? 'mdi:loading' : 'mdi:sparkles'"
              class="ai-icon"
              :class="{ 'animate-spin': generatingAI }"
            />
          </button>
        </UTooltip>
      </template>
    </div>

    <!-- Info Section -->
    <div class="info-section">
      <!-- Name & Status -->
      <div class="header">
        <h3 class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</h3>
        <DwellerStatusBadge :status="dweller.status" :show-label="false" size="small" />
      </div>

      <!-- Stats -->
      <div class="stats">
        <div class="stat-item">
          <span class="stat-label">Lvl</span>
          <span class="stat-value">{{ dweller.level }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">HP</span>
          <span class="stat-value">{{ dweller.health }}/{{ dweller.max_health }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">😊</span>
          <span class="stat-value">{{ dweller.happiness }}%</span>
        </div>
      </div>

      <!-- Health Bar -->
      <div class="health-bar">
        <div class="health-fill" :style="{ width: `${healthPercentage}%` }"></div>
      </div>

      <!-- Room Badge -->
      <div class="room-info">
        <template v-if="roomName">
          <UTooltip :text="`Assigned to ${roomName}`" position="top">
            <button
              @click.stop="emit('room-click')"
              class="room-badge"
            >
              <Icon icon="mdi:office-building" class="room-icon" />
              <span class="room-name">{{ roomName }}</span>
            </button>
          </UTooltip>
        </template>
        <template v-else>
          <div class="room-badge unassigned">
            <Icon icon="mdi:account-off" class="room-icon" />
            <span class="room-name">Unassigned</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dweller-grid-item {
  display: flex;
  flex-direction: column;
  background: rgba(31, 41, 55, 0.8);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.1);
}

.dweller-grid-item:hover {
  border-color: rgba(0, 255, 0, 0.5);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
  transform: translateY(-2px);
}

.thumbnail-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: rgba(0, 0, 0, 0.3);
}

.thumbnail-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.5);
}

.placeholder-icon {
  width: 60%;
  height: 60%;
  color: rgba(156, 163, 175, 0.5);
}

.ai-generate-button {
  position: absolute;
  bottom: 0.5rem;
  right: 0.5rem;
  background: rgba(31, 41, 55, 0.9);
  border: none;
  border-radius: 50%;
  padding: 0.5rem;
  cursor: pointer;
  transition: all 0.3s ease;
  animation: pulse-glow 2s ease-in-out infinite;
}

.ai-generate-button:hover:not(:disabled) {
  animation: none;
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.9);
  background: rgba(31, 41, 55, 1);
}

.ai-generate-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.ai-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: #00ff00;
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 5px rgba(0, 255, 0, 0.4);
  }
  50% {
    box-shadow: 0 0 15px rgba(0, 255, 0, 0.7);
  }
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.875rem;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}

.dweller-name {
  font-size: 1rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.5);
  line-height: 1.2;
  flex: 1;
}

.stats {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.125rem;
}

.stat-label {
  font-size: 0.75rem;
  color: rgba(0, 255, 0, 0.7);
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
}

.stat-value {
  font-size: 0.875rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 4px rgba(0, 255, 0, 0.5);
}

.health-bar {
  width: 100%;
  height: 6px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid rgba(0, 255, 0, 0.3);
  border-radius: 3px;
  overflow: hidden;
}

.health-fill {
  height: 100%;
  background: linear-gradient(90deg, #00ff00 0%, #00cc00 100%);
  box-shadow: 0 0 6px rgba(0, 255, 0, 0.6);
  transition: width 0.3s ease;
}

.room-info {
  display: flex;
}

.room-badge {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.625rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  background: rgba(31, 41, 55, 0.8);
  border: 1px solid rgba(107, 114, 128, 0.5);
  color: rgba(209, 213, 219, 0.9);
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.2);
  transition: all 0.2s ease;
  cursor: pointer;
}

.room-badge:hover:not(.unassigned) {
  border-color: rgba(0, 255, 0, 0.4);
  box-shadow: 0 0 8px rgba(0, 255, 0, 0.3);
}

.room-badge.unassigned {
  background: rgba(31, 41, 55, 0.5);
  border-color: rgba(107, 114, 128, 0.3);
  color: rgba(156, 163, 175, 0.7);
  cursor: default;
}

.room-icon {
  width: 0.875rem;
  height: 0.875rem;
}

.room-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
