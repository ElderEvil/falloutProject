<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import XPProgressBar from '../stats/XPProgressBar.vue'
import HappinessModifierPopover from './HappinessModifierPopover.vue'
import DwellerCardActions from './DwellerCardActions.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import DwellerAgeBadge from '../DwellerAgeBadge.vue'
import DwellerBadge from '../DwellerBadge.vue'
import DwellerIdentitySignal from '../DwellerIdentitySignal.vue'
import type { components } from '@/core/types/api.generated'
import { normalizeImageUrl } from '@/core/utils/image'
import { getRadiationPercentage } from '../../models/dweller'

type DwellerDetailRead = components['schemas']['DwellerReadFull']

interface Props {
  dweller: DwellerDetailRead
  imageUrl?: string | null
  loading?: boolean
  generatingPortrait?: boolean
  availableStimpaks?: number
  availableRadaways?: number
  issuingMedicalSupply?: boolean
  usingStimpak?: boolean
  usingRadAway?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'chat'): void
  (e: 'assign'): void
  (e: 'recall'): void
  (e: 'train'): void
  (e: 'use-stimpak'): void
  (e: 'use-radaway'): void
  (e: 'unassign'): void
  (e: 'send-wasteland'): void
  (e: 'generate-portrait'): void
  (e: 'issue-medical-supply', supply: 'stimpack' | 'radaway'): void
}>()

const getImageUrl = (imagePath: string) => {
  return normalizeImageUrl(imagePath)
}

const healthPercentage = computed(() => {
  if (!props.dweller.max_health) return 0
  return (props.dweller.health / props.dweller.max_health) * 100
})

const radiationPercentage = computed(() => getRadiationPercentage(props.dweller.radiation, props.dweller.max_health))

const happinessLevel = computed(() => {
  const happiness = props.dweller.happiness || 50
  if (happiness >= 75) return 'high'
  if (happiness >= 50) return 'medium'
  if (happiness >= 25) return 'low'
  return 'critical'
})

const happinessColor = computed(() => {
  switch (happinessLevel.value) {
    case 'high':
      return 'var(--color-theme-primary)'
    case 'medium':
      return 'var(--color-terminal-green-dark)'
    case 'low':
      return 'var(--color-warning)'
    case 'critical':
      return 'var(--color-danger)'
    default:
      return 'var(--color-theme-primary)'
  }
})

const GENDER_META = {
  male: { icon: 'mdi:gender-male', color: '#60a5fa' },
  female: { icon: 'mdi:gender-female', color: '#f472b6' },
} as const

const genderMeta = computed(() => GENDER_META[props.dweller.gender as keyof typeof GENDER_META] ?? GENDER_META.male)

const RARITY_META: Record<string, { icon: string; color: string }> = {
  legendary: { icon: 'mdi:star', color: '#fbbf24' },
  rare: { icon: 'mdi:star', color: '#a78bfa' },
  uncommon: { icon: 'mdi:star', color: '#60a5fa' },
  common: { icon: 'mdi:star', color: '#9ca3af' },
}

const rarityMeta = computed(() => RARITY_META[props.dweller.rarity?.toLowerCase() ?? ''] ?? RARITY_META.common)
const rarityLabel = computed(() => props.dweller.rarity || 'Common')


const canIssueStimpack = computed(() => (props.dweller.stimpack || 0) < 15 && (props.availableStimpaks ?? 0) > 0)
const canIssueRadaway = computed(() => (props.dweller.radaway || 0) < 15 && (props.availableRadaways ?? 0) > 0)

const availableStimpaksCount = computed(() => props.availableStimpaks ?? 0)
const availableRadawaysCount = computed(() => props.availableRadaways ?? 0)

const canUseStimpak = computed(
  () => (props.dweller.stimpack || 0) > 0 && props.dweller.health < props.dweller.max_health
)
const canUseRadaway = computed(
  () => (props.dweller.radaway || 0) > 0 && (props.dweller.radiation || 0) > 0
)
</script>

