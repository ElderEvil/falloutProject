<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import RoomDwellers from '@/modules/dwellers/components/RoomDwellers.vue'
import type { Incident } from '@/modules/combat/models/incident'
import { IncidentType } from '@/modules/combat/models/incident'
import type { Room } from '../models/room'
import { API_BASE_URL } from '@/core/config/api'

interface Props {
  room: Room
  showRoomImages: boolean
  isPowerOutage: boolean
  selected: boolean
  isDraggingOver: boolean
  highlighted: boolean
  incident?: Incident | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  click: [room: Room, event: MouseEvent]
  upgrade: [roomId: string, event: MouseEvent]
  destroy: [roomId: string, event: MouseEvent]
  'incident-click': [incidentId: string]
  dragover: [event: DragEvent, roomId: string]
  dragleave: []
  drop: [event: DragEvent, roomId: string]
}>()

// Styles for grid placement
const gridStyle = computed(() => {
  const col = (props.room.coordinate_x ?? 0) + 1
  const span = props.room.size === 1 ? 1 : Math.ceil((props.room.size || props.room.size_min) / 3)
  return {
    gridRow: (props.room.coordinate_y ?? 0) + 1,
    gridColumn: `${col} / span ${span}`,
  }
})

// Template-bound helpers
const getRoomImageUrl = (r: Room): string | null => {
  if (!r.image_url) return null
  return `${API_BASE_URL}${r.image_url}`
}

const isRoomAffectedByOutage = (): boolean => {
  if (!props.isPowerOutage) return false
  return props.room.ability?.toLowerCase() !== 'strength'
}

const getAbilityLetter = (ability: string | null | undefined): string => {
  if (!ability) return ''
  const abilityMap: Record<string, string> = {
    strength: 'S',
    perception: 'P',
    endurance: 'E',
    charisma: 'C',
    intelligence: 'I',
    agility: 'A',
    luck: 'L',
  }
  return abilityMap[ability.toLowerCase()] || ''
}

const getAbilityIcon = (ability: string | null | undefined): string => {
  if (!ability) return 'mdi:home'
  const iconMap: Record<string, string> = {
    strength: 'mdi:lightning-bolt',
    perception: 'mdi:water',
    agility: 'mdi:food-drumstick',
    endurance: 'mdi:flash',
    charisma: 'mdi:account-voice',
    intelligence: 'mdi:brain',
    luck: 'mdi:clover',
  }
  return iconMap[ability.toLowerCase()] || 'mdi:home'
}

const canUpgrade = (r: Room): boolean => {
  const maxTier = r.t2_upgrade_cost && r.t3_upgrade_cost ? 3 : r.t2_upgrade_cost ? 2 : 1
  return r.tier < maxTier
}

const getUpgradeCost = (r: Room): number => {
  if (r.tier === 1 && r.t2_upgrade_cost) return r.t2_upgrade_cost
  if (r.tier === 2 && r.t3_upgrade_cost) return r.t3_upgrade_cost
  return 0
}

const getIncidentIcon = (type: IncidentType): string => {
  switch (type) {
    case IncidentType.RAIDER_ATTACK:
      return 'mdi:skull'
    case IncidentType.RADROACH_INFESTATION:
      return 'mdi:bug'
    case IncidentType.FIRE:
      return 'mdi:fire'
    case IncidentType.MOLE_RAT_ATTACK:
      return 'mdi:paw'
    case IncidentType.DEATHCLAW_ATTACK:
      return 'mdi:claw-mark'
    case IncidentType.RADIATION_LEAK:
      return 'mdi:radioactive'
    case IncidentType.ELECTRICAL_FAILURE:
      return 'mdi:lightning-bolt'
    case IncidentType.WATER_CONTAMINATION:
      return 'mdi:water-alert'
    default:
      return 'mdi:alert-octagon'
  }
}

const handleIncidentClick = (event: MouseEvent) => {
  if (props.incident) {
    event.stopPropagation()
    emit('incident-click', props.incident.id)
  }
}
</script>

