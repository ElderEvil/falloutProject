<template>
  <UModal :modelValue="true" @close="$emit('close')" size="xl">
    <template #header>
      <div class="incident-header">
        <Icon :icon="incidentIcon" class="incident-header-icon" />
        <div class="incident-header-text">
          <h2 class="incident-title">{{ incidentTitle }}</h2>
          <p class="incident-subtitle">
            {{ incident?.room_name ?? 'Unknown room' }} &middot; {{ difficultyStars }} DIFFICULTY
            {{ incident?.difficulty }}/10<span v-if="incident && incident.spread_count > 0">
              &middot; SPREAD &times;{{ incident.spread_count }}</span
            >
          </p>
        </div>
        <span v-if="incident" class="incident-badge" :class="statusClass">{{
          incident.status.toUpperCase()
        }}</span>
      </div>
    </template>

    <ComponentLoader v-if="isLoading" label="Loading incident data…" />

    <UAlert v-else-if="loadFailed" variant="danger" title="Incident unavailable">
      <p>Unable to load incident data.</p>
      <UButton class="mt-3" variant="secondary" size="sm" @click="loadIncident">RETRY</UButton>
    </UAlert>

    <div v-else-if="incident" class="incident-content">
      <div v-if="resolution" class="result-view">
        <div class="result-banner" :class="resolution.success ? 'victory' : 'defeat'">
          <Icon
            :icon="resolution.success ? 'mdi:trophy' : 'mdi:skull-crossbones'"
            class="result-icon"
          />
          <div>
            <h3 class="result-title">
              {{ resolution.success ? 'INCIDENT RESOLVED' : 'INCIDENT FAILED' }}
            </h3>
            <p class="result-subtitle">{{ resolutionSubtitle }}</p>
          </div>
        </div>

        <div class="stat-row">
          <div class="stat">
            <span class="stat-label">Elapsed</span>
            <span class="stat-value">{{ formatElapsedTime(incident.elapsed_time) }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Dweller damage</span>
            <span class="stat-value danger">{{ incident.damage_dealt }} HP</span>
          </div>
          <div class="stat">
            <span class="stat-label">Outcome</span>
            <span class="stat-value"
              >{{ incident.progress.current }} / {{ incident.progress.target }}</span
            >
          </div>
        </div>

        <div v-if="incident.loot" class="loot-items">
          <div v-if="incident.loot.caps" class="loot-item">
            <Icon icon="mdi:bottle-cap" class="loot-icon" />
            <span class="loot-text">{{ incident.loot.caps }} Caps</span>
          </div>
          <div v-for="(item, idx) in incident.loot.items ?? []" :key="idx" class="loot-item">
            <Icon :icon="getItemIcon(item.type)" class="loot-icon" />
            <span class="loot-text">
              {{ item.name }}
              <span v-if="item.rarity" class="loot-rarity">({{ item.rarity }})</span>
              <span v-if="item.quantity">(x{{ item.quantity }})</span>
            </span>
          </div>
        </div>

        <details v-if="incident.events.length" class="section">
          <summary class="section-title collapsible-summary">
            <Icon icon="mdi:clipboard-text-clock-outline" class="section-title-icon" />
            Incident journal ({{ incident.events.length }})
          </summary>
          <div class="journal-list">
            <div v-for="event in incident.events" :key="event.id" class="journal-entry">
              <Icon :icon="journalIcon(event.kind)" class="journal-entry-icon" />
              <span v-if="eventTime(event)" class="journal-time">{{ eventTime(event) }}</span>
              <span>{{ journalMessage(event) }}</span>
            </div>
          </div>
        </details>

        <div class="result-actions">
          <UButton variant="primary" @click="$emit('close')">CLOSE</UButton>
        </div>
      </div>

      <template v-else>
        <IncidentStage
          :incident="incident"
          :dwellers="dwellers"
          :treating-dweller-id="treatingDwellerId"
          :vault-medical="vaultMedical"
          :preview="preview"
          @dweller-click="openDweller"
          @heal="healDwellerById"
          @treat-radiation="treatRadawayById"
        />

        <!-- Status -->
        <div class="section">
          <h3 class="section-title">
            <Icon
              :icon="incident.objective === 'contain' ? 'mdi:shield-check' : 'mdi:sword-cross'"
              class="section-title-icon"
            />
            {{ incident.objective === 'contain' ? 'Containment status' : 'Combat status' }}
          </h3>
          <div class="stat-row">
            <div class="stat">
              <span class="stat-label">Elapsed</span>
              <span class="stat-value">{{ formatElapsedTime(incident.elapsed_time) }}</span>
            </div>
            <div class="stat">
              <span class="stat-label">Dweller damage</span>
              <span class="stat-value danger">{{ incident.damage_dealt }} HP</span>
            </div>
            <div class="stat">
              <span class="stat-label">{{
                incident.objective === 'contain' ? 'Contained' : 'Enemies down'
              }}</span>
              <span class="stat-value"
                >{{ incident.progress.current }} / {{ incident.progress.target }}</span
              >
            </div>
          </div>
          <UProgressBar
            :model-value="progressPercent"
            :height="10"
            :glow="false"
            color="var(--color-theme-primary)"
            ariaLabel="Incident progress"
          />
          <div class="progress-value">
            {{ progressPercent }}% &middot; {{ remainingProgress }}
            {{ incident.objective === 'contain' ? 'to contain' : 'enemies left' }}
          </div>
        </div>

        <!-- Response team -->
        <details class="section">
          <summary class="section-title collapsible-summary">
            <Icon icon="mdi:account-group" class="section-title-icon" />
            Response team ({{ availableResponders.length }})
          </summary>
          <div v-if="bestResponders.length" class="responder-quick">
            <UButton
              variant="primary"
              size="sm"
              :loading="isSendingBest"
              @click="sendBestDefenders"
            >
              {{ incident.response.label.toUpperCase() }}: {{ bestResponders.length }} BEST
            </UButton>
            <span class="responder-quick-note">
              {{ bestResponders.map((d) => d.first_name).join(', ') }}
            </span>
          </div>
          <div v-if="availableResponders.length" class="responder-rows">
            <div v-for="dweller in availableResponders" :key="dweller.id" class="responder-row">
              <DwellerPortrait
                :thumbnail-url="dweller.thumbnail_url"
                :alt="`${dweller.first_name} ${dweller.last_name ?? ''}`"
                image-class="responder-portrait"
                fallback-class="h-10 w-10 icon-primary"
              />
              <div class="responder-main">
                <button
                  type="button"
                  class="responder-name"
                  :title="`Open ${dweller.first_name} details`"
                  @click="openDweller(dweller.id)"
                >
                  {{ dweller.first_name }}
                </button>
                <span class="responder-meta"
                  >Lv. {{ dweller.level }} &middot; POW {{ getCombatPower(dweller) }}</span
                >
                <UProgressBar
                  :model-value="hpPercent(dweller)"
                  :height="5"
                  :glow="false"
                  :color="hpFillColor(dweller)"
                />
              </div>
              <span class="responder-hp" :class="hpClass(dweller)"
                >{{ dweller.health }}/{{ dweller.max_health }}</span
              >
              <div class="responder-actions">
                <UButton
                  v-if="heal(dweller).need"
                  variant="secondary"
                  size="sm"
                  :loading="treatingDwellerId === dweller.id"
                  :disabled="preview || treatingDwellerId !== null"
                  :title="preview ? 'Preview mode — treatment disabled' : heal(dweller).title"
                  @click="healDwellerById(dweller.id)"
                >
                  HEAL
                </UButton>
                <UButton
                  v-if="rad(dweller).need"
                  variant="secondary"
                  size="sm"
                  :loading="treatingDwellerId === dweller.id"
                  :disabled="preview || treatingDwellerId !== null"
                  :title="preview ? 'Preview mode — treatment disabled' : rad(dweller).title"
                  @click="treatRadawayById(dweller.id)"
                >
                  RAD
                </UButton>
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
          </div>
          <p v-else class="empty-note">All available adults are already defending or away.</p>
        </details>

        <!-- Journal -->
        <details v-if="incident.events.length" class="section">
          <summary class="section-title collapsible-summary">
            <Icon icon="mdi:clipboard-text-clock-outline" class="section-title-icon" />
            Incident journal ({{ incident.events.length }})
          </summary>
          <div class="journal-list">
            <div v-for="event in incident.events" :key="event.id" class="journal-entry">
              <Icon :icon="journalIcon(event.kind)" class="journal-entry-icon" />
              <span v-if="eventTime(event)" class="journal-time">{{ eventTime(event) }}</span>
              <span>{{ journalMessage(event) }}</span>
            </div>
          </div>
        </details>

        <!-- Rewards -->
        <details v-if="incident.loot" class="section">
          <summary class="section-title collapsible-summary">
            <Icon icon="mdi:treasure-chest" class="section-title-icon" />
            Rewards
          </summary>
          <div class="loot-items">
            <div v-if="incident.loot.caps" class="loot-item">
              <Icon icon="mdi:bottle-cap" class="loot-icon" />
              <span class="loot-text">{{ incident.loot.caps }} Caps</span>
            </div>
            <div v-for="(item, idx) in incident.loot.items ?? []" :key="idx" class="loot-item">
              <Icon :icon="getItemIcon(item.type)" class="loot-icon" />
              <span class="loot-text">
                {{ item.name }}
                <span v-if="item.rarity" class="loot-rarity">({{ item.rarity }})</span>
                <span v-if="item.quantity">(x{{ item.quantity }})</span>
              </span>
            </div>
          </div>
        </details>
      </template>
    </div>

    <!-- Scanline overlay -->
    <div class="scanline"></div>
  </UModal>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import UAlert from '@/core/components/ui/UAlert.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import IncidentStage from './IncidentStage.vue'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getCombatPower } from '@/modules/dwellers/models/dweller'
import { useIncidentStore } from '../../stores/incident'
import { incidentApi } from '../../api/incident'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'
import type { Incident } from '../../models/incident'
import {
  IncidentStatus,
  getIncidentIcon,
  getTreatmentState,
  type MedicalSupply,
  type VaultMedicalStocks,
} from '../../models/incident'

interface Props {
  incidentId: string
  vaultId: string
  dwellers: DwellerShort[]
  previewIncident?: Incident | null
  previewVaultMedical?: VaultMedicalStocks | null
  preview?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  responded: []
}>()

const authStore = useAuthStore()
const incidentStore = useIncidentStore()
const medicalStore = useDwellerMedicalStore()
const vaultStore = useVaultStore()
const router = useRouter()
const toast = useToast()

const incident = ref<Incident | null>(null)
const isLoading = ref(true)
const loadFailed = ref(false)
const resolution = ref<{ success: boolean } | null>(null)
const assigningDwellerId = ref<string | null>(null)
const treatingDwellerId = ref<string | null>(null)

const vaultMedical = computed<VaultMedicalStocks>(
  () =>
    props.previewVaultMedical ?? {
      stimpack: vaultStore.loadedVaults[props.vaultId]?.stimpack ?? 0,
      radaway: vaultStore.loadedVaults[props.vaultId]?.radaway ?? 0,
    }
)

const resolutionForStatus = (status: IncidentStatus) =>
  status === IncidentStatus.RESOLVED || status === IncidentStatus.FAILED
    ? { success: status === IncidentStatus.RESOLVED }
    : null

// Lifecycle
onMounted(async () => {
  await loadIncident()
})

// Methods
async function loadIncident() {
  if (props.previewIncident) {
    incident.value = props.previewIncident
    resolution.value = resolutionForStatus(props.previewIncident.status)
    loadFailed.value = false
    isLoading.value = false
    return
  }
  if (!authStore.token) return

  try {
    await incidentStore.fetchIncidents(props.vaultId, authStore.token)
    const lookup = incidentStore.getIncidentById(props.incidentId)
    if (lookup) {
      incident.value = lookup
      resolution.value = resolutionForStatus(lookup.status)
      loadFailed.value = false
      if (resolution.value) polling.pause()
      return
    }
    const final = await incidentApi.getIncident(props.vaultId, props.incidentId, authStore.token)
    incident.value = final
    resolution.value = resolutionForStatus(final.status)
    if (resolution.value) polling.pause()
    loadFailed.value = false
  } catch {
    if (!incident.value && !resolution.value) {
      loadFailed.value = true
      toast.error('Failed to load incident')
    }
  } finally {
    isLoading.value = false
  }
}

// Auto-refresh every 5 seconds while the modal is mounted (live mode only).
const polling = usePolling(
  () => {
    if (!props.previewIncident) void loadIncident()
  },
  { interval: 5_000, immediate: false }
)

async function assignResponder(dwellerId: string) {
  if (!authStore.token || assigningDwellerId.value) return
  assigningDwellerId.value = dwellerId
  try {
    await incidentStore.assignResponders(
      props.vaultId,
      props.incidentId,
      [dwellerId],
      authStore.token
    )
    emit('responded')
  } catch {
    toast.error('Failed to assign responder')
  } finally {
    assigningDwellerId.value = null
  }
}

const isSendingBest = ref(false)

function openDweller(dwellerId: string) {
  void router.push({ name: 'dwellerDetail', params: { id: props.vaultId, dwellerId } })
}

const heal = (dweller: DwellerShort) => getTreatmentState(dweller, vaultMedical.value, 'stimpack')
const rad = (dweller: DwellerShort) => getTreatmentState(dweller, vaultMedical.value, 'radaway')

async function treatDwellerById(dwellerId: string, supply: MedicalSupply) {
  const dweller = props.dwellers.find((entry) => entry.id === dwellerId)
  if (!authStore.token || treatingDwellerId.value || !dweller) return
  if (!getTreatmentState(dweller, vaultMedical.value, supply).need) return
  treatingDwellerId.value = dwellerId
  try {
    const useSupply =
      supply === 'stimpack'
        ? () => medicalStore.useStimpack(dwellerId, authStore.token as string)
        : () => medicalStore.useRadaway(dwellerId, authStore.token as string)
    const treated = await useSupply()
    if (!treated && vaultMedical.value[supply] > 0) {
      const issued = await medicalStore.issueMedicalSupply(
        props.vaultId,
        dwellerId,
        supply,
        authStore.token as string
      )
      if (!issued) {
        toast.error(`Failed to issue ${supply === 'stimpack' ? 'stimpak' : 'RadAway'} from vault`)
        return
      }
      await useSupply()
    }
    await loadIncident()
  } finally {
    treatingDwellerId.value = null
  }
}

async function healDwellerById(dwellerId: string) {
  await treatDwellerById(dwellerId, 'stimpack')
}

async function treatRadawayById(dwellerId: string) {
  await treatDwellerById(dwellerId, 'radaway')
}

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

function journalIcon(kind: string): string {
  switch (kind) {
    case 'round':
      return 'mdi:sword-cross'
    case 'containment':
      return 'mdi:shield-check'
    case 'failed':
      return 'mdi:alert-circle'
    case 'spawned':
      return 'mdi:alert'
    case 'responders_assigned':
      return 'mdi:account-group'
    case 'spread':
      return 'mdi:arrow-expand-all'
    case 'resolved':
      return 'mdi:trophy'
    default:
      return 'mdi:dots-horizontal'
  }
}

function journalMessage(event: Incident['events'][number]): string {
  const data = event.data
  if (event.kind === 'round' && data) {
    const dealt = data.damage_to_threat
    const taken = data.damage_to_dwellers
    const killed = data.enemies_defeated
    const expected = data.expected_threat
    if (
      typeof dealt === 'number' &&
      typeof taken === 'number' &&
      typeof killed === 'number' &&
      typeof expected === 'number'
    )
      return `Dealt ${Math.round(dealt)} damage (${killed}/${expected} down) · took ${Math.round(taken)}`
    if (typeof dealt === 'number' && typeof taken === 'number')
      return `Damage dealt: ${Math.round(dealt)} · Damage taken: ${Math.round(taken)}`
  }
  return event.message
}

function eventTime(event: Incident['events'][number]): string {
  if (!event.created_at) return ''
  const stamp = event.created_at.endsWith('Z') ? event.created_at : `${event.created_at}Z`
  const time = new Date(stamp).getTime()
  if (!Number.isFinite(time)) return ''
  const date = new Date(time)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

// Computed
const incidentIcon = computed(() =>
  incident.value ? getIncidentIcon(incident.value.type) : 'mdi:alert-octagon'
)

const incidentTitle = computed(() => {
  if (!incident.value) return 'INCIDENT'
  return incident.value.type.replace(/_/g, ' ').toUpperCase()
})

const statusClass = computed(() => {
  switch (incident.value?.status) {
    case 'spreading':
      return 'warning'
    case 'resolved':
      return 'success'
    case 'failed':
      return 'danger'
    default:
      return 'active'
  }
})

const difficultyStars = computed(() => {
  if (!incident.value) return ''
  return '★'.repeat(incident.value.difficulty)
})

const resolutionSubtitle = computed(() => {
  if (!incident.value) return ''
  if (resolution.value?.success) {
    const caps = incident.value.loot?.caps ?? 0
    return caps > 0 ? `Recovered ${caps} caps — vault secure.` : 'Vault secure.'
  }
  return `The vault was overrun — ${incident.value.damage_dealt} damage taken.`
})

const progressPercent = computed(() => {
  if (!incident.value || incident.value.progress.target <= 0) return 0
  return Math.min(
    100,
    Math.floor((incident.value.progress.current / incident.value.progress.target) * 100)
  )
})

const remainingProgress = computed(() =>
  incident.value ? Math.max(0, incident.value.progress.target - incident.value.progress.current) : 0
)

const hpPercent = (dweller: DwellerShort) =>
  dweller.max_health > 0 ? Math.round((dweller.health / dweller.max_health) * 100) : 0

const hpClass = (dweller: DwellerShort) => {
  const pct = hpPercent(dweller)
  if (pct < 25) return 'hp-critical'
  if (pct < 50) return 'hp-low'
  return 'hp-healthy'
}

const HP_FILL_COLOR: Record<string, string> = {
  'hp-healthy': 'var(--color-success)',
  'hp-low': 'var(--color-warning)',
  'hp-critical': 'var(--color-danger)',
}

const hpFillColor = (dweller: DwellerShort) =>
  HP_FILL_COLOR[hpClass(dweller)] ?? HP_FILL_COLOR['hp-healthy']!

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
/* Header pattern shared with the arena/room modals */
.incident-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  padding-top: 0.5rem;
  border-bottom: 1px solid var(--color-surface-light);
}

.incident-header-icon {
  width: 40px;
  height: 40px;
  color: var(--color-danger);
  flex-shrink: 0;
}

.incident-header-text {
  min-width: 0;
}

.incident-title {
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  letter-spacing: 0.05em;
  margin: 0;
}

.incident-subtitle {
  font-size: 0.75rem;
  color: var(--color-gray-500);
  margin: 0.25rem 0 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.incident-badge {
  margin-left: auto;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: bold;
  letter-spacing: 0.08em;
  color: var(--color-gray-400);
  flex-shrink: 0;
}

.incident-badge.active {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.incident-badge.warning {
  border-color: var(--color-warning);
  color: var(--color-warning);
}

.incident-badge.success {
  border-color: var(--color-success);
  color: var(--color-success);
}

.incident-badge.danger {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* Section pattern shared with the other room-modal sections */
.incident-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 1rem 1.5rem;
  max-height: 600px;
  overflow-y: auto;
}

.result-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.result-banner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.9rem 1rem;
  border-radius: 4px;
}

.result-banner.victory {
  background: color-mix(in srgb, var(--color-theme-primary) 12%, transparent);
  border: 1px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.result-banner.defeat {
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
}

.result-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.result-title {
  font-size: 1.1rem;
  font-weight: bold;
  letter-spacing: 0.08em;
  margin: 0;
}

.result-subtitle {
  font-size: 0.8rem;
  margin: 0.25rem 0 0;
  opacity: 0.85;
}

.result-actions {
  display: flex;
  justify-content: center;
  padding: 0.25rem 0;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.section-title-icon {
  width: 0.875rem;
  height: 0.875rem;
}

summary.section-title {
  cursor: pointer;
}

summary.section-title:hover {
  color: var(--color-warning);
}

summary.section-title::marker {
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  text-transform: uppercase;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-variant-numeric: tabular-nums;
}

.stat-value.danger {
  color: var(--color-danger);
}

.progress-value {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  text-align: right;
}

.responder-quick {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  background: color-mix(in srgb, var(--color-theme-primary) 6%, transparent);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.responder-quick-note {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.responder-rows {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.responder-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.4rem 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
}

.responder-portrait {
  width: 36px;
  height: 36px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid var(--color-theme-glow);
}

.responder-main {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 0;
}

button.responder-name {
  padding: 0;
  background: none;
  border: none;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-align: left;
  cursor: pointer;
}

button.responder-name:hover,
button.responder-name:focus-visible {
  color: var(--color-warning);
  text-decoration: underline;
  outline: none;
}

button.responder-name:focus-visible {
  outline: 1px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.responder-meta {
  font-size: 0.7rem;
  color: var(--color-gray-500);
}

.responder-hp {
  font-size: 0.7rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.responder-hp.hp-healthy {
  color: var(--color-success);
}

.responder-hp.hp-low {
  color: var(--color-warning);
}

.responder-hp.hp-critical {
  color: var(--color-danger);
}

.responder-actions {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}

.empty-note {
  font-size: 0.8rem;
  color: var(--color-gray-500);
  margin: 0;
}

.journal-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 180px;
  overflow-y: auto;
  padding: 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
}

.journal-entry {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
  color: var(--color-gray-300);
  line-height: 1.35;
}

.journal-entry-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--color-gray-500);
}

.journal-time {
  font-size: 0.7rem;
  color: var(--color-theme-primary);
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.loot-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.loot-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
}

.loot-icon {
  width: 20px;
  height: 20px;
  color: var(--color-caps);
  flex-shrink: 0;
}

.loot-text {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
}

.loot-rarity {
  opacity: 0.8;
  margin-left: 0.5rem;
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
