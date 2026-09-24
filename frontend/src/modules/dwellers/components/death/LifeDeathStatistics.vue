<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import { Skeleton } from '@/core/components/ui/skeleton'
import type { DeathStatistics } from '@/core/types/death'

interface Props {
  statistics: DeathStatistics | null
  totalDwellersCreated: number
  loading?: boolean
}

const { loading = false, statistics, totalDwellersCreated } = defineProps<Props>()

const mortalityRate = computed(() => {
  if (!statistics || totalDwellersCreated === 0 || totalDwellersCreated < statistics.total_dwellers_died) return null
  return ((statistics.total_dwellers_died / totalDwellersCreated) * 100).toFixed(1)
})

const isEmpty = computed(() => {
  if (!statistics) return false
  return statistics.total_dwellers_born === 0 && statistics.total_dwellers_died === 0
})

const causeData = computed(() => {
  if (!statistics) return []
  const causes = statistics.deaths_by_cause
  const total = statistics.total_dwellers_died || 1

  return [
    {
      id: 'health',
      label: 'Natural Causes',
      count: causes.health,
      icon: 'mdi:heart-broken',
    },
    {
      id: 'radiation',
      label: 'Radiation',
      count: causes.radiation,
      icon: 'mdi:radioactive',
    },
    {
      id: 'incident',
      label: 'Incidents',
      count: causes.incident,
      icon: 'mdi:fire',
    },
    {
      id: 'exploration',
      label: 'Exploration',
      count: causes.exploration,
      icon: 'mdi:compass',
    },
    {
      id: 'combat',
      label: 'Combat',
      count: causes.combat,
      icon: 'mdi:sword',
    },
  ].map((item) => ({
    ...item,
    percentage: ((item.count / total) * 100).toFixed(1),
  }))
})
</script>

<template>
  <Card
    class="life-death-stats gap-0 border-theme-primary/20 bg-surface p-6"
  >
    <div class="mb-5">
      <h3 class="text-xl font-bold text-theme-primary">Vital statistics</h3>
    </div>
    <div v-if="loading" class="space-y-4">
      <div class="grid grid-cols-3 gap-4">
        <Skeleton class="h-24 w-full" />
        <Skeleton class="h-24 w-full" />
        <Skeleton class="h-24 w-full" />
      </div>
      <Skeleton class="h-40 w-full" />
    </div>

    <div v-else-if="statistics" class="space-y-6">
      <div
        v-if="isEmpty"
        class="text-center py-8 text-theme-primary/70 font-mono text-sm"
      >
        <Icon icon="mdi:clipboard-text-off-outline" class="h-10 w-10 mx-auto mb-3 opacity-50" />
        <p>No activity recorded yet.</p>
      </div>

      <template v-else>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            class="bg-surface-sunken border border-theme-primary/25 p-4 rounded-lg flex flex-col items-center justify-center text-center"
          >
            <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-1">
              Children Born
            </div>
            <div class="text-3xl font-bold text-theme-primary flex items-center gap-2">
              <Icon icon="mdi:baby-carriage" class="w-6 h-6 text-theme-primary/70" />
              {{ statistics.total_dwellers_born }}
            </div>
            <p class="mt-1 text-xs text-theme-primary/60">Through breeding</p>
          </div>

          <div
            class="bg-surface-sunken border border-theme-primary/25 p-4 rounded-lg flex flex-col items-center justify-center text-center"
          >
            <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-1">
              Total Deaths
            </div>
            <div class="text-3xl font-bold text-theme-primary flex items-center gap-2">
              <Icon icon="mdi:skull" class="w-6 h-6 text-theme-primary/70" />
              {{ statistics.total_dwellers_died }}
            </div>
          </div>

          <div
            class="bg-surface-sunken border border-theme-primary/25 p-4 rounded-lg flex flex-col items-center justify-center text-center"
          >
            <div class="text-xs text-theme-primary/70 uppercase tracking-wider mb-1">
              Mortality Rate
            </div>
            <div class="text-3xl font-bold text-theme-primary flex items-center gap-2">
              <Icon icon="mdi:chart-line" class="w-6 h-6 text-theme-primary/70" />
              {{ mortalityRate === null ? '—' : `${mortalityRate}%` }}
            </div>
            <p class="mt-1 text-xs text-theme-primary/60">
              {{ mortalityRate === null ? 'Lifetime data unavailable' : 'Deaths / all dwellers created' }}
            </p>
          </div>
        </div>

        <div class="border-t border-theme-primary/20 pt-4">
          <h4 class="text-sm font-bold text-theme-primary uppercase mb-4 flex items-center gap-2">
            <Icon icon="mdi:file-chart" />
            Casualty Analysis
          </h4>

          <div class="space-y-3">
            <div v-for="cause in causeData" :key="cause.id" class="flex items-center gap-3">
              <div
                class="w-8 h-8 rounded flex items-center justify-center bg-surface-sunken border border-theme-primary/25 shrink-0"
              >
                <Icon :icon="cause.icon" class="w-5 h-5 text-theme-primary/70" />
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex justify-between items-end mb-1">
                  <span class="text-sm font-medium text-theme-primary/80">
                    {{ cause.label }}
                  </span>
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-theme-primary/70">{{ cause.count }}</span>
                    <span class="text-xs font-mono text-theme-primary/60 w-10 text-right"
                      >{{ cause.percentage }}%</span
                    >
                  </div>
                </div>

                <Progress :model-value="Number(cause.percentage)" class="h-1.5" />
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 gap-4 pt-2 sm:grid-cols-2">
          <div
            class="flex items-center gap-3 p-3 bg-surface-sunken rounded-lg border border-theme-primary/25"
          >
            <Icon icon="mdi:heart-plus" class="h-6 w-6 text-theme-primary/70 shrink-0" />
            <div class="flex-1 min-w-0">
              <div class="text-xs text-theme-primary/70 uppercase tracking-wider">
                Revivable Subjects
              </div>
              <div class="text-2xl font-bold font-mono text-theme-primary">
                {{ statistics.revivable_count }}
              </div>
            </div>
          </div>

          <div
            class="flex items-center gap-3 p-3 bg-surface-sunken rounded-lg border border-theme-primary/25"
          >
            <Icon icon="mdi:grave-stone" class="h-6 w-6 text-theme-primary/70 shrink-0" />
            <div class="flex-1 min-w-0">
              <div class="text-xs text-theme-primary/70 uppercase tracking-wider">
                Permanent Casualties
              </div>
              <div class="text-2xl font-bold font-mono text-theme-primary">
                {{ statistics.permanently_dead_count }}
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <div v-else class="text-center py-8 text-theme-primary/40 font-mono text-sm">
      No vital statistics available yet.
    </div>
  </Card>
</template>

<style scoped>
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0s !important;
    animation-duration: 0s !important;
  }
}
</style>
