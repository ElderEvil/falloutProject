<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useQuestStore } from '@/stores/quest'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { Icon } from '@iconify/vue'

const route = useRoute()
const questStore = useQuestStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref<'active' | 'completed'>('active')

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

const hasOverseerOffice = computed(() => {
  return roomStore.rooms.some(
    (room) => room.name.toLowerCase().includes('overseer') || room.category === 'quests'
  )
})

onMounted(async () => {
  if (vaultId.value) {
    // Fetch rooms first (requires token)
    if (authStore.token) {
      await roomStore.fetchRooms(vaultId.value, authStore.token)
    }
    if (hasOverseerOffice.value) {
      questStore.fetchVaultQuests(vaultId.value)
      questStore.fetchAllQuests()
    }
  }
})

const activeQuests = computed(() => questStore.activeQuests)
const availableQuests = computed(() => questStore.availableQuests)
const completedQuests = computed(() => questStore.completedQuests)

const handleStartQuest = async (questId: string) => {
  if (!vaultId.value) return
  await questStore.assignQuest(vaultId.value, questId, true)
}

const handleCompleteQuest = async (questId: string) => {
  if (!vaultId.value) return
  await questStore.completeQuest(vaultId.value, questId)
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8">
          <!-- Locked State -->
          <div v-if="!hasOverseerOffice" class="locked-container">
            <div class="locked-icon">
              <Icon icon="mdi:lock" class="text-9xl opacity-50" />
            </div>
            <h1 class="locked-title">OVERSEER'S OFFICE REQUIRED</h1>
            <p class="locked-description">
              Build an <strong>Overseer's Office</strong> to unlock the quest system and access missions for your vault.
            </p>
            <div class="locked-hint">
              <Icon icon="mdi:information" class="inline mr-2" />
              Quests provide special challenges and valuable rewards
            </div>
          </div>

          <!-- Quests View -->
          <div v-else class="quests-container">
            <h1 class="title">
              {{ currentVault ? `Vault ${currentVault.number} Quests` : 'Quests' }}
            </h1>

            <!-- Tabs -->
            <div class="tabs">
              <button
                @click="activeTab = 'active'"
                :class="{ active: activeTab === 'active' }"
                class="tab-button"
              >
                <Icon icon="mdi:play-circle" class="inline mr-2" />
                Active & Available
              </button>
              <button
                @click="activeTab = 'completed'"
                :class="{ active: activeTab === 'completed' }"
                class="tab-button"
              >
                <Icon icon="mdi:check-circle" class="inline mr-2" />
                Completed
              </button>
            </div>

            <!-- Active & Available Quests -->
            <div v-if="activeTab === 'active'" class="tab-content">
              <!-- Active Quests Section -->
              <div v-if="activeQuests.length > 0" class="quest-section">
                <h2 class="section-title">
                  <Icon icon="mdi:progress-check" class="inline mr-2" />
                  ACTIVE QUESTS
                </h2>
                <div class="quest-grid">
                  <div v-for="quest in activeQuests" :key="quest.id" class="quest-card active-quest">
                    <div class="quest-header">
                      <h3 class="quest-title">{{ quest.title }}</h3>
                      <div class="quest-badge active-badge">ACTIVE!</div>
                    </div>

                    <p class="quest-description">{{ quest.short_description }}</p>

                    <div class="quest-section-divider"></div>

                    <div class="quest-details">
                      <div class="detail-item">
                        <div class="detail-label">
                          <Icon icon="mdi:clipboard-check" class="inline mr-1" />
                          REQUIREMENTS
                        </div>
                        <div class="detail-value">{{ quest.requirements }}</div>
                      </div>
                      <div class="detail-item">
                        <div class="detail-label">
                          <Icon icon="mdi:treasure-chest" class="inline mr-1" />
                          REWARDS
                        </div>
                        <div class="detail-value reward-text">{{ quest.rewards }}</div>
                      </div>
                    </div>

                    <button @click="handleCompleteQuest(quest.id)" class="quest-action-btn complete-btn">
                      <Icon icon="mdi:check-bold" class="inline mr-2" />
                      COMPLETE QUEST
                    </button>
                  </div>
                </div>
              </div>

              <!-- Available Quests Section -->
              <div v-if="availableQuests.length > 0" class="quest-section">
                <h2 class="section-title">
                  <Icon icon="mdi:book-open-page-variant" class="inline mr-2" />
                  AVAILABLE QUESTS
                </h2>
                <div class="quest-grid">
                  <div v-for="quest in availableQuests" :key="quest.id" class="quest-card available-quest">
                    <div class="quest-header">
                      <h3 class="quest-title">{{ quest.title }}</h3>
                      <div class="quest-badge available-badge">NEW</div>
                    </div>

                    <p class="quest-description">{{ quest.short_description }}</p>

                    <div class="quest-section-divider"></div>

                    <div class="quest-details">
                      <div class="detail-item">
                        <div class="detail-label">
                          <Icon icon="mdi:clipboard-check" class="inline mr-1" />
                          REQUIREMENTS
                        </div>
                        <div class="detail-value">{{ quest.requirements }}</div>
                      </div>
                      <div class="detail-item">
                        <div class="detail-label">
                          <Icon icon="mdi:treasure-chest" class="inline mr-1" />
                          REWARDS
                        </div>
                        <div class="detail-value reward-text">{{ quest.rewards }}</div>
                      </div>
                    </div>

                    <button @click="handleStartQuest(quest.id)" class="quest-action-btn start-btn">
                      <Icon icon="mdi:play" class="inline mr-2" />
                      START QUEST
                    </button>
                  </div>
                </div>
              </div>

              <!-- Empty State -->
              <div v-if="activeQuests.length === 0 && availableQuests.length === 0" class="empty-state">
                <Icon icon="mdi:inbox" class="text-8xl mb-6 opacity-30" />
                <p>No quests available at the moment</p>
              </div>
            </div>

            <!-- Completed Quests -->
            <div v-if="activeTab === 'completed'" class="tab-content">
              <div v-if="completedQuests.length === 0" class="empty-state">
                <Icon icon="mdi:checkbox-marked-circle-outline" class="text-8xl mb-6 opacity-30" />
                <p>No completed quests yet</p>
              </div>

              <div v-else class="quest-grid">
                <div v-for="quest in completedQuests" :key="quest.id" class="quest-card completed-quest">
                  <div class="quest-header">
                    <h3 class="quest-title">{{ quest.title }}</h3>
                    <div class="quest-badge completed-badge">
                      <Icon icon="mdi:check" class="inline mr-1" />
                      DONE
                    </div>
                  </div>

                  <p class="quest-description">{{ quest.short_description }}</p>

                  <div class="quest-section-divider"></div>

                  <div class="quest-details">
                    <div class="detail-item">
                      <div class="detail-label">
                        <Icon icon="mdi:treasure-chest" class="inline mr-1" />
                        REWARDS CLAIMED
                      </div>
                      <div class="detail-value reward-text">{{ quest.rewards }}</div>
                    </div>
                  </div>

                  <div class="completion-stamp">
                    <Icon icon="mdi:seal" class="inline mr-2" />
                    COMPLETED
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
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

.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}

