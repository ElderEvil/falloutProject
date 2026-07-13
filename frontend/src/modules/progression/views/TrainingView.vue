<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import TrainingQueuePanel from '@/modules/progression/components/training/TrainingQueuePanel.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSidePanel } from '@/core/composables/useSidePanel'
import PageHeader from '@/core/components/common/PageHeader.vue'

const route = useRoute()
const vaultStore = useVaultStore()
const authStore = useAuthStore()
const { isCollapsed } = useSidePanel()

const vaultId = route.params.id as string

const showInfo = ref(false)

onMounted(async () => {
  if (authStore.token && vaultId) {
    // Ensure vault is loaded - loadVault handles the check internally
    await vaultStore.loadVault(vaultId, authStore.token)
  }
})
</script>

<template>
  <div class="training-layout">
    <SidePanel />

    <div class="training-view" :class="{ collapsed: isCollapsed }">
      <PageHeader
        title="Training Center"
        icon="mdi:dumbbell"
        subtitle="Monitor and manage SPECIAL stat training across your vault"
      />

      <div class="training-content">
        <div class="main-panel">
          <TrainingQueuePanel />
        </div>

        <div class="info-panel">
          <button class="info-toggle" @click="showInfo = !showInfo">
            <div class="toggle-left">
              <Icon icon="mdi:information-outline" class="toggle-icon" />
              <span class="toggle-label">Training Reference</span>
            </div>
            <div class="toggle-right">
              <span class="section-count">3 sections</span>
              <Icon icon="mdi:chevron-down" class="chevron" :class="{ rotated: showInfo }" />
            </div>
          </button>

          <template v-if="showInfo">
            <div class="info-card">
              <Icon icon="mdi:information" class="info-icon" />
              <h3 class="info-title">About Training</h3>
              <div class="info-text">
                <p>
                  Dwellers can train their SPECIAL stats in dedicated training rooms. Each stat has
                  its own training room type:
                </p>
                <ul class="stat-list">
                  <li><Icon icon="mdi:arm-flex" /> <strong>Strength</strong> - Weight Room</li>
                  <li><Icon icon="mdi:eye" /> <strong>Perception</strong> - Armory</li>
                  <li><Icon icon="mdi:heart" /> <strong>Endurance</strong> - Fitness Room</li>
                  <li><Icon icon="mdi:account-voice" /> <strong>Charisma</strong> - Lounge</li>
                  <li><Icon icon="mdi:brain" /> <strong>Intelligence</strong> - Classroom</li>
                  <li><Icon icon="mdi:run-fast" /> <strong>Agility</strong> - Athletics Room</li>
                  <li><Icon icon="mdi:clover" /> <strong>Luck</strong> - Game Room</li>
                </ul>
              </div>
            </div>

            <div class="info-card">
              <Icon icon="mdi:clock-time-four" class="info-icon" />
              <h3 class="info-title">Training Duration</h3>
              <div class="info-text">
                <p>Training takes time based on the current stat level:</p>
                <ul class="duration-list">
                  <li><strong>Base Duration:</strong> 2 hours</li>
                  <li><strong>Scaling:</strong> +30 minutes per current stat level</li>
                  <li><strong>Tier 2 Rooms:</strong> 25% faster</li>
                  <li><strong>Tier 3 Rooms:</strong> 40% faster</li>
                </ul>
                <p class="example">
                  <Icon icon="mdi:lightbulb" />
                  <em
                    >Example: Training from 5→6 takes 4.5 hours (or 2.7 hours in a Tier 3 room)</em
                  >
                </p>
              </div>
            </div>

            <div class="info-card">
              <Icon icon="mdi:star" class="info-icon" />
              <h3 class="info-title">Tips & Tricks</h3>
              <div class="info-text">
                <ul class="tips-list">
                  <li>
                    <Icon icon="mdi:check-circle" class="tip-icon" />
                    SPECIAL stats cap at 10 - can't train beyond maximum
                  </li>
                  <li>
                    <Icon icon="mdi:check-circle" class="tip-icon" />
                    Dwellers earn XP while training (50 XP per hour)
                  </li>
                  <li>
                    <Icon icon="mdi:check-circle" class="tip-icon" />
                    Higher tier rooms train faster - upgrade when possible
                  </li>
                  <li>
                    <Icon icon="mdi:check-circle" class="tip-icon" />
                    Training rooms have limited capacity - plan accordingly
                  </li>
                  <li>
                    <Icon icon="mdi:check-circle" class="tip-icon" />
                    You can cancel training anytime without penalty
                  </li>
                </ul>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.training-layout {
  display: flex;
  min-height: 100vh;
}

.training-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1.5rem;
  gap: 1.5rem;
  overflow: hidden;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  flex: 1;
}

.training-view.collapsed {
  margin-left: 64px;
}

.training-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  flex: 1;
  overflow: hidden;
}

@media (max-width: 1280px) {
  .training-content {
    grid-template-columns: 1fr;
  }

  .info-panel {
    display: none;
  }
}

.main-panel {
  min-height: 0;
}

.info-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
}

.info-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0.75rem 1rem;
  background: transparent;
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.info-toggle:hover {
  border-color: var(--color-theme-accent);
  box-shadow: 0 0 15px var(--color-theme-accent);
}

.toggle-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.toggle-icon {
  font-size: 1.25rem;
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.toggle-label {
  font-size: 0.875rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.toggle-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.section-count {
  font-size: 0.75rem;
  opacity: 0.6;
}

.chevron {
  font-size: 1.25rem;
  transition: transform 0.2s ease;
}

.chevron.rotated {
  transform: rotate(180deg);
}

.info-card {
  background: transparent;
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  padding: 1rem;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.info-icon {
  font-size: 1.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
  margin-bottom: 0.5rem;
}

.info-title {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-text {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
  font-family: 'Courier New', monospace;
  line-height: 1.6;
}

.info-text p {
  margin: 0 0 0.75rem 0;
}

.stat-list,
.duration-list,
.tips-list {
  list-style: none;
  padding: 0;
  margin: 0.75rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.stat-list li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.25rem;
}

.stat-list li :deep(svg) {
  color: var(--color-theme-primary);
  font-size: 1rem;
}

.duration-list li {
  padding-left: 1rem;
}

.example {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-accent);
  border-radius: 0.25rem;
  color: var(--color-theme-accent);
  font-style: italic;
  font-size: 0.8rem;
}

.example :deep(svg) {
  font-size: 1rem;
  flex-shrink: 0;
}

.tips-list li {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding-left: 0.5rem;
}

.tip-icon {
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  flex-shrink: 0;
  margin-top: 0.125rem;
}
</style>
