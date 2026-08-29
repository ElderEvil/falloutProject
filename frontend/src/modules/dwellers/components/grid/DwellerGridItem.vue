<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import DwellerStatusBadge from '../stats/DwellerStatusBadge.vue'
import DwellerAgeBadge from '../DwellerAgeBadge.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import type { DwellerShort } from '../../models/dweller'
import DwellerPortrait from '../DwellerPortrait.vue'
import DwellerIdentitySignal from '../DwellerIdentitySignal.vue'

interface RoomStat {
  icon: string
  label: string
  value: number
  isPower: boolean
}

interface Props {
  dweller: DwellerShort
  roomName?: string | null
  roomStat?: RoomStat | null
  generatingAI?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'generate-ai'): void
  (e: 'room-click'): void
}>()

const healthPercentage = computed(() => {
  if (!props.dweller.max_health) return 0
  return (props.dweller.health / props.dweller.max_health) * 100
})

// Room stat is passed precomputed from the list view (DwellersList.getRoomStat)
// so the grid and list render identical values (combat power for arena, else SPECIAL).

// Get color class based on stat value
const getStatColorClass = (value: number) => {
  if (value >= 7) return 'text-green-400'
  if (value >= 4) return 'text-yellow-400'
  return 'text-red-400'
}
</script>

<template>
  <div
    class="dweller-grid-item"
    role="button"
    tabindex="0"
    @click="emit('click')"
    @keydown.enter.prevent="emit('click')"
    @keydown.space.prevent="emit('click')"
  >
    <!-- Thumbnail / Avatar -->
    <div class="thumbnail-container">
      <template v-if="dweller.thumbnail_url">
        <DwellerPortrait
          :thumbnail-url="dweller.thumbnail_url"
          alt=""
          url-mode="static"
          image-class="thumbnail-image"
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
            aria-label="Generate AI portrait"
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
        <div class="header-badges">
          <DwellerIdentitySignal :visual-attributes="dweller.visual_attributes" compact />
          <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
          <DwellerStatusBadge :status="dweller.status" :show-label="false" size="small" />
        </div>
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

      <!-- Job-relevant stat (matches list view: combat power for arena, else SPECIAL) -->
      <div v-if="roomStat" class="job-stat">
        <Icon :icon="roomStat.icon" class="job-stat-icon" />
        <span class="job-stat-label">{{ roomStat.label }}:</span>
        <span class="job-stat-value" :class="roomStat.isPower ? 'text-orange-400' : getStatColorClass(roomStat.value)">
          {{ roomStat.value }}
        </span>
      </div>

      <!-- Room Badge -->
      <div class="room-info">
        <template v-if="roomName">
          <UTooltip :text="`Assigned to ${roomName}`" position="top">
            <button @click.stop="emit('room-click')" class="room-badge">
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
  background: var(--color-surface);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.dweller-grid-item:hover {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: translateY(-2px);
}

.thumbnail-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: var(--color-surface-sunken);
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
  background: var(--color-surface-sunken);
}

.placeholder-icon {
  width: 60%;
  height: 60%;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.ai-generate-button {
  position: absolute;
  bottom: 0.5rem;
  right: 0.5rem;
  background: var(--color-surface-raised);
  border: none;
  border-radius: 50%;
  padding: 0.5rem;
  cursor: pointer;
  transition: all 0.3s ease;
}

.ai-generate-button:hover:not(:disabled) {
  box-shadow: 0 0 20px var(--color-theme-primary);
  background: var(--color-surface-hover);
}

.ai-generate-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.ai-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--color-theme-primary);
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

.header-badges {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  flex-shrink: 0;
}

.dweller-name {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
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
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.stat-value {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.health-bar {
  width: 100%;
  height: 6px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 3px;
  overflow: hidden;
}

.health-fill {
  height: 100%;
  background: var(--color-theme-primary);
  box-shadow: 0 0 6px var(--color-theme-glow);
  transition: width 0.3s ease;
}

.job-stat {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.5rem;
  background: rgba(31, 41, 55, 0.6);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  font-size: 0.75rem;
}

.job-stat-icon {
  font-size: 1rem;
}

.job-stat-label {
  color: var(--color-theme-primary);
  opacity: 0.8;
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.job-stat-value {
  font-weight: 700;
  text-shadow: 0 0 4px var(--color-theme-glow);
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
  text-shadow: 0 0 2px var(--color-theme-glow);
  transition: all 0.2s ease;
  cursor: pointer;
}

.room-badge:hover:not(.unassigned) {
  border-color: var(--color-theme-glow);
  box-shadow: 0 0 8px var(--color-theme-glow);
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
