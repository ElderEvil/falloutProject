<script setup lang="ts">
interface Props {
  S: number
  P: number
  E: number
  C: number
  I: number
  A: number
  L: number
}

defineProps<Props>()

const stats = [
  { key: 'S', label: 'Strength', description: 'Physical power and melee damage' },
  { key: 'P', label: 'Perception', description: 'Accuracy and awareness' },
  { key: 'E', label: 'Endurance', description: 'Health and radiation resistance' },
  { key: 'C', label: 'Charisma', description: 'Trading and breeding success' },
  { key: 'I', label: 'Intelligence', description: 'Crafting and science efficiency' },
  { key: 'A', label: 'Agility', description: 'Speed and weapon reload' },
  { key: 'L', label: 'Luck', description: 'Critical hits and loot quality' }
]
</script>

<template>
  <div class="dweller-stats">
    <h3 class="stats-title">S.P.E.C.I.A.L.</h3>
    <div class="stats-grid">
      <div
        v-for="stat in stats"
        :key="stat.key"
        class="stat-item"
      >
        <div class="stat-header">
          <span class="stat-label">{{ stat.label }}</span>
          <span class="stat-value">{{ ($props as any)[stat.key] || 0 }}</span>
        </div>
        <div class="stat-bar">
          <div
            class="stat-fill"
            :style="{ width: `${(($props as any)[stat.key] || 0) * 10}%` }"
          ></div>
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
</style>
