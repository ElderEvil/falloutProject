<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import TrainingQueuePanel from '@/modules/progression/components/training/TrainingQueuePanel.vue'
import TrainingRoomCard from '@/modules/progression/components/training/TrainingRoomCard.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useSidePanel } from '@/core/composables/useSidePanel'
import PageHeader from '@/core/components/common/PageHeader.vue'

const route = useRoute()
const vaultStore = useVaultStore()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const trainingStore = useTrainingStore()
const { isCollapsed } = useSidePanel()

const vaultId = route.params.id as string

const showInfo = ref(false)

const trainingRooms = computed(() => {
  return roomStore.rooms.filter((room) => room.category === 'training')
})

const activeTrainings = computed(() => trainingStore.allActiveTrainings)

const getRoomActiveCount = (roomId: string) => {
  return activeTrainings.value.filter((training) => training.room_id === roomId).length
}

const roomsInUse = computed(() => {
  const roomIds = new Set(activeTrainings.value.map((training) => training.room_id))
  return trainingRooms.value.filter((room) => roomIds.has(room.id)).length
})

const totalCapacity = computed(() => {
  return trainingRooms.value.reduce((sum, room) => sum + (room.capacity ?? 0), 0)
})

const capacityPercent = computed(() => {
  if (totalCapacity.value <= 0) return 0
  return Math.min(100, Math.round((activeTrainings.value.length / totalCapacity.value) * 100))
})

onMounted(async () => {
  if (authStore.token && vaultId) {
    // Ensure vault is loaded - loadVault handles the check internally
    await vaultStore.loadVault(vaultId, authStore.token)
    await roomStore.fetchRooms(vaultId, authStore.token)
    await trainingStore.fetchVaultTrainings(vaultId, authStore.token)
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <SidePanel />

      <main class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto flex flex-col gap-6 px-4 py-8 lg:px-8">
          <PageHeader
            title="Training Center"
            icon="mdi:dumbbell"
            subtitle="Monitor and manage SPECIAL stat training across your vault"
          />

          <section class="training-rooms-section">
            <div class="rooms-header">
              <div class="header-title">
                <Icon icon="mdi:office-building" class="header-icon" />
                <h3>Training Rooms ({{ trainingRooms.length }})</h3>
              </div>
              <div class="rooms-summary">
                <span class="summary-chip">
                  <Icon icon="mdi:account-multiple" class="summary-chip-icon" />
                  {{ activeTrainings.length }} training
                </span>
                <span class="summary-chip">
                  <Icon icon="mdi:progress-clock" class="summary-chip-icon" />
                  {{ roomsInUse }} / {{ trainingRooms.length }} in use
                </span>
              </div>
            </div>

            <div v-if="trainingRooms.length === 0" class="rooms-empty">
              <Icon icon="mdi:hammer-wrench" class="rooms-empty-icon" />
              <p class="rooms-empty-text">No training rooms built yet</p>
              <p class="rooms-empty-hint">Build training rooms in the vault to train dwellers</p>
            </div>

            <div v-else class="rooms-grid">
              <TrainingRoomCard
                v-for="room in trainingRooms"
                :key="room.id"
                :room="room"
                :active-count="getRoomActiveCount(room.id)"
              />
            </div>

            <div v-if="trainingRooms.length > 0" class="capacity-strip">
              <div class="capacity-header">
                <span class="capacity-label">Overall Capacity</span>
                <span class="capacity-value"
                  >{{ activeTrainings.length }} / {{ totalCapacity }}</span
                >
              </div>
              <div class="capacity-bar">
                <div class="capacity-fill" :style="{ width: `${capacityPercent}%` }"></div>
              </div>
            </div>
          </section>

          <div class="w-full">
            <TrainingQueuePanel />
          </div>

          <section class="training-reference">
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
                    Dwellers can train their SPECIAL stats in dedicated training rooms. Each stat
                    has its own training room type:
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
                      >Example: Training from 5→6 takes 4.5 hours (or 2.7 hours in a Tier 3
                      room)</em
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
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

.training-reference {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
}

.training-rooms-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
}

.rooms-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  font-size: 1.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.header-title h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.rooms-summary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.summary-chip {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.25rem 0.625rem;
  background: rgb(0 0 0 / 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.25rem;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.summary-chip-icon {
  font-size: 0.875rem;
}

.rooms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.rooms-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2rem;
  border: 2px dashed var(--color-theme-glow);
  border-radius: 0.5rem;
  text-align: center;
}

.rooms-empty-icon {
  font-size: 3rem;
  color: var(--color-theme-primary);
  opacity: 0.3;
}

.rooms-empty-text {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-family: 'Courier New', monospace;
}

.rooms-empty-hint {
  margin: 0;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  font-family: 'Courier New', monospace;
}

.capacity-strip {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.375rem;
  background: rgb(0 0 0 / 0.3);
}

.capacity-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.capacity-label {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
}

.capacity-value {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.capacity-bar {
  height: 8px;
  background: rgb(0 0 0 / 0.5);
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.25rem;
  overflow: hidden;
}

.capacity-fill {
  height: 100%;
  background: linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent));
  transition: width 0.3s ease;
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
