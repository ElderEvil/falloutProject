<script setup lang="ts">
import { computed } from 'vue'
import { Progress } from '@/core/components/ui/progress'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'

interface Props {
  level: number
  currentXP: number
  maxLevel?: number
}

const { maxLevel = 50, currentXP, level } = defineProps<Props>()

// XP formula: 100 * (level ^ 1.5)
const calculateXPRequired = (level: number): number => {
  if (level <= 1) return 0
  return Math.floor(100 * Math.pow(level, 1.5))
}

const requiredXP = computed(() => {
  if (level >= maxLevel) return 0
  return calculateXPRequired(level + 1)
})

const previousLevelXP = computed(() => calculateXPRequired(level))

const xpInCurrentLevel = computed(() => currentXP - previousLevelXP.value)

const xpNeededForNextLevel = computed(() => requiredXP.value - previousLevelXP.value || 1)

const xpToNextLevel = computed(() =>
  level >= maxLevel ? 0 : Math.max(0, requiredXP.value - currentXP)
)

const progressPercentage = computed(() => {
  if (level >= maxLevel) return 100
  return Math.min(100, (xpInCurrentLevel.value / xpNeededForNextLevel.value) * 100)
})

const isMaxLevel = computed(() => level >= maxLevel)

const barAnimation = computed(() => {
  if (isMaxLevel.value) return 'shimmer' as const
  if (progressPercentage.value >= 90) return 'pulse' as const
  return 'none' as const
})

const tooltipText = computed(() =>
  isMaxLevel.value
    ? 'Maximum level reached'
    : `${xpToNextLevel.value} XP to level ${level + 1}`
)

// Amber for the at-risk / max-level states, primary→accent gradient otherwise.
const fillGradient = computed(() =>
  barAnimation.value === 'none'
    ? 'linear-gradient(90deg, var(--color-theme-primary) 0%, var(--color-theme-accent) 100%)'
    : 'linear-gradient(90deg, rgb(250 204 21) 0%, rgb(251 191 36) 50%, rgb(250 204 21) 100%)'
)
</script>

<template>
  <div class="xp-bar-container">
    <div class="stat-row">
      <span class="stat-label">Level {{ level }}</span>
      <TooltipProvider :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <span class="stat-value" :class="{ 'max-level': isMaxLevel }">
              <template v-if="!isMaxLevel">{{ xpToNextLevel }} XP to L{{ level + 1 }}</template>
              <template v-else>MAX</template>
            </span>
          </TooltipTrigger>
          <TooltipContent side="top">{{ tooltipText }}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
    <Progress
      class="xp-progress h-2.5"
      :class="{
        'xp-progress--pulse': barAnimation === 'pulse',
        'xp-progress--shimmer': barAnimation === 'shimmer',
      }"
      :fill="fillGradient"
      :model-value="progressPercentage"
    />
  </div>
</template>

<style scoped>
.xp-progress--pulse :deep([data-slot='progress-indicator']) {
  animation: xp-pulse 1.5s ease-in-out infinite;
}

.xp-progress--shimmer :deep([data-slot='progress-indicator']) {
  background-size: 200% 100%;
  animation: xp-shimmer 3s linear infinite;
}

/* Informational values (glow-0): facts about progress, not calls to action. */
.xp-bar-container {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.stat-label {
  font-weight: 600;
  font-size: 0.78rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  white-space: nowrap;
}

.stat-value {
  font-weight: 700;
  font-size: 0.78rem;
  color: var(--color-theme-primary);
  white-space: nowrap;
}

.stat-value.max-level {
  color: rgb(250 204 21);
}

@keyframes xp-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

@keyframes xp-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
