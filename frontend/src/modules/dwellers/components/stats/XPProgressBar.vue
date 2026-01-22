<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  level: number
  currentXP: number
  maxLevel?: number
}

const props = withDefaults(defineProps<Props>(), {
  maxLevel: 50
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
    <div class="xp-bar" :class="{ 'near-level-up': isNearLevelUp, 'max-level': isMaxLevel }">
      <div class="xp-fill" :style="{ width: `${progressPercentage}%` }"></div>
    </div>
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

.xp-bar {
  width: 100%;
  height: 10px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 5px;
  overflow: hidden;
}

.xp-bar.near-level-up {
  border-color: rgb(250 204 21 / 0.8);
  box-shadow: 0 0 8px rgb(250 204 21 / 0.4);
  animation: pulse 1.5s ease-in-out infinite;
}

.xp-bar.max-level {
  border-color: rgb(250 204 21);
  box-shadow: 0 0 12px rgb(250 204 21 / 0.5);
}

.xp-fill {
  height: 100%;
  background: linear-gradient(90deg, rgb(250 204 21) 0%, rgb(234 179 8) 50%, rgb(250 204 21) 100%);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: width 0.3s ease;
}

.xp-bar.max-level .xp-fill {
  background: linear-gradient(90deg, rgb(250 204 21) 0%, rgb(251 191 36) 50%, rgb(250 204 21) 100%);
  background-size: 200% 100%;
  animation: shimmer 3s linear infinite;
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 8px rgb(250 204 21 / 0.4);
  }
  50% {
    box-shadow: 0 0 16px rgb(250 204 21 / 0.8);
  }
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
