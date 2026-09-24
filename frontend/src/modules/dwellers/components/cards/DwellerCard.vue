<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import HealthRadiationBar from '@/core/components/common/HealthRadiationBar.vue'
import XPProgressBar from '../stats/XPProgressBar.vue'
import HappinessModifierPopover from './HappinessModifierPopover.vue'
import DwellerCardActions from './DwellerCardActions.vue'
import type { components } from '@/core/types/api.generated'
import { getStaticImageUrl } from '@/core/utils/image'
import {
  getEffectiveMaxHealth,
  getHappinessColor,
  getHappinessLevel,
  getHealthDisplay,
  getRadiationPercentage,
} from '../../models/dweller'

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
  return getStaticImageUrl(imagePath) ?? ''
}

const healthPercentage = computed(() => {
  if (!props.dweller.max_health) return 0
  return (
    (Math.min(
      props.dweller.health,
      getEffectiveMaxHealth(props.dweller.radiation, props.dweller.max_health)
    ) /
      props.dweller.max_health) *
    100
  )
})

const radiationPercentage = computed(() =>
  getRadiationPercentage(props.dweller.radiation, props.dweller.max_health)
)

const happinessColor = computed(() => getHappinessColor(getHappinessLevel(props.dweller.happiness)))

const availableStimpaksCount = computed(() => props.availableStimpaks ?? 0)
const availableRadawaysCount = computed(() => props.availableRadaways ?? 0)

// Supplies are shown only when this dweller has a reason to care: they carry
// the item, or they need it and the vault can supply it. A healthy dweller with
// empty pockets sees nothing.
const isInjured = computed(
  () => props.dweller.health < getEffectiveMaxHealth(props.dweller.radiation, props.dweller.max_health)
)
const isRadiated = computed(() => (props.dweller.radiation || 0) > 0)

const showStimpackSection = computed(
  () => (props.dweller.stimpack || 0) > 0 || (isInjured.value && availableStimpaksCount.value > 0)
)
const showRadawaySection = computed(
  () => (props.dweller.radaway || 0) > 0 || (isRadiated.value && availableRadawaysCount.value > 0)
)
const showInventory = computed(() => showStimpackSection.value || showRadawaySection.value)

const canIssueStimpack = computed(
  () => (props.dweller.stimpack || 0) < 15 && availableStimpaksCount.value > 0
)
const canIssueRadaway = computed(
  () => (props.dweller.radaway || 0) < 15 && availableRadawaysCount.value > 0
)

const canUseStimpak = computed(
  () =>
    (props.dweller.stimpack || 0) > 0 &&
    props.dweller.health < getEffectiveMaxHealth(props.dweller.radiation, props.dweller.max_health)
)
const canUseRadaway = computed(
  () => (props.dweller.radaway || 0) > 0 && (props.dweller.radiation || 0) > 0
)
</script>

