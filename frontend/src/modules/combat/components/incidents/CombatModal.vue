<template>
  <UModal :modelValue="true" @close="$emit('close')" size="xl">
    <template #header>
      <div class="modal-header">
        <div class="header-left">
          <Icon :icon="incidentIcon" class="header-icon" />
          <div>
            <h2 class="header-title">{{ incidentTitle }}</h2>
            <div class="header-subtitle">
              {{ difficultyStars }} DIFFICULTY {{ incident?.difficulty }}/10
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-if="isLoading" class="loading">
      <div class="spinner">⚙️</div>
      <p>Loading incident data...</p>
    </div>

    <div v-else-if="incident" class="combat-modal-content">
      <!-- Room Info Section -->
      <div class="section">
        <h3 class="section-title">&gt;&gt; LOCATION</h3>
        <div class="section-content">
          <div class="info-row">
            <span class="info-label">Room</span>
            <span class="info-value">{{ incident.room_name ?? 'Unknown room' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Status</span>
            <span class="status-badge" :class="`status-${incident.status}`">
              {{ incident.status.toUpperCase() }}
            </span>
          </div>
          <div v-if="incident.rooms_affected.length > 1" class="info-row">
            <span class="info-label">Spreading</span>
            <span class="info-value warning">
              {{ incident.rooms_affected.length }} rooms affected (spread count:
              {{ incident.spread_count }})
            </span>
          </div>
        </div>
      </div>

      <!-- Combat Status Section -->
      <div class="section">
        <h3 class="section-title">&gt;&gt; COMBAT STATUS</h3>
        <div class="section-content">
          <div class="combat-stats">
            <div class="stat">
              <div class="stat-label">Elapsed Time</div>
              <div class="stat-value">{{ formatElapsedTime(incident.elapsed_time) }}</div>
            </div>
            <div class="stat">
              <div class="stat-label">Damage Dealt</div>
              <div class="stat-value danger">{{ incident.damage_dealt }} HP</div>
            </div>
            <div class="stat">
              <div class="stat-label">Enemies Down</div>
              <div class="stat-value success">
                {{ incident.enemies_defeated }} / {{ expectedEnemies }}
              </div>
            </div>
          </div>

          <!-- Progress bars -->
          <div class="progress-section">
            <div class="progress-item">
              <div class="progress-label">Threat Contained</div>
              <UProgressBar
                :model-value="combatProgress"
                :height="20"
                :glow="false"
                color="linear-gradient(90deg, var(--color-theme-primary) 0%, var(--color-theme-glow) 100%)"
                ariaLabel="Threat contained"
                class="combat-progress-bar"
              />
              <div class="progress-value">{{ combatProgress }}% · {{ expectedEnemies - incident.enemies_defeated }} enemies left</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Loot Preview Section -->
      <div v-if="incident.loot" class="section">
        <h3 class="section-title">&gt;&gt; REWARDS</h3>
        <div class="section-content">
          <div class="loot-items">
            <div v-if="incident.loot.caps" class="loot-item">
              <Icon icon="mdi:bottle-cap" class="loot-icon" />
              <span class="loot-text">{{ incident.loot.caps }} Caps</span>
            </div>
            <div v-for="(item, idx) in incident.loot.items" :key="idx" class="loot-item">
              <Icon :icon="getItemIcon(item.type)" class="loot-icon" />
              <span class="loot-text">
                {{ item.name }}
                <span v-if="item.rarity" class="loot-rarity">({{ item.rarity }})</span>
                <span v-if="item.quantity">(x{{ item.quantity }})</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Expected Loot (if not resolved) -->
      <div v-else class="section">
        <h3 class="section-title">&gt;&gt; EXPECTED REWARDS</h3>
        <div class="section-content">
          <div class="expected-loot">
            <p>Estimated caps: {{ estimatedCaps }}</p>
            <p>Possible items: Weapons, Outfits, or Junk</p>
          </div>
        </div>
      </div>

      <div class="section">
        <h3 class="section-title">&gt;&gt; RESPONSE TEAM</h3>
        <div class="section-content">
          <p class="expected-loot">Responders join this room and fight immediately.</p>
          <div v-if="bestResponders.length" class="responder-quick">
            <UButton
              variant="primary"
              size="sm"
              :loading="isSendingBest"
              @click="sendBestDefenders"
            >
              SEND {{ bestResponders.length }} BEST DEFENDERS
            </UButton>
            <span class="responder-quick-note">
              {{ bestResponders.map((d) => d.first_name).join(', ') }}
            </span>
          </div>
          <div v-if="availableResponders.length" class="responder-list">
            <div v-for="dweller in availableResponders" :key="dweller.id" class="responder-card">
              <div class="responder-info">
                <span class="responder-name">{{ dweller.first_name }}</span>
                <span class="responder-meta">
                  Lv. {{ dweller.level }} · {{ dweller.health }}/{{ dweller.max_health }} HP
                  · POW {{ getCombatPower(dweller) }}
                </span>
              </div>
              <UButton
                variant="secondary"
                size="sm"
                :disabled="assigningDwellerId === dweller.id"
                @click="assignResponder(dweller.id)"
              >
                {{ assigningDwellerId === dweller.id ? 'ASSIGNING...' : 'SEND' }}
              </UButton>
            </div>
          </div>
          <p v-else class="expected-loot">All available adults are already defending or away.</p>
        </div>
      </div>
    </div>

    <!-- Scanline overlay -->
    <div class="scanline"></div>
  </UModal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
import { useIncidentStore } from '../../stores/incident'
import type { Incident } from '../../models/incident'
import { IncidentType } from '../../models/incident'

interface Props {
  incidentId: string
  vaultId: string
  dwellers: DwellerShort[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  responded: []
}>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const toast = useToast()

const incident = ref<Incident | null>(null)
const isLoading = ref(true)
const assigningDwellerId = ref<string | null>(null)
// Lifecycle
onMounted(async () => {
  await loadIncident()
})

// Methods
async function loadIncident() {
  if (!authStore.token) return

  try {
    await incidentStore.fetchIncidents(props.vaultId, authStore.token)
    incident.value = incidentStore.getIncidentById(props.incidentId) || null
    isLoading.value = false
  } catch {
    toast.error('Failed to load incident')
  }
}

// Auto-refresh every 5 seconds while the modal is mounted.
usePolling(loadIncident, { interval: 5_000, immediate: false })

async function assignResponder(dwellerId: string) {
  if (!authStore.token || assigningDwellerId.value) return
  assigningDwellerId.value = dwellerId
  try {
    await incidentStore.assignResponders(props.vaultId, props.incidentId, [dwellerId], authStore.token)
    emit('responded')
  } catch {
    toast.error('Failed to assign responder')
  } finally {
    assigningDwellerId.value = null
  }
}

const isSendingBest = ref(false)

async function sendBestDefenders() {
  if (!authStore.token || isSendingBest.value || !bestResponders.value.length) return
  isSendingBest.value = true
  try {
    await incidentStore.assignResponders(
      props.vaultId,
      props.incidentId,
      bestResponders.value.map((dweller) => dweller.id),
      authStore.token
    )
    emit('responded')
  } catch {
    toast.error('Failed to assign defenders')
  } finally {
    isSendingBest.value = false
  }
}

function formatElapsedTime(seconds: number): string {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

function getItemIcon(type: string): string {
  switch (type) {
    case 'weapon':
      return 'mdi:pistol'
    case 'outfit':
      return 'mdi:tshirt-crew'
    case 'junk':
      return 'mdi:cog'
    default:
      return 'mdi:package-variant'
  }
}

// Computed
const incidentIcon = computed(() => {
  if (!incident.value) return 'mdi:alert-octagon'

  switch (incident.value.type) {
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
    case IncidentType.FERAL_GHOUL_ATTACK:
      return 'mdi:ghost'
    case IncidentType.RADSCORPION_ATTACK:
      return 'mdi:spider'
    default:
      return 'mdi:alert-octagon'
  }
})

const incidentTitle = computed(() => {
  if (!incident.value) return 'INCIDENT'
  return incident.value.type.replace(/_/g, ' ').toUpperCase()
})

const difficultyStars = computed(() => {
  if (!incident.value) return ''
  return '★'.repeat(incident.value.difficulty)
})

const combatProgress = computed(() => {
  if (!incident.value) return 0
  const expectedEnemies = incident.value.difficulty * 2
  return Math.min(100, Math.floor((incident.value.enemies_defeated / expectedEnemies) * 100))
})

const expectedEnemies = computed(() => {
  if (!incident.value) return 0
  return incident.value.difficulty * 2
})

const estimatedCaps = computed(() => {
  if (!incident.value) return '0-0'
  const min = 50 + (incident.value.difficulty - 1) * 50
  const max = 50 + incident.value.difficulty * 100
  return `${min}-${max}`
})

const availableResponders = computed(() =>
  props.dwellers.filter(
    (dweller) =>
      dweller.is_adult &&
      dweller.health > 0 &&
      dweller.room_id !== incident.value?.room_id &&
      !['exploring', 'questing', 'dead'].includes(dweller.status)
  )
)

const bestResponders = computed(() =>
  availableResponders.value
    .slice()
    .sort((a, b) => getCombatPower(b) - getCombatPower(a))
    .slice(0, 3)
)
</script>

<style scoped>
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1rem;
  padding-top: 0.5rem;
  border-bottom: 1px solid var(--color-surface-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-icon {
  width: 48px;
  height: 48px;
  color: var(--color-danger);
}

.header-title {
  font-family: 'Courier New', monospace;
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  letter-spacing: 0.05em;
  margin: 0;
}

.header-subtitle {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  margin-top: 0.25rem;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  font-weight: bold;
  letter-spacing: 0.1em;
}

.status-active {
  background: color-mix(in srgb, var(--color-danger) 20%, transparent);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
}

.status-spreading {
  background: color-mix(in srgb, var(--color-warning) 20%, transparent);
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
}

.status-resolved {
  background: rgba(var(--color-theme-primary-rgb), 0.2);
  border: 1px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 3rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.spinner {
  font-size: 3rem;
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.combat-modal-content {
  padding: 1.5rem;
  max-height: 600px;
  overflow-y: auto;
}

.section {
  margin-bottom: 2rem;
}

.section-title {
  font-family: 'Courier New', monospace;
  font-size: 1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin-bottom: 1rem;
  letter-spacing: 0.1em;
}

.section-content {
  padding-left: 1rem;
}

.info-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.info-label {
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.info-value {
  color: var(--color-theme-primary);
}

.info-value.warning {
  color: var(--color-theme-primary);
  opacity: 0.8;
}

.combat-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat-label {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  text-transform: uppercase;
}

.stat-value {
  font-family: 'Courier New', monospace;
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
}

.stat-value.danger {
  color: var(--color-danger);
}

.stat-value.success {
  color: var(--color-theme-primary);
}

.progress-section {
  margin-top: 1rem;
}

.progress-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.progress-label {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  text-transform: uppercase;
}

.combat-progress-bar {
  border-radius: 4px;
  background: var(--color-surface-light);
}

.combat-progress-bar :deep(.u-progress-bar__fill) {
  box-shadow: none;
}

.progress-value {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  text-align: right;
}

.responder-quick {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  padding: 0.6rem 0.75rem;
  background: color-mix(in srgb, var(--color-theme-primary) 6%, transparent);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.responder-quick-note {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.responder-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.5rem;
}

@media (min-width: 900px) {
  .responder-list {
    grid-template-columns: repeat(3, 1fr);
  }
}

.responder-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: rgba(var(--color-theme-primary-rgb), 0.05);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.responder-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.responder-name {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-theme-primary);
}

.responder-meta {
  font-family: 'Courier New', monospace;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.loot-items {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.loot-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(var(--color-theme-primary-rgb), 0.05);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.loot-icon {
  width: 24px;
  height: 24px;
  color: var(--color-theme-primary);
}

.loot-text {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
}

.loot-rarity {
  color: var(--color-theme-primary);
  opacity: 0.8;
  margin-left: 0.5rem;
}

.expected-loot {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  line-height: 1.6;
}

.scanline {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--color-theme-primary) 30%, transparent),
    transparent
  );
  animation: scanline 3s linear infinite;
  pointer-events: none;
  z-index: 1000;
}

@keyframes scanline {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(600px);
  }
}
</style>
