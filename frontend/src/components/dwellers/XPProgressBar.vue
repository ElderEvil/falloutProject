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
    <div class="xp-labels">
      <span class="level-label">Lvl {{ level }}</span>
      <span v-if="!isMaxLevel" class="xp-label">
        {{ xpInCurrentLevel }} / {{ xpNeededForNextLevel }} XP
      </span>
      <span v-else class="xp-label max-level">MAX LEVEL</span>
      <span v-if="!isMaxLevel" class="percentage">{{ progressPercentage.toFixed(1) }}%</span>
    </div>
    <div class="xp-bar" :class="{ 'near-level-up': isNearLevelUp, 'max-level': isMaxLevel }">
      <div class="xp-fill" :style="{ width: `${progressPercentage}%` }">
        <div class="xp-shine"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.xp-bar-container {
  margin-top: 0.5rem;
  width: 100%;
}

.xp-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.level-label {
  font-weight: bold;
  color: rgb(250 204 21);
}

.xp-label {
  flex: 1;
  text-align: center;
  color: var(--color-theme-primary);
  opacity: 0.8;
}

.xp-label.max-level {
  color: rgb(250 204 21);
  font-weight: bold;
  text-shadow: 0 0 8px rgb(250 204 21 / 0.5);
}

.percentage {
  color: var(--color-theme-primary);
  opacity: 0.9;
  font-size: 0.7rem;
}

.xp-bar {
  height: 0.75rem;
  background: linear-gradient(to bottom, rgb(0 0 0 / 0.8), rgb(0 0 0 / 0.6));
  border: 1px solid var(--color-theme-glow);
  border-radius: 2px;
  overflow: hidden;
  position: relative;
  box-shadow: inset 0 1px 3px rgb(0 0 0 / 0.5);
}

.xp-bar.near-level-up {
  border-color: rgb(250 204 21 / 0.8);
  box-shadow: 0 0 8px rgb(250 204 21 / 0.4), inset 0 1px 3px rgb(0 0 0 / 0.5);
  animation: pulse 1.5s ease-in-out infinite;
}

.xp-bar.max-level {
  border-color: rgb(250 204 21);
  background: linear-gradient(to bottom, rgb(250 204 21 / 0.2), rgb(250 204 21 / 0.1));
  box-shadow: 0 0 12px rgb(250 204 21 / 0.5), inset 0 1px 3px rgb(0 0 0 / 0.5);
}

.xp-fill {
  height: 100%;
  background: linear-gradient(
    to right,
    rgb(250 204 21),
    rgb(234 179 8),
    rgb(250 204 21)
  );
  transition: width 0.5s ease-out;
  position: relative;
  box-shadow: 0 0 8px rgb(250 204 21 / 0.6);
}

.xp-bar.max-level .xp-fill {
  background: linear-gradient(
    to right,
    rgb(250 204 21),
    rgb(251 191 36),
    rgb(250 204 21),
    rgb(251 191 36),
    rgb(250 204 21)
  );
  background-size: 200% 100%;
  animation: shimmer 3s linear infinite;
}

.xp-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 100%
  );
  animation: shine 3s ease-in-out infinite;
}

@keyframes shine {
  0% {
    left: -100%;
  }
  50%,
  100% {
    left: 200%;
  }
}

@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 0 8px rgb(250 204 21 / 0.4), inset 0 1px 3px rgb(0 0 0 / 0.5);
  }
  50% {
    box-shadow: 0 0 16px rgb(250 204 21 / 0.8), inset 0 1px 3px rgb(0 0 0 / 0.5);
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