<template>
  <div class="dweller-card">
    <div class="portrait-rail">
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
            class="placeholder-icon text-theme-primary opacity-30"
            :class="{ 'animate-spin': generatingPortrait }"
          />
            <span class="placeholder-hint">{{
              generatingPortrait ? 'Generating portrait…' : 'Generate portrait'
            }}</span>
          </button>
        </template>
      </div>

      <div class="stats-container">
        <div class="stat-row">
          <span class="stat-label">Health</span>
          <span class="stat-value">{{
            getHealthDisplay(dweller.health, dweller.max_health, dweller.radiation)
          }}</span>
        </div>
        <HealthRadiationBar
          :value="healthPercentage"
          :radiation="radiationPercentage"
          :height="10"
          glow
        />

        <div class="stat-row happiness-row">
          <span class="stat-label">Happiness</span>
          <div class="happiness-value-container">
            <span class="stat-value" :style="{ color: happinessColor }"
              >{{ dweller.happiness }}%</span
            >
            <HappinessModifierPopover :dweller-id="dweller.id" />
          </div>
        </div>
        <Progress
          class="h-2.5"
          :fill="happinessColor"
          :model-value="dweller.happiness"
        />

        <XPProgressBar :level="dweller.level" :current-x-p="dweller.experience" />

        <div v-if="showInventory" class="supplies">
          <div v-if="showStimpackSection" class="supply-row supply-stimpack">
            <Icon icon="mdi:medical-bag" class="supply-icon" :ariaHidden="true" />
            <span class="supply-name">Stimpack</span>
            <span class="supply-count" :title="`Carrying ${dweller.stimpack || 0} of 15`">
              {{ dweller.stimpack || 0 }}
            </span>
            <div class="supply-actions">
              <Button
                v-if="canUseStimpak"
                variant="outline"
                size="xs"
                aria-label="Use Stimpack"
                title="Use one Stimpak (heals dweller)"
                :disabled="usingStimpak"
                @click="emit('use-stimpak')"
              >
                <Icon v-if="usingStimpak" icon="mdi:loading" class="mr-1 animate-spin" />
                Use
              </Button>
              <Button
                v-if="canIssueStimpack"
                variant="outline"
                size="xs"
                aria-label="Issue Stimpack from vault"
                :title="`Issue one Stimpak from vault (${availableStimpaksCount} available)`"
                :disabled="issuingMedicalSupply"
                @click="emit('issue-medical-supply', 'stimpack')"
              >
                <Icon icon="mdi:plus" class="supply-issue-icon" />
              </Button>
            </div>
          </div>

          <div v-if="showRadawaySection" class="supply-row supply-radaway">
            <Icon icon="mdi:radiation" class="supply-icon" :ariaHidden="true" />
            <span class="supply-name">RadAway</span>
            <span class="supply-count" :title="`Carrying ${dweller.radaway || 0} of 15`">
              {{ dweller.radaway || 0 }}
            </span>
            <div class="supply-actions">
              <Button
                v-if="canUseRadaway"
                variant="outline"
                size="xs"
                aria-label="Use RadAway"
                title="Use one RadAway (reduces radiation)"
                :disabled="usingRadAway"
                @click="emit('use-radaway')"
              >
                <Icon v-if="usingRadAway" icon="mdi:loading" class="mr-1 animate-spin" />
                Use
              </Button>
              <Button
                v-if="canIssueRadaway"
                variant="outline"
                size="xs"
                aria-label="Issue RadAway from vault"
                :title="`Issue one RadAway from vault (${availableRadawaysCount} available)`"
                :disabled="issuingMedicalSupply"
                @click="emit('issue-medical-supply', 'radaway')"
              >
                <Icon icon="mdi:plus" class="supply-issue-icon" />
              </Button>
            </div>
          </div>
        </div>

        <div v-if="dweller.radiation && dweller.radiation > 0" class="stat-row">
          <span class="stat-label">Radiation</span>
          <span class="stat-value text-yellow-400">{{ dweller.radiation }}</span>
        </div>
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
  gap: 1.25rem;
  padding: 1.25rem;
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  box-shadow: 0 0 15px var(--color-theme-glow);
  /* The card is the query container, so the portrait/stats split responds to
     the card's own width rather than the viewport's. */
  container-type: inline-size;
}

/* Portrait and stats share one row while there is room for both. The portrait
   is sized by its own ratio within a height budget, so a square portrait gets
   the full width allowance while a vertical one stays narrow and hands the
   space to the stats. */
.portrait-rail {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

/* Too narrow for two columns: stack, and let the portrait use the full width. */
@container (max-width: 360px) {
  .portrait-rail {
    grid-template-columns: minmax(0, 1fr);
  }

  .portrait-image {
    max-width: 100%;
  }
}

.portrait-container {
  position: relative;
  min-width: 0;
}

.stats-container {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.portrait-image {
  display: block;
  width: auto;
  height: auto;
  max-width: 11rem;
  max-height: 12rem;
  border-radius: 8px;
  border: 2px solid var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
}

/* The placeholder has no intrinsic size to borrow, so it takes a definite box
   matching the image allowance and scales its glyph to the container. */
.portrait-placeholder {
  width: 11rem;
  max-width: 100%;
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
  transition:
    border-color var(--transition-base),
    box-shadow var(--transition-base);
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
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  text-align: center;
}

.placeholder-icon {
  width: 45%;
  height: auto;
  aspect-ratio: 1;
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
  font-size: 0.78rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 3px var(--color-theme-glow);
  opacity: 0.8;
}

.stat-value {
  font-weight: 700;
  font-size: 0.82rem;
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

/* Supplies: one compact row per item, with an action only when that action is
   actually available. */
.supplies {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.45rem 0.6rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  margin-top: 0.25rem;
}

.supply-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.supply-icon {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  opacity: 0.8;
}

.supply-name {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
}

.supply-count {
  font-weight: 700;
  font-size: 0.85rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.supply-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-left: auto;
}

.supply-issue-icon {
  width: 0.85rem;
  height: 0.85rem;
}
</style>