<template>
  <div class="dweller-card">
    <div class="portrait-container">
      <template v-if="imageUrl">
        <img
          :src="getImageUrl(imageUrl)"
          alt="Dweller Portrait"
          :class="['portrait-image', { 'grayscale brightness-50 contrast-125': dweller.is_dead }]"
        />
        <span
          v-if="dweller.is_dead"
          class="dead-portrait-marker absolute right-3 top-3 rounded-full border border-red-400/70 bg-black/75 p-2 text-red-400 shadow-[0_0_12px_rgba(248,113,113,0.6)]"
          role="img"
          aria-label="Deceased"
        >
          <Icon icon="mdi:skull" class="h-6 w-6" :ariaHidden="true" />
        </span>
      </template>
      <template v-else>
        <button
          type="button"
          class="portrait-placeholder"
          :disabled="loading"
          @click="emit('generate-portrait')"
        >
          <Icon
            :icon="generatingPortrait ? 'mdi:loading' : 'mdi:account-circle'"
            class="h-48 w-48"
            :class="{ 'animate-spin': generatingPortrait }"
            style="color: var(--color-theme-primary); opacity: 0.3"
          />
          <span class="placeholder-hint">{{ generatingPortrait ? 'Generating portrait…' : 'Generate portrait' }}</span>
        </button>
      </template>
    </div>

    <div class="info-badges">
      <DwellerBadge :icon="genderMeta.icon" :color="genderMeta.color" :label="dweller.gender" size="md" />
      <DwellerBadge :icon="rarityMeta.icon" :color="rarityMeta.color" :label="rarityLabel" size="md" />
      <DwellerAgeBadge :age-group="dweller.age_group" :show-label="true" size="md" />
    </div>
    <DwellerIdentitySignal :visual-attributes="dweller.visual_attributes" compact />

    <div class="stats-container">
      <div class="stat-row">
        <span class="stat-label">Level</span>
        <span class="stat-value">{{ dweller.level }}</span>
      </div>

      <div class="stat-row">
        <span class="stat-label">Health</span>
        <span class="stat-value">{{ dweller.health }} / {{ dweller.max_health }}</span>
      </div>
      <UProgressBar :model-value="healthPercentage" :radiation="radiationPercentage" :height="10" />

      <div class="stat-row happiness-row">
        <span class="stat-label">Happiness</span>
        <div class="happiness-value-container">
          <span class="stat-value" :style="{ color: happinessColor }"
            >{{ dweller.happiness }}%</span
          >
          <HappinessModifierPopover :dweller-id="dweller.id" />
        </div>
      </div>
      <UProgressBar :model-value="dweller.happiness" :height="10" :color="happinessColor" />

      <XPProgressBar :level="dweller.level" :current-x-p="dweller.experience" />

      <div class="inventory-stats">
        <div class="inventory-item">
          <Icon icon="mdi:medical-bag" class="h-5 w-5 text-green-500 inventory-type-icon" />
          <div class="inventory-count">
            <span class="inventory-value">{{ dweller.stimpack || 0 }}</span>
            <span class="inventory-label">Stimpack</span>
          </div>
          <div class="inventory-actions">
            <UButton
              class="inventory-use-btn"
              variant="secondary"
              size="sm"
              aria-label="Use Stimpack"
              :title="canUseStimpak ? 'Use one Stimpack (heals dweller)' : 'No Stimpaks to use'"
              :disabled="!canUseStimpak || usingStimpak"
              :loading="usingStimpak"
              @click="emit('use-stimpak')"
            >
              <Icon icon="mdi:syringe" class="h-4 w-4" />
              Use
            </UButton>
            <UButton
              v-if="availableStimpaksCount > 0"
              class="inventory-issue-btn"
              variant="ghost"
              size="xs"
              aria-label="Issue Stimpack from vault"
              :title="canIssueStimpack ? `Issue one Stimpack from vault (${availableStimpaksCount} available)` : 'Dweller at capacity (15)'"
              :disabled="!canIssueStimpack || issuingMedicalSupply"
              :loading="issuingMedicalSupply"
              @click="emit('issue-medical-supply', 'stimpack')"
            >
              <Icon icon="mdi:plus" class="h-3.5 w-3.5" />
              <span class="issue-label">Issue ({{ availableStimpaksCount }})</span>
            </UButton>
          </div>
        </div>

        <div class="inventory-item">
          <Icon icon="mdi:radiation" class="h-5 w-5 text-yellow-500 inventory-type-icon" />
          <div class="inventory-count">
            <span class="inventory-value">{{ dweller.radaway || 0 }}</span>
            <span class="inventory-label">RadAway</span>
          </div>
          <div class="inventory-actions">
            <UButton
              class="inventory-use-btn"
              variant="secondary"
              size="sm"
              aria-label="Use RadAway"
              :title="canUseRadaway ? 'Use one RadAway (reduces radiation)' : 'No RadAway to use'"
              :disabled="!canUseRadaway || usingRadAway"
              :loading="usingRadAway"
              @click="emit('use-radaway')"
            >
              <Icon icon="mdi:syringe" class="h-4 w-4" />
              Use
            </UButton>
            <UButton
              v-if="availableRadawaysCount > 0"
              class="inventory-issue-btn"
              variant="ghost"
              size="xs"
              aria-label="Issue RadAway from vault"
              :title="canIssueRadaway ? `Issue one RadAway from vault (${availableRadawaysCount} available)` : 'Dweller at capacity (15)'"
              :disabled="!canIssueRadaway || issuingMedicalSupply"
              :loading="issuingMedicalSupply"
              @click="emit('issue-medical-supply', 'radaway')"
            >
              <Icon icon="mdi:plus" class="h-3.5 w-3.5" />
              <span class="issue-label">Issue ({{ availableRadawaysCount }})</span>
            </UButton>
          </div>
        </div>
      </div>

      <div v-if="dweller.radiation && dweller.radiation > 0" class="stat-row">
        <span class="stat-label">Radiation</span>
        <span class="stat-value text-yellow-400">{{ dweller.radiation }}</span>
      </div>
    </div>

    <DwellerCardActions
      :dweller="dweller"
      :loading="loading"
      @chat="emit('chat')"
      @assign="emit('assign')"
      @recall="emit('recall')"
      @train="emit('train')"
      @unassign="emit('unassign')"
      @send-wasteland="emit('send-wasteland')"
    />
  </div>