<template>
  <div
    :style="gridStyle"
    class="room built-room"
    :class="{
      selected,
      'drag-over': isDraggingOver,
      'has-incident': !!incident,
      highlighted,
      'power-outage': isRoomAffectedByOutage(),
    }"
    draggable="false"
    role="button"
    tabindex="0"
    @click="emit('click', room, $event)"
    @keydown.enter.prevent="emit('click', room, $event)"
    @keydown.space.prevent="emit('click', room, $event)"
    @dragover="emit('dragover', $event, room.id)"
    @dragleave="emit('dragleave')"
    @drop="emit('drop', $event, room.id)"
  >
    <div class="room-content">
      <!-- Room Image (toggleable) -->
      <img
        v-if="showRoomImages && getRoomImageUrl(room)"
        :src="getRoomImageUrl(room)"
        :alt="room.name"
        class="room-background-image"
        draggable="false"
      />
      <div class="room-info-overlay">
        <div class="room-header">
          <h3 class="room-name">
            {{ room.name }}
            <span v-if="room.ability" class="ability-letter"
              >({{ getAbilityLetter(room.ability) }})</span
            >
          </h3>
          <Icon v-if="room.ability" :icon="getAbilityIcon(room.ability)" class="ability-icon" />
        </div>
        <p class="room-category">{{ room.category }}</p>
        <div v-if="room.tier" class="room-tier">Tier {{ room.tier }}</div>
      </div>
      <div v-if="isDraggingOver" class="drop-indicator">
        <Icon icon="mdi:account-plus" class="h-6 w-6" />
        <span>Drop to assign</span>
      </div>
      <div v-if="selected" class="room-actions">
        <button
          v-if="canUpgrade(room)"
          @click="emit('upgrade', room.id, $event)"
          class="upgrade-button"
          :title="`Upgrade to Tier ${room.tier + 1} (${getUpgradeCost(room)} caps)`"
        >
          <Icon icon="mdi:arrow-up-circle" class="h-5 w-5" />
          <span class="upgrade-cost">{{ getUpgradeCost(room) }}</span>
        </button>
        <button
          @click="emit('destroy', room.id, $event)"
          class="destroy-button"
          aria-label="Destroy room"
          title="Destroy Room"
        >
          <Icon icon="mdi:delete" class="h-5 w-5" />
        </button>
      </div>

      <!-- Display dwellers in room -->
      <div class="room-dwellers-container">
        <RoomDwellers :roomId="room.id" />
      </div>

      <!-- Incident overlay -->
      <div
        v-if="incident"
        class="incident-overlay"
        role="button"
        tabindex="0"
        @click="handleIncidentClick"
        @keydown.enter.prevent="handleIncidentClick"
        @keydown.space.prevent="handleIncidentClick"
      >
        <Icon :icon="getIncidentIcon(incident.type)" class="incident-icon" />
        <div class="incident-label">ALERT</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.built-room {
  z-index: 2;
}

.room-content {
  padding: 0;
  text-align: center;
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 100%;
  overflow: hidden;
  background: linear-gradient(135deg, rgba(50, 50, 50, 0.9), rgba(30, 30, 30, 0.9));
}

.room-background-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: 0;
  pointer-events: none;
  -webkit-user-drag: none;
}

.room-info-overlay {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  background: rgba(0, 0, 0, 0.85);
  padding: 2px 6px;
  border-radius: 0 0 4px 4px;
  backdrop-filter: blur(3px);
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: auto;
}

.room-name {
  font-size: 0.75em;
  margin-bottom: 2px;
  color: var(--color-theme-primary);
  font-weight: 600;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.8);
}

.room-category {
  font-size: 0.65em;
  color: var(--color-gray-200);
  font-weight: 500;
  text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.8);
}

.room-tier {
  font-size: 0.6em;
  color: var(--color-warning);
  margin-top: 1px;
  font-weight: 600;
  text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.8);
}

.room-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.ability-letter {
  color: var(--color-theme-primary);
  font-weight: 700;
  margin-left: 2px;
}

.ability-icon {
  width: 16px;
  height: 16px;
  color: var(--color-theme-primary);
  flex-shrink: 0;
}

.room-dwellers-container {
  position: relative;
  margin-top: auto;
  padding: 5px;
  z-index: 3;
}

.drop-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: bold;
  pointer-events: none;
  z-index: 10;
}

.room-actions {
  position: absolute;
  top: 5px;
  right: 5px;
  display: flex;
  gap: 8px;
  align-items: center;
  z-index: 5;
}

.upgrade-button {
  background: none;
  border: 1px solid var(--color-warning);
  border-radius: 4px;
  cursor: pointer;
  color: var(--color-warning);
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  transition: all 0.2s;
}

.upgrade-button:hover {
  background: rgba(251, 191, 36, 0.1);
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
}

.upgrade-cost {
  font-weight: bold;
}

.destroy-button {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--color-danger);
  padding: 4px;
  transition: all 0.2s;
}

.destroy-button:hover {
  color: var(--color-danger);
  transform: scale(1.1);
}

.incident-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  cursor: pointer;
  z-index: 20;
  transition: background 0.3s ease;
}

.incident-overlay:hover {
  background: rgba(255, 0, 0, 0.25);
}

.incident-icon {
  width: 48px;
  height: 48px;
  color: var(--color-danger);
  filter: drop-shadow(0 0 8px rgba(255, 51, 51, 0.8));
  animation: incident-shake 0.5s ease-in-out infinite;
}

@keyframes incident-shake {
  0%,
  100% {
    transform: translate(0, 0) rotate(0deg);
  }
  25% {
    transform: translate(-2px, 0) rotate(-2deg);
  }
  75% {
    transform: translate(2px, 0) rotate(2deg);
  }
}

.incident-label {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-danger);
  letter-spacing: 0.1em;
  text-shadow: 0 0 8px rgba(255, 51, 51, 0.8);
}

/* Power outage child overrides */
.room.power-outage .room-name,
.room.power-outage .room-category {
  color: var(--color-gray-500);
}
</style>
