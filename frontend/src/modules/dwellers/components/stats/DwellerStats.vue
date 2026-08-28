<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

interface Props {
  S: number
  P: number
  E: number
  C: number
  I: number
  A: number
  L: number
  highlightStat?: string
}

const props = defineProps<Props>()

const statValue = (key: keyof Props): number => (props[key] as number) ?? 0

const stats: Array<{ key: keyof Props; label: string; description: string }> = [
  { key: 'S', label: 'Strength', description: 'Physical power and melee damage' },
  { key: 'P', label: 'Perception', description: 'Accuracy and awareness' },
  { key: 'E', label: 'Endurance', description: 'Health and radiation resistance' },
  { key: 'C', label: 'Charisma', description: 'Trading and breeding success' },
  { key: 'I', label: 'Intelligence', description: 'Crafting and science efficiency' },
  { key: 'A', label: 'Agility', description: 'Speed and weapon reload' },
  { key: 'L', label: 'Luck', description: 'Critical hits and loot quality' },
]

const statKeyByLowercase: Record<string, keyof Props> = {
  strength: 'S',
  perception: 'P',
  endurance: 'E',
  charisma: 'C',
  intelligence: 'I',
  agility: 'A',
  luck: 'L',
}

const highlightedKey = computed<keyof Props | undefined>(() => {
  if (!props.highlightStat) return undefined
  return statKeyByLowercase[props.highlightStat.toLowerCase()]
})

const showBadge = ref(!!highlightedKey.value)
let badgeTimer: ReturnType<typeof setTimeout> | undefined

watch(
  highlightedKey,
  (stat) => {
    clearTimeout(badgeTimer)
    showBadge.value = !!stat
    if (stat) badgeTimer = setTimeout(() => (showBadge.value = false), 2500)
  },
  { immediate: true }
)
onBeforeUnmount(() => clearTimeout(badgeTimer))

const isHighlighted = (key: keyof Props) => highlightedKey.value === key
</script>

<template>
  <div class="dweller-stats">
    <h3 class="stats-title">S.P.E.C.I.A.L.</h3>
    <div class="stats-grid">
      <div
        v-for="stat in stats"
        :key="stat.key"
        class="stat-item"
        :class="{ 'stat-highlighted': isHighlighted(stat.key) }"
      >
        <div class="stat-header">
          <span class="stat-label">{{ stat.label }}</span>
          <span class="stat-value-group">
            <span class="stat-value">{{ statValue(stat.key) }}</span>
            <span v-if="isHighlighted(stat.key) && showBadge" class="stat-badge">+1</span>
          </span>
        </div>
        <div class="stat-bar">
          <div class="stat-fill" :style="{ width: `${statValue(stat.key) * 10}%` }"></div>
        </div>
        <p class="stat-description">{{ stat.description }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dweller-stats {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.stats-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  border-bottom: 2px solid var(--color-theme-glow);
  padding-bottom: 0.375rem;
}

.stats-grid {
  display: grid;
  gap: 0.5rem;
}

.stat-item {
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-left: 2px solid var(--color-theme-glow);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.stat-item:hover {
  background: rgba(0, 0, 0, 0.5);
  border-left-color: var(--color-theme-primary);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.stat-label {
  font-weight: 600;
  font-size: 0.8125rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.stat-value {
  font-weight: 700;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
  min-width: 1.5rem;
  text-align: right;
}

.stat-bar {
  position: relative;
  width: 100%;
  height: 8px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.25rem;
}

.stat-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: width 0.3s ease;
}

.stat-description {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
  text-shadow: 0 0 2px var(--color-theme-glow);
  line-height: 1.3;
}

.stat-value-group {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}

.stat-badge {
  font-size: 0.6875rem;
  font-weight: 700;
  color: var(--color-theme-accent);
  text-shadow: 0 0 6px var(--color-theme-glow);
  animation: badge-fade 2.5s ease-out forwards;
}

.stat-highlighted {
  border-left-color: var(--color-theme-accent);
  background: rgba(0, 255, 0, 0.06);
  animation: stat-pulse 2.5s ease-out forwards;
}

@keyframes stat-pulse {
  0% {
    box-shadow: 0 0 12px var(--color-theme-glow);
    filter: brightness(1.3);
  }
  40% {
    box-shadow:
      0 0 20px var(--color-theme-glow),
      0 0 30px var(--color-theme-glow);
    filter: brightness(1.5);
  }
  100% {
    box-shadow: 0 0 6px var(--color-theme-glow);
    filter: brightness(1);
  }
}

@keyframes badge-fade {
  0% {
    opacity: 1;
    transform: translateY(0);
  }
  70% {
    opacity: 1;
    transform: translateY(0);
  }
  100% {
    opacity: 0;
    transform: translateY(-4px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stat-highlighted {
    animation: none;
    box-shadow: 0 0 12px var(--color-theme-glow);
  }

  .stat-badge {
    animation: none;
    opacity: 1;
  }
}
</style>
