<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import HealthRadiationBar from '@/core/components/common/HealthRadiationBar.vue'
import { Progress } from '@/core/components/ui/progress'
import { getEffectiveMaxHealth, getHealthDisplay, getRadiationPercentage } from '@/modules/dwellers/models/dweller'
import type { Dweller, DetailedDweller } from '@/modules/dwellers/models/dweller'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import ExplorationStatusBadges from './ExplorationStatusBadges.vue'

const props = defineProps<{
  dwellerName: string
  dwellerImageUrl?: string | null
  dwellerThumbnailUrl?: string | null
  dwellerLevel: number
  health: number
  maxHealth: number
  radiation?: number | null
  progressPercentage: number
  timeRemaining: string
  explorationDuration: number
  isReturning?: boolean
  exploration: Exploration
  dweller?: Dweller | DetailedDweller | null
}>()

const radiationPercentage = computed(() => getRadiationPercentage(props.radiation, props.maxHealth))
const healthPercentage = computed(
  () =>
    (Math.min(props.health, getEffectiveMaxHealth(props.radiation, props.maxHealth)) /
      props.maxHealth) *
    100
)
</script>

<template>
  <div
    class="mb-4 rounded-lg border-2 border-theme-primary bg-terminal-background p-4 shadow-[0_0_20px_var(--color-theme-glow)]"
  >
    <!-- Dweller Portrait Card -->
    <div
      class="mb-4 flex gap-4 border-b-2 border-theme-primary/30 pb-4 max-md:flex-col max-md:items-center max-md:text-center"
    >
      <div
        class="relative flex h-[70px] w-[70px] shrink-0 items-center justify-center rounded-md border-2 border-theme-primary bg-terminal-background shadow-[0_0_15px_var(--color-theme-glow)]"
      >
        <DwellerPortrait
          :image-url="dwellerImageUrl"
          :thumbnail-url="dwellerThumbnailUrl"
          prefer-thumbnail
          :alt="`${dwellerName} portrait`"
          image-class="dweller-portrait h-full w-full rounded-md object-cover"
          fallback-class="h-[45px] w-[45px] text-theme-primary drop-shadow-[0_0_8px_var(--color-theme-glow)]"
        />
        <div
          class="absolute -bottom-1.5 -right-1.5 rounded-[3px] bg-theme-primary px-2 py-1 text-xs font-bold text-black shadow-[0_0_10px_var(--color-theme-glow)]"
        >
          LVL {{ dwellerLevel }}
        </div>
      </div>
      <div class="flex flex-1 flex-col justify-center">
        <h2
          class="mb-2 text-xl font-bold text-theme-primary [text-shadow:0_0_10px_var(--color-theme-glow)] max-md:text-2xl"
        >
          {{ dwellerName }}
        </h2>
        <ExplorationStatusBadges :exploration="exploration" :dweller="dweller" class="mb-2" />
        <div class="flex flex-col gap-1">
          <div class="flex items-center gap-2">
            <span class="min-w-[50px] text-xs text-theme-primary/80">Health</span>
            <HealthRadiationBar
              :value="healthPercentage"
              :radiation="radiationPercentage"
              :height="12"
              aria-label="Health"
            />
            <span class="min-w-[60px] shrink-0 whitespace-nowrap text-right text-xs font-bold text-theme-primary">{{
              getHealthDisplay(health, maxHealth, radiation)
            }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Progress Section -->
    <div class="mb-4">
      <h3
        class="mb-2 flex items-center text-base font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
      >
        <Icon :icon="isReturning ? 'mdi:home-import-outline' : 'mdi:compass'" class="mr-2" />
        {{ isReturning ? 'Returning Home' : 'Exploring Wasteland' }} - {{ explorationDuration }}h
      </h3>
      <Progress
        class="mb-2 h-5"
        :model-value="progressPercentage"
        segmented
        label="Exploration progress"
        :value-text="`${Math.round(progressPercentage)}%`"
      />
      <div class="flex justify-between text-sm font-bold">
        <span class="text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]"
          >{{ Math.round(progressPercentage) }}% {{ isReturning ? 'home' : 'Complete' }}</span
        >
        <span class="text-theme-primary/80">{{ timeRemaining }}</span>
      </div>
    </div>
  </div>
</template>
