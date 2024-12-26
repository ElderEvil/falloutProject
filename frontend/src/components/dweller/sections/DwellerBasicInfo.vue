<script setup lang="ts">
import { NProgress } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import type { DwellerFull } from '@/types/dweller.types'

const props = defineProps<{
  dweller: DwellerFull
}>()

const themeStore = useThemeStore()
</script>

<template>
  <div class="dweller-info">
    <div class="info-row">
      <span class="label">LEVEL</span>
      <span class="value">{{ dweller.level }}</span>
    </div>
    <div class="info-row">
      <span class="label">HP</span>
      <NProgress
        type="line"
        :percentage="(dweller.health / dweller.max_health) * 100"
        :color="themeStore.theme.colors.primary"
        :height="12"
      />
      <span class="health-value">{{ dweller.health }}/{{ dweller.max_health }}</span>
    </div>
    <div class="info-row">
      <span class="label">HAPPINESS</span>
      <span class="value">{{ dweller.happiness }}%</span>
    </div>
    <div v-if="dweller.radiation > 0" class="info-row">
      <span class="label">RADIATION</span>
      <span class="value">{{ dweller.radiation }}</span>
    </div>
    <div class="info-row">
      <span class="label">GENDER</span>
      <span class="value">{{ dweller.gender?.toUpperCase() || 'UNKNOWN' }}</span>
    </div>
    <div class="info-row">
      <span class="label">RARITY</span>
      <span class="value">{{ dweller.rarity?.toUpperCase() || 'COMMON' }}</span>
    </div>
  </div>
</template>

<style scoped>
.dweller-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 0.9em;
  opacity: 0.8;
}

.value {
  font-size: 1.2em;
  color: var(--theme-text);
}

.health-value {
  font-size: 0.9em;
  text-align: right;
  margin-top: 4px;
}
</style>