/* Locked State */
.locked-container {
  max-width: 800px;
  margin: 80px auto;
  padding: 60px 40px;
  background-color: #1a1a1a;
  border: 3px solid var(--color-theme-primary);
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 0 30px var(--color-theme-glow);
}

.locked-icon {
  margin-bottom: 32px;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.locked-title {
  font-size: 3rem;
  font-weight: bold;
  margin-bottom: 24px;
  color: var(--color-theme-primary);
  letter-spacing: 0.1em;
}

.locked-description {
  font-size: 1.3rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  line-height: 1.8;
  margin-bottom: 32px;
}

.locked-hint {
  padding: 16px 24px;
  background-color: rgba(0, 0, 0, 0.4);
  border-left: 4px solid var(--color-theme-accent);
  font-size: 1.1rem;
  color: var(--color-theme-accent);
}

/* Quests Container */
.quests-container {
  max-width: 1400px;
  margin: 0 auto;
}

.title {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 24px;
  text-align: center;
}

/* Tabs */
.tabs {
  display: flex;
  justify-content: flex-start;
  gap: 0;
  margin-bottom: 24px;
  border-bottom: 2px solid var(--color-theme-glow);
}

.tab-button {
  padding: 10px 24px;
  background-color: transparent;
  color: var(--color-theme-primary);
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.6;
}

.tab-button.active {
  opacity: 1;
  border-bottom-color: var(--color-theme-primary);
  background-color: var(--color-theme-glow);
}

.tab-button:hover:not(.active) {
  opacity: 0.8;
  background-color: rgba(0, 0, 0, 0.2);
}

/* Section Title */
.quest-section {
  margin-bottom: 32px;
}

.section-title {
  font-size: 1.3rem;
  font-weight: bold;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--color-theme-glow);
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Quest Grid */
.quest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

/* Quest Card */
.quest-card {
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  padding: 16px;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.quest-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.quest-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px var(--color-theme-glow);
}

.active-quest {
  border-color: var(--color-theme-accent);
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
}

.active-quest::before {
  background: var(--color-theme-accent);
}

.available-quest {
  border-color: var(--color-theme-primary);
}

.completed-quest {
  border-color: #666666;
  opacity: 0.75;
  background: linear-gradient(135deg, #1a1a1a 0%, #252525 100%);
}

.completed-quest::before {
  background: #666666;
}

/* Quest Header */
.quest-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 12px;
}

.quest-title {
  font-size: 1.1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex: 1;
}

.quest-badge {
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  white-space: nowrap;
  flex-shrink: 0;
}

.active-badge {
  background-color: var(--color-theme-accent);
  color: #000000;
  box-shadow: 0 0 10px var(--color-theme-accent);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.available-badge {
  background-color: var(--color-theme-primary);
  color: #000000;
}

.completed-badge {
  background-color: #666666;
  color: #ffffff;
}

/* Quest Description */
.quest-description {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
  margin-bottom: 12px;
  line-height: 1.5;
}

.quest-section-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-theme-primary), transparent);
  margin: 12px 0;
  opacity: 0.3;
}

