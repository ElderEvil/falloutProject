<template>
  <div class="children-list">
    <div v-if="children.length === 0" class="empty-state">
      <Icon icon="mdi:human-child" class="empty-icon" />
      <p class="empty-text">No children growing in this vault yet.</p>
      <p class="empty-hint">Partners need to conceive and give birth first!</p>
    </div>

    <div v-else class="children-grid">
      <div v-for="child in children" :key="child.id" class="child-card">
        <div class="child-header">
          <div class="child-info">
            <h3 class="child-name">
              {{ child.first_name }} {{ child.last_name }}
            </h3>
            <div class="child-age-badge">
              <Icon icon="mdi:human-child" class="mr-1" />
              {{ child.age_group }}
            </div>
          </div>
          <Icon icon="mdi:human-child" class="child-avatar-icon" />
        </div>

        <div class="child-details">
          <div class="detail-row">
            <span class="detail-label">Gender:</span>
            <span class="detail-value">{{ (child as any).gender || 'Unknown' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Health:</span>
            <span class="detail-value">{{ child.health }} / {{ child.max_health }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">Happiness:</span>
            <span class="detail-value">{{ child.happiness }}%</span>
          </div>
        </div>

        <div class="growth-info">
          <div class="growth-label">
            <Icon icon="mdi:clock-outline" class="mr-1" />
            Growth Progress
          </div>
          <div class="growth-bar">
            <div class="growth-fill" :style="{ width: '50%' }"></div>
          </div>
          <div class="growth-time">~1.5 hours remaining</div>
        </div>

        <div class="child-stats">
          <div class="special-preview">
            <div class="stat-mini">
              <span class="stat-letter">S</span>
              <span class="stat-val">{{ child.strength }}</span>
            </div>
            <div class="stat-mini">
              <span class="stat-letter">P</span>
              <span class="stat-val">{{ child.perception }}</span>
            </div>
            <div class="stat-mini">
              <span class="stat-letter">E</span>
              <span class="stat-val">{{ child.endurance }}</span>
            </div>
            <div class="stat-mini">
              <span class="stat-letter">C</span>
              <span class="stat-val">{{ child.charisma }}</span>
            </div>
            <div class="stat-mini">
              <span class="stat-letter">I</span>
              <span class="stat-val">{{ child.intelligence }}</span>
            </div>
            <div class="stat-mini">
              <span class="stat-letter">A</span>
              <span class="stat-val">{{ child.agility }}</span>
            </div>
            <div class="stat-mini">
              <span class="stat-letter">L</span>
              <span class="stat-val">{{ child.luck }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

interface Props {
  vaultId: string
}

defineProps<Props>()

const dwellerStore = useDwellerStore()

const children = computed(() =>
  dwellerStore.dwellers.filter(d => d.age_group === 'child')
)
</script>

<style scoped>
.children-list {
  padding: 1rem 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-icon {
  font-size: 4rem;
  color: var(--color-theme-primary);
  opacity: 0.3;
  margin-bottom: 1rem;
}

.empty-text {
  font-size: 1.125rem;
  color: var(--color-theme-primary);
  margin-bottom: 0.5rem;
}

.empty-hint {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.children-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1rem;
}

.child-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 0 10px var(--color-theme-glow);
  transition: all 0.2s;
}

.child-card:hover {
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: translateY(-2px);
}

.child-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--color-theme-glow);
}

.child-info {
  flex: 1;
}

.child-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  margin-bottom: 0.5rem;
}

.child-age-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  background: rgba(0, 255, 0, 0.1);
  border: 1px solid var(--color-theme-primary);
  border-radius: 999px;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
}

.child-avatar-icon {
  font-size: 2.5rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.child-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
}

.detail-label {
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.detail-value {
  color: var(--color-theme-primary);
  font-weight: 600;
}

.growth-info {
  margin: 1rem 0;
}

.growth-label {
  display: flex;
  align-items: center;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  margin-bottom: 0.5rem;
}

.growth-bar {
  width: 100%;
  height: 10px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid var(--color-theme-glow);
  border-radius: 5px;
  overflow: hidden;
}

.growth-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-theme-primary) 0%, var(--color-theme-accent) 100%);
  box-shadow: 0 0 10px var(--color-theme-glow);
  transition: width 0.3s ease;
}

.growth-time {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
  margin-top: 0.25rem;
  text-align: right;
}

.child-stats {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-theme-glow);
}

.special-preview {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
}

.stat-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.stat-letter {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.stat-val {
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 5px var(--color-theme-glow);
}
</style>
