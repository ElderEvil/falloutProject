<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import TrainingQueuePanel from '@/components/training/TrainingQueuePanel.vue'
import { useVaultStore } from '@/stores/vault'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const vaultStore = useVaultStore()
const authStore = useAuthStore()

const vaultId = route.params.id as string

onMounted(async () => {
  if (authStore.accessToken && vaultId) {
    // Ensure vault is loaded
    if (!vaultStore.currentVault || vaultStore.currentVault.id !== vaultId) {
      await vaultStore.fetchVault(vaultId, authStore.accessToken)
    }
  }
})
</script>

<template>
  <div class="training-view">
    <div class="training-header">
      <div class="header-content">
        <Icon icon="mdi:dumbbell" class="header-icon" />
        <div class="header-text">
          <h1 class="header-title">Training Center</h1>
          <p class="header-subtitle">
            Monitor and manage SPECIAL stat training across your vault
          </p>
        </div>
      </div>
    </div>

    <div class="training-content">
      <div class="main-panel">
        <TrainingQueuePanel />
      </div>

      <div class="info-panel">
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
              <li>
                <strong>Base Duration:</strong> 2 hours
              </li>
              <li>
                <strong>Scaling:</strong> +30 minutes per current stat level
              </li>
              <li>
                <strong>Tier 2 Rooms:</strong> 25% faster
              </li>
              <li>
                <strong>Tier 3 Rooms:</strong> 40% faster
              </li>
            </ul>
            <p class="example">
              <Icon icon="mdi:lightbulb" />
              <em>Example: Training from 5→6 takes 4.5 hours (or 2.7 hours in a Tier 3 room)</em>
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
      </div>
    </div>
  </div>
</template>

<style scoped>
.training-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1.5rem;
  gap: 1.5rem;
  overflow: hidden;
}

.training-header {
  background: linear-gradient(135deg, rgb(0 0 0 / 0.7), rgb(15 23 42 / 0.7));
  border: 1px solid rgb(34 197 94 / 0.3);
  border-radius: 0.5rem;
  padding: 1.5rem;
  box-shadow: 0 0 20px rgb(34 197 94 / 0.2);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.header-icon {
  font-size: 3rem;
  color: rgb(34 197 94);
  filter: drop-shadow(0 0 8px rgb(34 197 94 / 0.6));
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.header-title {
  margin: 0;
  font-size: 2rem;
  font-weight: bold;
  color: rgb(34 197 94);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  text-shadow: 0 0 10px rgb(34 197 94 / 0.5);
}

.header-subtitle {
  margin: 0;
  font-size: 1rem;
  color: rgb(134 239 172);
  font-family: 'Courier New', monospace;
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

.info-card {
  background: linear-gradient(135deg, rgb(0 0 0 / 0.7), rgb(15 23 42 / 0.7));
  border: 1px solid rgb(34 197 94 / 0.3);
  border-radius: 0.5rem;
  padding: 1.5rem;
  box-shadow: 0 0 10px rgb(34 197 94 / 0.1);
}

.info-icon {
  font-size: 2rem;
  color: rgb(34 197 94);
  filter: drop-shadow(0 0 4px rgb(34 197 94 / 0.5));
  margin-bottom: 0.75rem;
}

.info-title {
  margin: 0 0 1rem 0;
  font-size: 1.25rem;
  font-weight: bold;
  color: rgb(74 222 128);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-text {
  font-size: 0.875rem;
  color: rgb(134 239 172);
  font-family: 'Courier New', monospace;
  line-height: 1.6;
}

.info-text p {
  margin: 0 0 1rem 0;
}

.stat-list,
.duration-list,
.tips-list {
  list-style: none;
  padding: 0;
  margin: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat-list li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgb(0 0 0 / 0.3);
  border: 1px solid rgb(34 197 94 / 0.2);
  border-radius: 0.25rem;
}

.stat-list li :deep(svg) {
  color: rgb(34 197 94);
  font-size: 1.25rem;
}

.duration-list li {
  padding-left: 1rem;
}

.example {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgb(250 204 21 / 0.1);
  border: 1px solid rgb(250 204 21 / 0.3);
  border-radius: 0.25rem;
  color: rgb(250 204 21);
  font-style: italic;
}

.example :deep(svg) {
  font-size: 1.25rem;
  flex-shrink: 0;
}

.tips-list li {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding-left: 0.5rem;
}

.tip-icon {
  color: rgb(34 197 94);
  font-size: 1rem;
  flex-shrink: 0;
  margin-top: 0.125rem;
}
</style>