/* Quest Details */
.quest-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-item {
  background-color: rgba(0, 0, 0, 0.3);
  padding: 8px 12px;
  border-left: 2px solid var(--color-theme-primary);
  border-radius: 3px;
}

.detail-label {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
}

.reward-text {
  font-weight: bold;
  color: var(--color-theme-accent);
}

/* Action Buttons */
.quest-action-btn {
  width: 100%;
  padding: 10px 16px;
  border: 2px solid var(--color-theme-primary);
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Courier New', monospace;
}

.complete-btn {
  background-color: var(--color-theme-accent);
  color: #000000;
  border-color: var(--color-theme-accent);
}

.complete-btn:hover {
  background-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
  transform: translateY(-1px);
}

.start-btn {
  background-color: transparent;
  color: var(--color-theme-primary);
}

.start-btn:hover {
  background-color: var(--color-theme-primary);
  color: #000000;
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: translateY(-2px);
}

/* Completion Stamp */
.completion-stamp {
  text-align: center;
  padding: 12px;
  background-color: rgba(0, 0, 0, 0.5);
  border: 2px dashed #666666;
  border-radius: 4px;
  color: #666666;
  font-weight: bold;
  font-size: 1.1rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 80px 24px;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.empty-state p {
  font-size: 1.5rem;
}
</style>
