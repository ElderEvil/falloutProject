<template>
  <div
    class="incident-alert"
    :class="{ pulsing: hasActiveIncidents }"
    @click="$emit('click', incidents[0]?.id)"
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
      <div v-if="incidents.length > 1" class="alert-badge">
        {{ incidents.length }} ACTIVE
      </div>
    </div>

    <!-- Scanline overlay -->
    <div class="scanline"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import type { Incident } from '@/models/incident'
import { IncidentType } from '@/models/incident'

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

  return primaryIncident.value.type
    .replace(/_/g, ' ')
    .toUpperCase()
})

const incidentSubtitle = computed(() => {
  if (!primaryIncident.value) return ''

  const difficulty = primaryIncident.value.difficulty
  const stars = '★'.repeat(difficulty)

  return `DIFFICULTY: ${stars} (${difficulty}/10)`
})

const elapsedTime = computed(() => {
  if (!primaryIncident.value) return '00:00'

  const startTime = new Date(primaryIncident.value.start_time).getTime()
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
  background: linear-gradient(180deg, #2a0000 0%, #1a0000 100%);
  border: 2px solid #ff3333;
  border-radius: 4px;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.3s ease;
}

.incident-alert:hover {
  border-color: #ff5555;
  box-shadow: 0 0 20px rgba(255, 51, 51, 0.5);
}

.incident-alert.pulsing {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    border-color: #ff3333;
    box-shadow: 0 0 10px rgba(255, 51, 51, 0.3);
  }
  50% {
    border-color: #ff5555;
    box-shadow: 0 0 30px rgba(255, 51, 51, 0.6);
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
  background: rgba(255, 51, 51, 0.2);
  border: 1px solid #ff3333;
  border-radius: 50%;
}

.alert-icon .icon {
  width: 24px;
  height: 24px;
  color: #ff3333;
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
  color: #ff3333;
  letter-spacing: 0.05em;
}

.alert-subtitle {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: #ff9999;
}

.alert-timer {
  flex-shrink: 0;
  font-family: 'Courier New', monospace;
  font-size: 1.25rem;
  font-weight: bold;
  color: #ff3333;
  letter-spacing: 0.1em;
}

.alert-badge {
  flex-shrink: 0;
  padding: 0.25rem 0.75rem;
  background: #ff3333;
  color: #fff;
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
  background: linear-gradient(to bottom, rgba(255, 51, 51, 0.8), transparent);
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
