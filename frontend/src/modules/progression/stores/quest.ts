import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as questApi from '../api/quest'
import type { components } from '@/core/types/api.generated'
import type { Quest, QuestPartyMember, VaultQuest } from '../models/quest'
import { formatGrantedReward, isQuestReturning, isStateQuestCategory } from '../models/quest'
import { useToast } from '@/core/composables/useToast'
import { refreshNukaColaCount } from '@/modules/vault/composables/useNukaColaCount'
import { notifyErrorOnce, handleStoreError } from '@/core/utils/errorHandler'

type QuestCompleteResponse = components['schemas']['QuestCompleteResponse']

import type { EligibleDweller } from '../api/quest'

export type { EligibleDweller } from '../api/quest'

/** Prefer the backend's detail; a transport failure keeps the caller's fixed context. */
function apiErrorDetail(error: unknown, fallback: string): string {
  const detail = (error as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail) return detail
  const responseDetail = (error as { response?: { data?: { detail?: unknown } } } | null)?.response
    ?.data?.detail
  return typeof responseDetail === 'string' && responseDetail ? responseDetail : fallback
}

export const useQuestStore = defineStore('quest', () => {
  const toast = useToast()

  // State
  const quests = ref<Quest[]>([])
  const vaultQuests = ref<VaultQuest[]>([])
  const isLoading = ref(false)
  const questSlotLimit = ref(3)
  const questPartyMap = ref<Record<string, QuestPartyMember[]>>({})

  // Computed
  // Single pass classification of all vault quests
  const questCategories = computed(() => {
    const active: VaultQuest[] = []
    const returning: VaultQuest[] = []
    const readyToClaim: VaultQuest[] = []
    const completed: VaultQuest[] = []
    const available: VaultQuest[] = []
    const allVisible: VaultQuest[] = []

    for (const quest of vaultQuests.value) {
      if (!quest.is_visible) continue
      allVisible.push(quest)
      if (quest.is_completed) {
        completed.push(quest)
      } else if (quest.is_reward_ready) {
        readyToClaim.push(quest)
      } else if (quest.started_at != null && isQuestReturning(quest)) {
        returning.push(quest)
      } else if (quest.started_at != null) {
        active.push(quest)
      } else {
        available.push(quest)
      }
    }

    return { active, returning, readyToClaim, completed, available, allVisible }
  })

  const activeTimedQuestCount = computed(
    () =>
      vaultQuests.value.filter(
        (quest) =>
          quest.started_at &&
          !quest.is_completed &&
          !quest.is_reward_ready &&
          (quest.duration_minutes ?? 0) > 0 &&
          !isStateQuestCategory(quest.quest_category)
      ).length
  )
  const timedQuestLimitReached = computed(() => activeTimedQuestCount.value >= questSlotLimit.value)

  // Actions
  async function fetchAllQuests(): Promise<void> {
    try {
      isLoading.value = true
      quests.value = await questApi.listQuests()
    } catch (error: unknown) {
      notifyErrorOnce(error, 'Failed to load quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVaultQuests(vaultId: string, options?: { silent?: boolean }): Promise<void> {
    const silent = options?.silent ?? false
    try {
      if (!silent) isLoading.value = true
      vaultQuests.value = await questApi.listVaultQuests(vaultId)
    } catch (error: unknown) {
      if (!silent) notifyErrorOnce(error, 'Failed to load vault quests')
      throw error
    } finally {
      if (!silent) isLoading.value = false
    }
  }

  async function fetchPartiesForActiveQuests(vaultId: string): Promise<void> {
    const active = vaultQuests.value.filter(
      (q) => q.is_visible && q.started_at != null && !q.is_completed
    )
    const nextPartyMap: Record<string, QuestPartyMember[]> = {}
    for (const quest of active) {
      try {
        nextPartyMap[quest.id] = await getParty(vaultId, quest.id)
      } catch (error: unknown) {
        handleStoreError(
          error,
          `Failed to fetch party for quest ${quest.id} in vault ${vaultId}`,
          false
        )
        nextPartyMap[quest.id] = []
      }
    }
    questPartyMap.value = nextPartyMap
  }

  async function assignQuest(vaultId: string, questId: string, isVisible = true): Promise<void> {
    try {
      await questApi.assignQuest(vaultId, questId, isVisible)
      toast.success('Quest assigned successfully')
    } catch (error: unknown) {
      const errorMessage = apiErrorDetail(error, 'Failed to assign quest')
      notifyErrorOnce(error, errorMessage)
      throw error
    }
    // Refresh vault quests (silent — mutation already succeeded)
    try {
      await fetchVaultQuests(vaultId, { silent: true })
    } catch {
      toast.warning('Quest was assigned, but the quest list could not refresh')
    }
  }

  async function claimQuestRewards(
    vaultId: string,
    questId: string
  ): Promise<QuestCompleteResponse | null> {
    let result: QuestCompleteResponse | null = null
    try {
      const claimed = await questApi.claimRewards(vaultId, questId)
      result = claimed

      if (claimed.granted_rewards && claimed.granted_rewards.length > 0) {
        const rewardsText = claimed.granted_rewards.map(formatGrantedReward).join(', ')
        toast.success(`Rewards claimed: ${rewardsText}`)
      } else {
        toast.success('Quest rewards claimed!')
      }
      void refreshNukaColaCount(vaultId)
    } catch (error: unknown) {
      const errorMessage = apiErrorDetail(error, 'Failed to claim quest rewards')
      notifyErrorOnce(error, errorMessage)
      throw error
    }
    // Refresh vault quests (silent — mutation already succeeded)
    try {
      await fetchVaultQuests(vaultId, { silent: true })
    } catch {
      toast.warning('Rewards were claimed, but the quest list could not refresh')
    }
    return result
  }

  async function getParty(vaultId: string, questId: string): Promise<QuestPartyMember[]> {
    try {
      return await questApi.getParty(vaultId, questId)
    } catch (error: unknown) {
      notifyErrorOnce(error, 'Failed to load quest party')
      throw error
    }
  }

  async function getEligibleDwellers(vaultId: string, questId: string): Promise<EligibleDweller[]> {
    try {
      return await questApi.getEligibleDwellers(vaultId, questId)
    } catch (error: unknown) {
      notifyErrorOnce(error, 'Failed to load eligible dwellers')
      throw error
    }
  }

  async function startQuest(
    vaultId: string,
    questId: string,
    dwellerIds?: string[]
  ): Promise<void> {
    try {
      await questApi.startQuest(vaultId, questId, dwellerIds)
      toast.success('Quest started!')
    } catch (error: unknown) {
      const errorMessage = apiErrorDetail(error, 'Failed to start quest')
      notifyErrorOnce(error, errorMessage)
      throw error
    }
    // Refresh vault quests (silent — mutation already succeeded)
    try {
      await fetchVaultQuests(vaultId, { silent: true })
    } catch {
      toast.warning('Quest was started, but the quest list could not refresh')
    }
  }

  return {
    quests,
    vaultQuests,
    isLoading,
    questPartyMap,
    questCategories,
    activeTimedQuestCount,
    questSlotLimit,
    timedQuestLimitReached,
    fetchAllQuests,
    fetchVaultQuests,
    fetchPartiesForActiveQuests,
    assignQuest,
    claimQuestRewards,
    getParty,
    getEligibleDwellers,
    startQuest,
  }
})
