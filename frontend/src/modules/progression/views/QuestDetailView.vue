<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useQuestStore } from '../stores/quest'
import { useVaultStore } from '@/modules/vault/stores/vault'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { UCard, UBadge, UButton } from '@/core/components/ui'
import type { VaultQuest } from '../models/quest'

const route = useRoute()
const router = useRouter()
const questStore = useQuestStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()

const quest = ref<VaultQuest | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)

const vaultId = computed(() => route.params.id as string)
const questId = computed(() => route.params.questId as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

onMounted(async () => {
  if (!vaultId.value || !questId.value) {
    error.value = 'Missing vault or quest ID'
    isLoading.value = false
    return
  }

  try {
    // Fetch from vault quests first
    await questStore.fetchVaultQuests(vaultId.value)
    const vaultQuest = questStore.vaultQuests.find((q) => q.id === questId.value)

    if (vaultQuest) {
      quest.value = vaultQuest
    } else {
      // Try to fetch as a general quest
      await questStore.fetchAllQuests()
      const generalQuest = questStore.quests.find((q) => q.id === questId.value)
      if (generalQuest) {
        quest.value = { ...generalQuest, is_visible: false, is_completed: false }
      } else {
        error.value = 'Quest not found'
      }
    }
  } catch (err) {
    error.value = 'Failed to load quest details'
    console.error(err)
  } finally {
    isLoading.value = false
  }
})

// Type badge colors
const typeColors: Record<string, { bg: string; text: string }> = {
  main: { bg: '#ffb000', text: '#000000' },
  side: { bg: '#c0c0c0', text: '#000000' },
  daily: { bg: '#00d9ff', text: '#000000' },
  event: { bg: '#9b59b6', text: '#ffffff' },
  repeatable: { bg: '#00ff00', text: '#000000' },
}

const typeColor = computed(() => {
  if (!quest.value) return typeColors.side
  return typeColors[quest.value.quest_type] || typeColors.side
})

const typeLabel = computed(() => {
  if (!quest.value) return 'Side'
  return quest.value.quest_type.charAt(0).toUpperCase() + quest.value.quest_type.slice(1)
})

const isChainQuest = computed(() => {
  return quest.value?.chain_id !== null
})

const chainPosition = computed(() => {
  if (!isChainQuest.value || !quest.value) return null
  return quest.value.chain_order > 0 ? `Quest ${quest.value.chain_order}` : 'Chain Quest'
})

const hasPrerequisites = computed(() => {
  return quest.value?.quest_requirements && quest.value.quest_requirements.length > 0
})

const prerequisitesMet = computed(() => {
  if (!hasPrerequisites.value) return true
  // Prerequisites are met if quest is active or completed
  return quest.value?.is_visible || quest.value?.is_completed
})

const canStart = computed(() => {
  return !quest.value?.is_visible && !quest.value?.is_completed && prerequisitesMet.value
})

const canComplete = computed(() => {
  return quest.value?.is_visible && !quest.value?.is_completed
})

const isCompleted = computed(() => {
  return quest.value?.is_completed
})

const handleStartQuest = async () => {
  if (!vaultId.value || !questId.value) return
  await questStore.assignQuest(vaultId.value, questId.value, true)
  // Refresh quest data
  await questStore.fetchVaultQuests(vaultId.value)
  const updatedQuest = questStore.vaultQuests.find((q) => q.id === questId.value)
  if (updatedQuest) {
    quest.value = updatedQuest
  }
}

const handleCompleteQuest = async () => {
  if (!vaultId.value || !questId.value) return
  await questStore.completeQuest(vaultId.value, questId.value)
  // Refresh quest data
  await questStore.fetchVaultQuests(vaultId.value)
  const updatedQuest = questStore.vaultQuests.find((q) => q.id === questId.value)
  if (updatedQuest) {
    quest.value = updatedQuest
  }
}

const goBack = () => {
  router.push({ name: 'quests', params: { id: vaultId.value } })
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
          <!-- Back Button -->
          <button class="back-btn" @click="goBack">
            <Icon icon="mdi:arrow-left" class="inline mr-2" />
            Back to Quests
          </button>

          <!-- Loading State -->
          <div v-if="isLoading" class="loading-state">
            <Icon icon="mdi:loading" class="animate-spin text-4xl" />
            <p>Loading quest details...</p>
          </div>

          <!-- Error State -->
          <div v-else-if="error" class="error-state">
            <Icon icon="mdi:alert-circle" class="text-6xl mb-4" />
            <h2>{{ error }}</h2>
            <UButton variant="primary" @click="goBack">Return to Quests</UButton>
          </div>

          <!-- Quest Detail View -->
          <div v-else-if="quest" class="quest-detail">
            <!-- Header Section -->
            <div class="quest-header-section">
              <div class="quest-badges">
                <UBadge
                  :style="{ backgroundColor: typeColor.bg, color: typeColor.text }"
                  class="type-badge"
                >
                  {{ typeLabel }}
                </UBadge>
                <UBadge v-if="quest.quest_category" variant="secondary" class="category-badge">
                  {{ quest.quest_category }}
                </UBadge>
                <UBadge v-if="isChainQuest" variant="outline" class="chain-badge">
                  <Icon icon="mdi:link-variant" class="inline-icon" />
                  {{ chainPosition }}
                </UBadge>
              </div>

              <h1 class="quest-title">{{ quest.title }}</h1>

              <div v-if="isCompleted" class="completion-banner">
                <Icon icon="mdi:check-circle" class="banner-icon" />
                Quest Completed
              </div>
              <div v-else-if="canComplete" class="active-banner">
                <Icon icon="mdi:progress-check" class="banner-icon" />
                Quest In Progress
              </div>
            </div>

            <!-- Main Content Grid -->
            <div class="quest-content-grid">
              <!-- Left Column: Description & Details -->
              <div class="quest-main-content">
                <UCard title="Description" class="description-card">
                  <p class="quest-description">{{ quest.long_description }}</p>
                </UCard>

                <!-- Prerequisites Section -->
                <UCard v-if="hasPrerequisites" title="Prerequisites" class="prerequisites-card">
                  <ul class="prerequisites-list">
                    <li
                      v-for="req in quest.quest_requirements"
                      :key="req.id"
                      class="prerequisite-item"
                      :class="{ met: prerequisitesMet, unmet: !prerequisitesMet }"
                    >
                      <Icon
                        :icon="prerequisitesMet ? 'mdi:check-circle' : 'mdi:lock'"
                        class="prerequisite-icon"
                      />
                      <div class="prerequisite-details">
                        <span class="prerequisite-type">{{ req.requirement_type }}</span>
                        <span v-if="req.is_mandatory" class="mandatory-tag">Required</span>
                      </div>
                    </li>
                  </ul>
                </UCard>

                <!-- Chain Progress Section -->
                <UCard v-if="isChainQuest" title="Quest Chain" class="chain-card">
                  <div class="chain-info">
                    <p class="chain-text">
                      This quest is part of a series. Complete all quests in the chain for
                      additional rewards!
                    </p>
                    <div v-if="quest.previous_quest_id" class="chain-link">
                      <Icon icon="mdi:arrow-left" />
                      Previous quest must be completed first
                    </div>
                    <div v-if="quest.next_quest_id" class="chain-link">
                      <Icon icon="mdi:arrow-right" />
                      Unlocks next quest upon completion
                    </div>
                  </div>
                </UCard>
              </div>

              <!-- Right Column: Rewards & Actions -->
              <div class="quest-sidebar">
                <UCard title="Rewards" class="rewards-card">
                  <div
                    v-if="quest.quest_rewards && quest.quest_rewards.length > 0"
                    class="rewards-list"
                  >
                    <div v-for="reward in quest.quest_rewards" :key="reward.id" class="reward-item">
                      <div class="reward-icon-wrapper">
                        <Icon icon="mdi:gift" class="reward-icon" />
                      </div>
                      <div class="reward-details">
                        <span class="reward-type">{{ reward.reward_type }}</span>
                        <span v-if="reward.reward_chance < 1" class="reward-chance">
                          {{ Math.round(reward.reward_chance * 100) }}% chance
                        </span>
                      </div>
                    </div>
                  </div>
                  <div v-else class="reward-fallback">
                    <Icon icon="mdi:text" class="reward-icon" />
                    <span>{{ quest.rewards }}</span>
                  </div>
                </UCard>

                <!-- Action Section -->
                <div class="action-section">
                  <UButton
                    v-if="canStart"
                    variant="primary"
                    class="action-btn"
                    @click="handleStartQuest"
                  >
                    <Icon icon="mdi:play" class="btn-icon" />
                    Start Quest
                  </UButton>

                  <UButton
                    v-else-if="canComplete"
                    variant="success"
                    class="action-btn"
                    @click="handleCompleteQuest"
                  >
                    <Icon icon="mdi:check-bold" class="btn-icon" />
                    Complete Quest
                  </UButton>

                  <div v-else-if="isCompleted" class="completed-message">
                    <Icon icon="mdi:seal" class="message-icon" />
                    <span>Quest Completed - Rewards Claimed</span>
                  </div>

                  <div v-else-if="!prerequisitesMet" class="locked-message">
                    <Icon icon="mdi:lock" class="message-icon" />
                    <span>Prerequisites not met</span>
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

.back-btn {
  background: transparent;
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 24px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.back-btn:hover {
  background: var(--color-theme-primary);
  color: #000000;
  box-shadow: 0 0 15px var(--color-theme-glow);
}

.loading-state,
.error-state {
  text-align: center;
  padding: 80px 24px;
  color: var(--color-theme-primary);
}

.error-state h2 {
  margin-bottom: 24px;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.quest-detail {
  max-width: 1400px;
  margin: 0 auto;
}

.quest-header-section {
  margin-bottom: 32px;
}

.quest-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.type-badge,
.category-badge,
.chain-badge {
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.quest-title {
  font-size: 2.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0 0 16px 0;
  text-shadow: 0 0 10px var(--color-theme-glow);
}

.completion-banner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: rgba(0, 255, 0, 0.1);
  border: 2px solid #00ff00;
  border-radius: 4px;
  color: #00ff00;
  font-weight: bold;
  font-size: 1.1rem;
}

.active-banner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  background: var(--color-theme-glow);
  border: 2px solid var(--color-theme-accent);
  border-radius: 4px;
  color: var(--color-theme-accent);
  font-weight: bold;
  font-size: 1.1rem;
}

.banner-icon {
  font-size: 1.5rem;
}

.quest-content-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

@media (max-width: 1024px) {
  .quest-content-grid {
    grid-template-columns: 1fr;
  }
}

.quest-main-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.description-card :deep(.card-content) {
  font-size: 1.1rem;
  line-height: 1.8;
  color: var(--color-theme-primary);
}

.prerequisites-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.prerequisite-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 4px;
  margin-bottom: 8px;
}

.prerequisite-item.met {
  background: rgba(0, 255, 0, 0.1);
}

.prerequisite-item.unmet {
  background: rgba(255, 102, 0, 0.1);
}

.prerequisite-icon {
  font-size: 1.5rem;
}

.prerequisite-item.met .prerequisite-icon {
  color: #00ff00;
}

.prerequisite-item.unmet .prerequisite-icon {
  color: #ff6600;
}

.prerequisite-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prerequisite-type {
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mandatory-tag {
  font-size: 0.75rem;
  color: var(--color-theme-accent);
}

.chain-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chain-text {
  font-style: italic;
  opacity: 0.9;
}

.chain-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--color-theme-glow);
  border-radius: 4px;
  font-size: 0.9rem;
}

.quest-sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.rewards-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.reward-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.reward-icon-wrapper {
  width: 40px;
  height: 40px;
  background: var(--color-theme-glow);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.reward-icon {
  font-size: 20px;
  color: var(--color-theme-primary);
}

.reward-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.reward-type {
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
}

.reward-chance {
  font-size: 0.8rem;
  opacity: 0.7;
}

.reward-fallback {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  font-size: 1rem;
}

.action-section {
  margin-top: auto;
}

.action-btn {
  width: 100%;
  padding: 16px;
  font-size: 1.1rem;
}

.btn-icon {
  margin-right: 8px;
}

.completed-message,
.locked-message {
  padding: 16px;
  border-radius: 4px;
  text-align: center;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.completed-message {
  background: rgba(0, 255, 0, 0.1);
  border: 2px solid #00ff00;
  color: #00ff00;
}

.locked-message {
  background: rgba(255, 102, 0, 0.1);
  border: 2px solid #ff6600;
  color: #ff6600;
}

.message-icon {
  font-size: 1.5rem;
}

.inline-icon {
  display: inline;
  vertical-align: middle;
}
</style>
