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
  gap: 1.5rem;
}

.stats-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
  border-bottom: 2px solid rgba(0, 255, 0, 0.3);
  padding-bottom: 0.5rem;
}

.stats-grid {
  display: grid;
  gap: 1rem;
}

.stat-item {
  padding: 0.75rem;
  background: rgba(0, 255, 0, 0.05);
  border-left: 3px solid rgba(0, 255, 0, 0.3);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.stat-item:hover {
  background: rgba(0, 255, 0, 0.08);
  border-left-color: #00ff00;
  box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.375rem;
}

.stat-label {
  font-weight: 600;
  font-size: 0.875rem;
  color: #00ff00;
  text-shadow: 0 0 4px rgba(0, 255, 0, 0.5);
}

.stat-value {
  font-weight: 700;
  font-size: 1rem;
  color: #00ff00;
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.6);
  min-width: 1.75rem;
  text-align: right;
}

.stat-bar {
  position: relative;
  width: 100%;
  height: 10px;
  background: rgba(68, 68, 68, 0.8);
  border: 1px solid rgba(0, 255, 0, 0.3);
  border-radius: 5px;
  overflow: hidden;
  margin-bottom: 0.375rem;
}

.stat-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: linear-gradient(90deg, #00ff00 0%, #00cc00 100%);
  box-shadow: 0 0 8px rgba(0, 255, 0, 0.6);
  transition: width 0.3s ease;
}

.stat-description {
  font-size: 0.8125rem;
  color: rgba(0, 255, 0, 0.7);
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
  line-height: 1.4;
}
</style>
