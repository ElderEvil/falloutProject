<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerBadge from '@/modules/dwellers/components/DwellerBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

interface Props {
  dweller: DwellerShort
  ability: string | null
  showApprentice?: boolean
}

const props = withDefaults(defineProps<Props>(), { showApprentice: false })

const emit = defineEmits<{
  activate: [dwellerId: string]
}>()

const statValue = (ability: string) => {
  const value = props.dweller[ability.toLowerCase() as SpecialKey]
  return typeof value === 'number' ? value : 0
}
</script>

<template>
  <button type="button" class="dweller-card clickable" @click="emit('activate', dweller.id)">
    <DwellerPortrait
      :thumbnail-url="dweller.thumbnail_url"
      :alt="`${dweller.first_name} ${dweller.last_name ?? ''}`"
      image-class="dweller-portrait"
      fallback-class="h-10 w-10 icon-primary"
    />
    <div class="dweller-info">
      <div class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</div>
      <div class="dweller-badges">
        <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
        <DwellerBadge
          v-if="showApprentice && dweller.apprentice_stat"
          icon="mdi:school-outline"
          color="var(--color-warning)"
          :label="`Apprentice · ${dweller.apprentice_stat.toLowerCase()} training`"
          :show-label="false"
          size="sm"
        />
      </div>
      <div class="dweller-level">Level {{ dweller.level }}</div>
    </div>
    <div v-if="ability" class="dweller-stat">
      <span class="stat-label">{{ ability.charAt(0) }}</span>
      <span class="stat-value">{{ statValue(ability) }}</span>
    </div>
  </button>
</template>

<style scoped>
.dweller-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  color: inherit;
  font: inherit;
  text-align: left;
  border-radius: 4px;
  transition: all 0.2s;
}

.dweller-card.clickable {
  cursor: pointer;
}

.dweller-card.clickable:hover,
.dweller-card.clickable:focus-visible {
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
  outline: none;
}

.dweller-portrait {
  width: 48px;
  height: 48px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid var(--color-theme-glow);
}

.dweller-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex: 1;
  min-width: 0;
}

.dweller-name {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--color-theme-primary);
  overflow-wrap: break-word;
}

.dweller-badges {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.dweller-level {
  font-size: 0.75rem;
  color: var(--color-gray-400);
}

.dweller-stat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-sunken);
  border-radius: 4px;
  flex-shrink: 0;
  min-width: 60px;
}

.dweller-stat .stat-label {
  font-weight: bold;
  color: var(--color-warning);
  font-size: 0.875rem;
}

.dweller-stat .stat-value {
  font-size: 1.125rem;
  font-weight: bold;
  color: var(--color-theme-primary);
}
</style>