</template>

<style scoped>
.dweller-card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.portrait-container {
  position: relative;
  width: 100%;
  max-width: 300px;
  margin: 0 auto;
}

.portrait-image {
  width: 100%;
  height: auto;
  border-radius: 8px;
  border: 2px solid var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.portrait-placeholder {
  width: 100%;
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  background: rgba(0, 0, 0, 0.5);
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  color: inherit;
  cursor: pointer;
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
}

.portrait-placeholder:hover:not(:disabled),
.portrait-placeholder:focus-visible {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
  outline: none;
}

.portrait-placeholder:disabled {
  cursor: wait;
}

.placeholder-hint {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  text-align: center;
}

.info-badges {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  flex-wrap: wrap;
}

.stats-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-weight: 600;
  color: var(--color-theme-primary);
  text-shadow: 0 0 3px var(--color-theme-glow);
  opacity: 0.8;
}

.stat-value {
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.happiness-row {
  position: relative;
}

.happiness-value-container {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.inventory-stats {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  margin-top: 0.5rem;
}

.inventory-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.inventory-type-icon {
  flex-shrink: 0;
}

.inventory-count {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
  min-width: 3.5rem;
}

.inventory-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
}

.inventory-use-btn {
  flex-shrink: 0;
}

.inventory-issue-btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.issue-label {
  font-size: 0.7rem;
  font-weight: 700;
}

.inventory-value {
  font-weight: 700;
  font-size: 1.125rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.inventory-label {
  font-size: 0.7rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
</style>
