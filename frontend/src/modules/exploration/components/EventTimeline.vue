<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Exploration, ExplorationEvent } from '@/stores/exploration'
import type { Dweller } from '@/stores/dweller'

interface Props {
  exploration: Exploration
  dweller: Dweller | undefined
}

const props = defineProps<Props>()

const dwellerName = computed(() => {
  if (!props.dweller) return 'Unknown'
  return `${props.dweller.first_name} ${props.dweller.last_name}`
})

const events = computed(() => {
  if (!props.exploration.events || props.exploration.events.length === 0) {
    return []
  }
  // Show events in reverse chronological order (most recent first)
  return [...props.exploration.events].reverse()
})

const getEventIcon = (eventType: string): string => {
  const iconMap: Record<string, string> = {
    combat: 'mdi:sword-cross',
    loot: 'mdi:treasure-chest',
    exploration: 'mdi:map-marker',
    discovery: 'mdi:eye',
    encounter: 'mdi:account-alert',
    danger: 'mdi:alert',
    rest: 'mdi:sleep',
    default: 'mdi:circle-medium'
  }
  return iconMap[eventType] ?? iconMap.default!
}

const getEventColor = (eventType: string): string => {
  const colorMap: Record<string, string> = {
    combat: '#ff4444',
    loot: '#FFD700',
    exploration: 'var(--color-theme-primary)',
    discovery: '#4169E1',
    encounter: '#ff9900',
    danger: '#ff0000',
    rest: '#00ced1',
    default: 'var(--color-theme-primary)'
  }
  return colorMap[eventType] ?? colorMap.default!
}

const formatTime = (hours: number): string => {
  const h = Math.floor(hours)
  const m = Math.floor((hours - h) * 60)
  return `${h}h ${m}m`
}

const hasLoot = (event: ExplorationEvent): boolean => {
  return !!event.loot && (!!event.loot.item || !!event.loot.caps)
}

const getLootDisplay = (event: ExplorationEvent): string => {
  if (!event.loot) return ''
  const parts: string[] = []

  if (event.loot.item) {
    parts.push(`${event.loot.item.name} (${event.loot.item.rarity})`)
  }
  if (event.loot.caps) {
    parts.push(`${event.loot.caps} caps`)
  }

  return parts.join(' + ')
}
</script>

<template>
  <div class="event-timeline">
    <!-- Dweller Header -->
    <div class="timeline-dweller-header">
      <Icon icon="mdi:account" class="dweller-icon" />
      <div>
        <div class="dweller-name">{{ dwellerName }}</div>
        <div class="dweller-subtitle">Exploration Log</div>
      </div>
    </div>

    <!-- Timeline Content -->
    <div class="timeline-content">
      <!-- No Events State -->
      <div v-if="events.length === 0" class="no-events">
        <Icon icon="mdi:clock-outline" class="no-events-icon" />
        <p class="no-events-text">No events yet. Check back soon!</p>
      </div>

      <!-- Events List -->
      <div v-else class="events-list">
        <div
          v-for="(event, index) in events"
          :key="index"
          class="event-entry"
        >
          <!-- Timeline Dot -->
          <div class="timeline-marker">
            <div
              class="timeline-dot"
              :style="{ borderColor: getEventColor(event.type) }"
            >
              <Icon
                :icon="getEventIcon(event.type)"
                :style="{ color: getEventColor(event.type) }"
              />
            </div>
            <div v-if="index < events.length - 1" class="timeline-line"></div>
          </div>

          <!-- Event Content -->
          <div class="event-content">
            <div class="event-header">
              <span
                class="event-type"
                :style="{ color: getEventColor(event.type) }"
              >
                {{ event.type.toUpperCase() }}
              </span>
              <span class="event-time">{{ formatTime(event.time_elapsed_hours) }}</span>
            </div>

            <p class="event-description">{{ event.description }}</p>

            <!-- Loot Badge -->
            <div v-if="hasLoot(event)" class="loot-badge">
              <Icon icon="mdi:treasure-chest" class="loot-icon" />
              <span class="loot-text">{{ getLootDisplay(event) }}</span>
            </div>

            <!-- Timestamp -->
            <div class="event-timestamp">
              {{ new Date(event.timestamp).toLocaleTimeString() }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Summary Stats Footer -->
    <div class="timeline-footer">
      <div class="footer-stat">
        <Icon icon="mdi:file-document" class="footer-icon" />
        <span>{{ events.length }} events</span>
      </div>
      <div class="footer-stat">
        <Icon icon="mdi:map-marker-distance" class="footer-icon" />
        <span>{{ exploration.total_distance }} mi</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.event-timeline {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.timeline-dweller-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.05);
  border-bottom: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.dweller-icon {
  width: 2rem;
  height: 2rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
}

.dweller-name {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.dweller-subtitle {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.6);
}

.timeline-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

/* Custom Scrollbar */
.timeline-content::-webkit-scrollbar {
  width: 6px;
}

.timeline-content::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
}

.timeline-content::-webkit-scrollbar-thumb {
  background: var(--color-theme-primary);
  border-radius: 3px;
}

.timeline-content::-webkit-scrollbar-thumb:hover {
  background: var(--color-theme-accent);
}

.no-events {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1rem;
  text-align: center;
}

.no-events-icon {
  width: 3rem;
  height: 3rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.no-events-text {
  font-size: 0.875rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.5);
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-entry {
  display: flex;
  gap: 1rem;
}

.timeline-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.timeline-dot {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  border: 2px solid;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  box-shadow: 0 0 10px currentColor;
  z-index: 1;
}

.timeline-line {
  width: 2px;
  flex: 1;
  min-height: 30px;
  background: linear-gradient(
    to bottom,
    rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3),
    rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1)
  );
  margin: 0.25rem 0;
}

.event-content {
  flex: 1;
  padding: 0.75rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.03);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border-radius: 6px;
  margin-bottom: 0.5rem;
}

.event-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.event-type {
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.1em;
}

.event-time {
  font-size: 0.625rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.6);
}

.event-description {
  font-size: 0.875rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.9);
  line-height: 1.4;
  margin-bottom: 0.5rem;
}

.loot-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.5rem;
  background: rgba(255, 215, 0, 0.1);
  border: 1px solid rgba(255, 215, 0, 0.3);
  border-radius: 4px;
  font-size: 0.75rem;
  color: #FFD700;
  margin-bottom: 0.5rem;
}

.loot-icon {
  width: 0.875rem;
  height: 0.875rem;
}

.loot-text {
  font-weight: 600;
}

.event-timestamp {
  font-size: 0.625rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.5);
  text-align: right;
}

.timeline-footer {
  display: flex;
  justify-content: space-around;
  padding: 0.75rem;
  border-top: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  background: rgba(0, 0, 0, 0.5);
}

.footer-stat {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.8);
}

.footer-icon {
  width: 1rem;
  height: 1rem;
  color: var(--color-theme-primary);
}
</style>
