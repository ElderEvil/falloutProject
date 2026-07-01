import { defineStore, acceptHMRUpdate } from 'pinia'
import { computed, ref } from 'vue'
import * as http from '@/core/plugins/httpClient'
import { handleStoreError } from '@/core/utils/errorHandler'
import type { Quest, QuestPartyMember, VaultQuest } from '../models/quest'
import { useToast } from '@/core/composables/useToast'

interface QuestCompleteResponse {
  quest_id: string
  quest_title: string
  is_completed: boolean
  granted_rewards: Array<{
    type?: string
    name?: string
    amount?: number
    resource_type?: string
    [key: string]: unknown
  }>
}

export const useQuestStore = defineStore('quest', () => {
  const toast = useToast()

  // State
  const quests = ref<Quest[]>([])
  const vaultQuests = ref<VaultQuest[]>([])
  const isLoading = ref(false)
  const questPartyMap = ref<Record<string, QuestPartyMember[]>>({})

  // Computed
  // Single pass classification of all vault quests
  const questCategories = computed(() => {
    const active: VaultQuest[] = []
    const completed: VaultQuest[] = []
    const available: VaultQuest[] = []
    const allVisible: VaultQuest[] = []

    for (const quest of vaultQuests.value) {
      if (!quest.is_visible) continue
      allVisible.push(quest)
      if (quest.is_completed) {
        completed.push(quest)
      } else if (quest.started_at != null) {
        active.push(quest)
      } else {
        available.push(quest)
      }
    }

    return { active, completed, available, allVisible }
  })

  // Actions
  async function fetchAllQuests(): Promise<void> {
    try {
      isLoading.value = true
      quests.value = await http.apiGet<Quest[]>('/api/v1/quests/', { _skipErrorNotification: true })
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch quests')
      toast.error('Failed to load quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVaultQuests(vaultId: string): Promise<void> {
    try {
      isLoading.value = true
      vaultQuests.value = await http.apiGet<VaultQuest[]>(`/api/v1/quests/${vaultId}/`, {
        _skipErrorNotification: true,
      })
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch vault quests')
      toast.error('Failed to load vault quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchPartiesForActiveQuests(vaultId: string): Promise<void> {
    const active = vaultQuests.value.filter(
      (q) => q.is_visible && q.started_at != null && !q.is_completed
    )
    for (const quest of active) {
      try {
        const party = await getParty(vaultId, quest.id)
        if (party.length > 0) {
          questPartyMap.value[quest.id] = party
        }
      } catch {
        questPartyMap.value[quest.id] = []
      }
    }
  }

  async function getQuest(vaultId: string, questId: string): Promise<Quest> {
    try {
      return await http.apiGet<Quest>(`/api/v1/quests/${vaultId}/${questId}`, {
        _skipErrorNotification: true,
      })
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch quest')
      toast.error('Failed to load quest details')
      throw error
    }
  }

  async function assignQuest(vaultId: string, questId: string, isVisible = true): Promise<void> {
    try {
      await http.apiPost(
        `/api/v1/quests/${vaultId}/${questId}/assign?is_visible=${isVisible}`,
        undefined,
        { _skipErrorNotification: true }
      )
      toast.success('Quest assigned successfully')
      // Refresh vault quests
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage = handleStoreError(error, 'Failed to assign quest')
      toast.error(errorMessage)
      throw error
    }
  }

  async function completeQuest(
    vaultId: string,
    questId: string
  ): Promise<QuestCompleteResponse | null> {
    try {
      const result = await http.apiPost<QuestCompleteResponse>(
        `/api/v1/quests/${vaultId}/${questId}/complete`,
        undefined,
        { _skipErrorNotification: true }
      )

      if (result.granted_rewards && result.granted_rewards.length > 0) {
        const rewardsText = result.granted_rewards
          .map((r) => r.amount || r.name || r.type || '???')
          .join(', ')
        toast.success(`Quest completed! Rewards: ${rewardsText}`)
      } else {
        toast.success('Quest completed!')
      }

      await fetchVaultQuests(vaultId)
      return result
    } catch (error: unknown) {
      const errorMessage = handleStoreError(error, 'Failed to complete quest')
      toast.error(errorMessage)
      throw error
    }
  }

  async function assignParty(
    vaultId: string,
    questId: string,
    dwellerIds: string[]
  ): Promise<void> {
    try {
      await http.apiPost(
        `/api/v1/quests/${vaultId}/${questId}/assign-party`,
        { dweller_ids: dwellerIds },
        { _skipErrorNotification: true }
      )
      toast.success('Party assigned successfully')
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage = handleStoreError(error, 'Failed to assign party')
      toast.error(errorMessage)
      throw error
    }
  }

  async function getParty(vaultId: string, questId: string): Promise<QuestPartyMember[]> {
    try {
      return await http.apiGet<QuestPartyMember[]>(
        `/api/v1/quests/${vaultId}/${questId}/party`,
        { _skipErrorNotification: true }
      )
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch party')
      throw error
    }
  }

  interface EligibleDweller {
    id: string
    first_name: string
    last_name: string | null
    level: number
    rarity: string
  }

  async function getEligibleDwellers(vaultId: string, questId: string): Promise<EligibleDweller[]> {
    try {
      const url = `/api/v1/quests/${vaultId}/${questId}/eligible-dwellers`
      return await http.apiGet<EligibleDweller[]>(url, { _skipErrorNotification: true })
    } catch (error: unknown) {
      handleStoreError(error, 'Failed to fetch eligible dwellers')
      throw error
    }
  }

  async function startQuest(vaultId: string, questId: string): Promise<void> {
    try {
      await http.apiPost(`/api/v1/quests/${vaultId}/${questId}/start`, undefined, {
        _skipErrorNotification: true,
      })
      toast.success('Quest started!')
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage = handleStoreError(error, 'Failed to start quest')
      toast.error(errorMessage)
      throw error
    }
  }

  return {
    quests,
    vaultQuests,
    isLoading,
    questPartyMap,
    questCategories,
    fetchAllQuests,
    fetchVaultQuests,
    fetchPartiesForActiveQuests,
    getQuest,
    assignQuest,
    completeQuest,
    assignParty,
    getParty,
    getEligibleDwellers,
    startQuest,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useQuestStore, import.meta.hot))
}
