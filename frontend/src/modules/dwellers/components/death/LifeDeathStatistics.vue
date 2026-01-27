<script setup lang="ts">
/**
 * LifeDeathStatistics - Visualization of vault mortality data
 * @component
 */
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UCard, USkeleton } from '@/core/components/ui'
import type { DeathStatistics } from '@/modules/profile/stores/profile'

interface Props {
  statistics: DeathStatistics | null
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const mortalityRate = computed(() => {
  if (!props.statistics || props.statistics.total_dwellers_born === 0) return 0
  return (
    (props.statistics.total_dwellers_died / props.statistics.total_dwellers_born) *
    100
  ).toFixed(1)
})

const causeData = computed(() => {
  if (!props.statistics) return []
  const causes = props.statistics.deaths_by_cause
  const total = props.statistics.total_dwellers_died || 1 // Avoid division by zero

  return [
    {
      id: 'health',
      label: 'Natural Causes',
      count: causes.health,
      icon: 'mdi:heart-broken',
      color: 'text-pink-500',
    },
    {
      id: 'radiation',
      label: 'Radiation',
      count: causes.radiation,
      icon: 'mdi:radioactive',
      color: 'text-green-400',
    },
    {
      id: 'incident',
      label: 'Incidents',
      count: causes.incident,
      icon: 'mdi:fire',
      color: 'text-orange-500',
    },
    {
      id: 'exploration',
      label: 'Exploration',
      count: causes.exploration,
      icon: 'mdi:compass',
      color: 'text-yellow-500',
    },
    {
      id: 'combat',
      label: 'Combat',
      count: causes.combat,
      icon: 'mdi:sword',
      color: 'text-red-500',
    },
  ].map((item) => ({
    ...item,
    percentage: ((item.count / total) * 100).toFixed(1),
  }))
})
</script>

<template>
  <UCard title="VITAL STATISTICS REGISTRY" glow crt class="life-death-stats">
    <div v-if="loading" class="space-y-4">
      <div class="grid grid-cols-3 gap-4">
        <USkeleton class="h-24 w-full" />
        <USkeleton class="h-24 w-full" />
        <USkeleton class="h-24 w-full" />
      </div>
      <USkeleton class="h-40 w-full" />
    </div>

    <div v-else-if="statistics" class="space-y-6">
      <!-- High Level Stats -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- Births -->
        <div
          class="bg-black/40 border border-theme-primary/30 p-3 rounded flex flex-col items-center justify-center text-center"
        >
          <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-1">
            Total Births
          </div>
          <div class="text-3xl font-bold text-theme-primary flex items-center gap-2">
            <Icon icon="mdi:baby-carriage" class="w-6 h-6 opacity-80" />
            {{ statistics.total_dwellers_born }}
          </div>
        </div>

        <!-- Deaths -->
        <div
          class="bg-black/40 border border-theme-primary/30 p-3 rounded flex flex-col items-center justify-center text-center"
        >
          <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-1">
            Total Deaths
          </div>
          <div class="text-3xl font-bold text-red-500 flex items-center gap-2">
            <Icon icon="mdi:skull" class="w-6 h-6 opacity-80" />
            {{ statistics.total_dwellers_died }}
          </div>
        </div>

        <!-- Mortality Rate -->
        <div
          class="bg-black/40 border border-theme-primary/30 p-3 rounded flex flex-col items-center justify-center text-center"
        >
          <div class="text-xs text-theme-primary/60 uppercase tracking-wider mb-1">
            Mortality Rate
          </div>
          <div
            class="text-3xl font-bold flex items-center gap-2"
            :class="Number(mortalityRate) > 50 ? 'text-red-500' : 'text-theme-primary'"
          >
            <Icon icon="mdi:chart-line" class="w-6 h-6 opacity-80" />
            {{ mortalityRate }}%
          </div>
        </div>
      </div>

      <!-- Death Causes Breakdown -->
      <div class="border-t border-theme-primary/20 pt-4">
        <h4 class="text-sm font-bold text-theme-primary uppercase mb-4 flex items-center gap-2">
          <Icon icon="mdi:file-chart" />
          Casualty Analysis
        </h4>

        <div class="space-y-3">
          <div v-for="cause in causeData" :key="cause.id" class="flex items-center gap-3 group">
            <div
              class="w-8 h-8 rounded flex items-center justify-center bg-black border border-theme-primary/30 shrink-0"
            >
              <Icon :icon="cause.icon" class="w-5 h-5" :class="cause.color" />
            </div>

            <div class="flex-1 min-w-0">
              <div class="flex justify-between items-end mb-1">
                <span
                  class="text-sm font-medium text-theme-primary group-hover:text-theme-glow transition-colors"
                >
                  {{ cause.label }}
                </span>
                <div class="flex items-center gap-2">
                  <span class="text-xs text-theme-primary/60">{{ cause.count }}</span>
                  <span class="text-xs font-mono text-theme-primary/40 w-10 text-right"
                    >{{ cause.percentage }}%</span
                  >
                </div>
              </div>

              <div
                class="h-1.5 bg-gray-900 rounded-full overflow-hidden border border-theme-primary/20"
              >
                <div
                  class="h-full w-[var(--width)] bg-theme-primary/60 group-hover:bg-theme-primary transition-all duration-500 shadow-[0_0_5px_currentColor]"
                  :style="{ '--width': `${cause.percentage}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Status Summary -->
      <div class="grid grid-cols-2 gap-4 pt-2">
        <div
          class="flex items-center justify-between p-2 bg-theme-primary/10 rounded border border-theme-primary/30"
        >
          <span class="text-xs uppercase text-theme-primary/80">Revivable Subjects</span>
          <span class="font-bold font-mono text-lg text-theme-primary">{{
            statistics.revivable_count
          }}</span>
        </div>

        <div
          class="flex items-center justify-between p-2 bg-red-900/10 rounded border border-red-500/30"
        >
          <span class="text-xs uppercase text-red-400/80">Permanent Casualties</span>
          <span class="font-bold font-mono text-lg text-red-500">{{
            statistics.permanently_dead_count
          }}</span>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-8 text-theme-primary/40 font-mono text-sm">
      NO MORTALITY DATA AVAILABLE
    </div>
  </UCard>
</template>

<style scoped>
/* Scoped styles */
</style>
