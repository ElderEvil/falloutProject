<template>
  <div
    class="incident-alert"
    :class="{ pulsing: hasActiveIncidents }"
    @click="incidents[0]?.id && $emit('click', incidents[0].id)"
  >
    <div class="alert-content">
      <!-- Icon -->
      <div class="alert-icon">
        <Icon :icon="incidentIcon" class="icon" />
      </div>

      <!-- Incident Info -->
      <div class="alert-info">
        <div class="alert-title">
          {{ incidentTitle }}
        </div>
        <div class="alert-subtitle">
          {{ incidentSubtitle }}
        </div>
      </div>

      <!-- Timer -->
      <div class="alert-timer">
        {{ elapsedTime }}
      </div>

      <!-- Count Badge (if multiple) -->
      <div v-if="incidents.length > 1" class="alert-badge">{{ incidents.length }} ACTIVE</div>
    </div>

    <!-- Scanline overlay -->
    <div class="scanline"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import type { Incident } from '../../models/incident'
import { IncidentType } from '../../models/incident'

interface Props {
  incidents: Incident[]
}

const props = defineProps<Props>()

defineEmits<{
  click: [incidentId: string]
}>()

// Timer for elapsed time updates
const currentTime = ref(Date.now())
let timer: number | null = null

onMounted(() => {
  timer = window.setInterval(() => {
    currentTime.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

// Computed
const hasActiveIncidents = computed(() => props.incidents.length > 0)

const primaryIncident = computed(() => props.incidents[0])

const incidentIcon = computed(() => {
  if (!primaryIncident.value) return 'mdi:alert-octagon'

  switch (primaryIncident.value.type) {
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
})

const incidentTitle = computed(() => {
  if (!primaryIncident.value) return 'INCIDENT ALERT'

  return primaryIncident.value.type.replace(/_/g, ' ').toUpperCase()
})

const incidentSubtitle = computed(() => {
  if (!primaryIncident.value) return ''

  const difficulty = primaryIncident.value.difficulty
  const stars = '★'.repeat(difficulty)

  return `DIFFICULTY: ${stars} (${difficulty}/10)`
})

const elapsedTime = computed(() => {
  if (!primaryIncident.value) return '00:00'

  // Parse as UTC by appending 'Z' if not present, or replace space with 'T' for ISO format
  let startTimeStr = primaryIncident.value.start_time
  if (!startTimeStr.endsWith('Z')) {
    // Convert "2026-07-05 16:58:7" to "2026-07-05T16:58:07Z" (UTC)
    startTimeStr = startTimeStr.replace(' ', 'T') + 'Z'
  }
  const startTime = new Date(startTimeStr).getTime()
  const elapsed = Math.floor((currentTime.value - startTime) / 1000)

  const minutes = Math.floor(elapsed / 60)
  const seconds = elapsed % 60

  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})
</script>

<style scoped>
.incident-alert {
  position: relative;
  width: 100%;
  height: 60px;
  background: linear-gradient(180deg, var(--color-surface-dark) 0%, var(--color-surface-dark) 100%);
  border: 2px solid var(--color-danger);
  border-radius: 4px;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.3s ease;
}

.incident-alert:hover {
  border-color: var(--color-danger);
  box-shadow: 0 0 20px color-mix(in srgb, var(--color-danger) 50%, transparent);
}

.incident-alert.pulsing {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    border-color: var(--color-danger);
    box-shadow: 0 0 10px color-mix(in srgb, var(--color-danger) 30%, transparent);
  }
  50% {
    border-color: var(--color-danger);
    box-shadow: 0 0 30px color-mix(in srgb, var(--color-danger) 60%, transparent);
  }
}

.alert-content {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 1rem;
  gap: 1rem;
}

.alert-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-danger) 20%, transparent);
  border: 1px solid var(--color-danger);
  border-radius: 50%;
}

.alert-icon .icon {
  width: 24px;
  height: 24px;
  color: var(--color-danger);
}

.alert-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.alert-title {
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  font-weight: bold;
  color: var(--color-danger);
  letter-spacing: 0.05em;
}

.alert-subtitle {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--color-danger);
}

.alert-timer {
  flex-shrink: 0;
  font-family: 'Courier New', monospace;
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-danger);
  letter-spacing: 0.1em;
}

.alert-badge {
  flex-shrink: 0;
  padding: 0.25rem 0.75rem;
  background: var(--color-danger);
  color: var(--color-gray-100);
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  font-weight: bold;
  border-radius: 12px;
  letter-spacing: 0.05em;
}

.scanline {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 4px;
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--color-danger) 80%, transparent),
    transparent
  );
  animation: scanline 2s linear infinite;
  pointer-events: none;
  z-index: 3;
}

@keyframes scanline {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(60px);
  }
}
</style>
