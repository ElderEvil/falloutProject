<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import XPProgressBar from '../stats/XPProgressBar.vue'
import HappinessModifierPopover from './HappinessModifierPopover.vue'
import DwellerCardActions from './DwellerCardActions.vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { components } from '@/core/types/api.generated'
import { normalizeImageUrl } from '@/utils/image'

type DwellerDetailRead = components['schemas']['DwellerReadFull']

interface Props {
  dweller: DwellerDetailRead
  imageUrl?: string | null
  loading?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'chat'): void
  (e: 'assign'): void
  (e: 'recall'): void
  (e: 'train'): void
  (e: 'assign-pet'): void
  (e: 'use-stimpack'): void
  (e: 'use-radaway'): void
  (e: 'unassign'): void
}>()

const getImageUrl = (imagePath: string) => {
  return normalizeImageUrl(imagePath)
}

const healthPercentage = computed(() => {
  if (!props.dweller.max_health) return 0
  return (props.dweller.health / props.dweller.max_health) * 100
})

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
      return '#4ade80'
    case 'low':
      return '#fbbf24'
    case 'critical':
      return '#ef4444'
    default:
      return 'var(--color-theme-primary)'
  }
})

const genderIcon = computed(() => {
  return props.dweller.gender === 'male' ? 'mdi:gender-male' : 'mdi:gender-female'
})

const genderColor = computed(() => {
  return props.dweller.gender === 'male' ? '#60a5fa' : '#f472b6'
})

const rarityColor = computed(() => {
  const rarity = props.dweller.rarity?.toLowerCase()
  switch (rarity) {
    case 'legendary':
      return '#fbbf24'
    case 'rare':
      return '#a78bfa'
    case 'uncommon':
      return '#60a5fa'
    case 'common':
    default:
      return '#9ca3af'
  }
})

const rarityLabel = computed(() => {
  return props.dweller.rarity || 'Common'
})

const ageGroupColor = computed(() => {
  const group = props.dweller.age_group
  switch (group) {
    case 'child':
      return '#38bdf8'
    case 'teen':
      return '#818cf8'
    case 'adult':
    default:
      return '#4ade80'
  }
})

const ageGroupIcon = computed(() => {
  const group = props.dweller.age_group
  switch (group) {
    case 'child':
      return 'mdi:baby-face-outline'
    case 'teen':
      return 'mdi:account-school'
    case 'adult':
    default:
      return 'mdi:account'
  }
})
</script>

<template>
  <div class="dweller-card">
    <div class="portrait-container">
      <template v-if="imageUrl">
        <img :src="getImageUrl(imageUrl)" alt="Dweller Portrait" class="portrait-image" />
      </template>
      <template v-else>
        <div class="portrait-placeholder">
          <Icon
            icon="mdi:account-circle"
            class="h-48 w-48"
            style="color: var(--color-theme-primary); opacity: 0.3"
          />
          <p class="placeholder-hint">Generate portrait in Appearance tab</p>
        </div>
      </template>
    </div>

    <div class="info-badges">
      <div class="info-badge gender-badge" :style="{ borderColor: genderColor }">
        <Icon :icon="genderIcon" class="badge-icon" :style="{ color: genderColor }" />
        <span class="badge-text" :style="{ color: genderColor }">{{ dweller.gender }}</span>
      </div>
      <div class="info-badge rarity-badge" :style="{ borderColor: rarityColor }">
        <Icon icon="mdi:star" class="badge-icon" :style="{ color: rarityColor }" />
        <span class="badge-text" :style="{ color: rarityColor }">{{ rarityLabel }}</span>
      </div>
      <div
        v-if="dweller.age_group !== 'adult'"
        class="info-badge age-badge"
        :style="{ borderColor: ageGroupColor }"
      >
        <Icon :icon="ageGroupIcon" class="badge-icon" :style="{ color: ageGroupColor }" />
        <span class="badge-text" :style="{ color: ageGroupColor }">{{ dweller.age_group }}</span>
      </div>
    </div>

    <div class="stats-container">
      <div class="stat-row">
        <span class="stat-label">Level</span>
        <span class="stat-value">{{ dweller.level }}</span>
      </div>

      <div class="stat-row">
        <span class="stat-label">Health</span>
        <span class="stat-value">{{ dweller.health }} / {{ dweller.max_health }}</span>
      </div>
      <UProgressBar :model-value="healthPercentage" :height="10" />

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
          <Icon icon="mdi:medical-bag" class="h-5 w-5 text-green-500" />
          <span class="inventory-value">{{ dweller.stimpack || 0 }}</span>
          <span class="inventory-label">Stimpack</span>
        </div>
        <div class="inventory-item">
          <Icon icon="mdi:radiation" class="h-5 w-5 text-yellow-500" />
          <span class="inventory-value">{{ dweller.radaway || 0 }}</span>
          <span class="inventory-label">RadAway</span>
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
      @assign-pet="emit('assign-pet')"
      @use-stimpack="emit('use-stimpack')"
      @use-radaway="emit('use-radaway')"
      @unassign="emit('unassign')"
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

.info-badge {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(0, 0, 0, 0.4);
  border: 2px solid;
  border-radius: 999px;
  font-family: 'Courier New', monospace;
  font-weight: 600;
  font-size: 0.875rem;
  text-transform: capitalize;
  box-shadow: 0 0 10px currentColor;
  transition: all 0.2s;
}

.info-badge:hover {
  transform: translateY(-2px);
  box-shadow: 0 0 20px currentColor;
}

.badge-icon {
  font-size: 1.25rem;
  filter: drop-shadow(0 0 4px currentColor);
}

.badge-text {
  font-weight: 700;
  text-shadow: 0 0 8px currentColor;
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
  gap: 1rem;
  justify-content: space-around;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  margin-top: 0.5rem;
}

.inventory-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.inventory-value {
  font-weight: 700;
  font-size: 1.125rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.inventory-label {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
</style>
