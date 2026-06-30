<script setup lang="ts">
import { computed } from 'vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'

interface Props {
  level: number
  currentXP: number
  maxLevel?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxLevel: 50,
})

// XP formula: 100 * (level ^ 1.5)
const calculateXPRequired = (level: number): number => {
  if (level <= 1) return 0
  return Math.floor(100 * Math.pow(level, 1.5))
}

const requiredXP = computed(() => {
  if (props.level >= props.maxLevel) return 0
  return calculateXPRequired(props.level + 1)
})

const previousLevelXP = computed(() => {
  return calculateXPRequired(props.level)
})

const xpInCurrentLevel = computed(() => {
  return props.currentXP - previousLevelXP.value
})

const xpNeededForNextLevel = computed(() => {
  return requiredXP.value - previousLevelXP.value
})

const progressPercentage = computed(() => {
  if (props.level >= props.maxLevel) return 100
  if (xpNeededForNextLevel.value === 0) return 100
  return Math.min(100, (xpInCurrentLevel.value / xpNeededForNextLevel.value) * 100)
})

const isNearLevelUp = computed(() => progressPercentage.value >= 90)
const isMaxLevel = computed(() => props.level >= props.maxLevel)

const barAnimation = computed(() => {
  if (isMaxLevel.value) return 'shimmer' as const
  if (isNearLevelUp.value) return 'pulse' as const
  return 'none' as const
})
</script>

<template>
  <div class="xp-bar-container">
    <div class="stat-row">
      <span class="stat-label">Experience</span>
      <span class="stat-value" :class="{ 'max-level': isMaxLevel }">
        <template v-if="!isMaxLevel">
          {{ xpInCurrentLevel }} / {{ xpNeededForNextLevel }} XP
        </template>
        <template v-else>MAX LEVEL</template>
      </span>
    </div>
    <UProgressBar :model-value="progressPercentage" :height="10" :animation="barAnimation" />
  </div>
</template>

<style scoped>
.xp-bar-container {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
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

.stat-value.max-level {
  color: rgb(250 204 21);
  text-shadow: 0 0 8px rgb(250 204 21 / 0.6);
}
</style>
