import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Quest, QuestPartyMember, VaultQuest } from '../models/quest'
import { useToast } from '@/core/composables/useToast'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { handleStoreError } from '@/core/utils/errorHandler'

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

export interface EligibleDweller {
  id: string
  first_name: string
  last_name: string | null
  level: number
  rarity: string
}

export const useQuestStore = defineStore('quest', () => {
  const toast = useToast()
  const authStore = useAuthStore()

  // State
  const quests = ref<Quest[]>([])
  const vaultQuests = ref<VaultQuest[]>([])
  const isLoading = ref(false)
  const questPartyMap = ref<Record<string, QuestPartyMember[]>>({})

  const getAuthHeaders = () => {
    const token = authStore.token || localStorage.getItem('token')?.replace(/^"|"$/g, '')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  // Computed
  // Single pass classification of all vault quests
  const questCategories = computed(() => {
    const active: VaultQuest[] = []
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
      } else if (quest.started_at != null) {
        active.push(quest)
      } else {
        available.push(quest)
      }
    }

    return { active, readyToClaim, completed, available, allVisible }
  })

  // Actions
  async function fetchAllQuests(): Promise<void> {
    try {
      isLoading.value = true
      const response = await axios.get<Quest[]>('/api/v1/quests/', { headers: getAuthHeaders() })
      quests.value = response.data
    } catch (error: unknown) {
      toast.error('Failed to load quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVaultQuests(vaultId: string, options?: { silent?: boolean }): Promise<void> {
    const silent = options?.silent ?? false
    try {
      if (!silent) isLoading.value = true
      const response = await axios.get<unknown>(`/api/v1/quests/${vaultId}/`, {
        headers: getAuthHeaders(),
      })
      if (!Array.isArray(response.data)) {
        throw new TypeError('Expected a list of vault quests')
      }
      vaultQuests.value = response.data as VaultQuest[]
    } catch (error: unknown) {
      if (!silent) toast.error('Failed to load vault quests')
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

  async function getQuest(vaultId: string, questId: string): Promise<Quest> {
    try {
      const response = await axios.get<Quest>(`/api/v1/quests/${vaultId}/${questId}`)
      return response.data
    } catch (error: unknown) {
      toast.error('Failed to load quest details')
      throw error
    }
  }

  async function assignQuest(vaultId: string, questId: string, isVisible = true): Promise<void> {
    try {
      await axios.post(`/api/v1/quests/${vaultId}/${questId}/assign`, null, {
        params: { is_visible: isVisible },
      })
      toast.success('Quest assigned successfully')
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to assign quest'
      toast.error(errorMessage)
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
      const response = await axios.post<QuestCompleteResponse>(
        `/api/v1/quests/${vaultId}/${questId}/claim-rewards`
      )
      result = response.data

      if (result.granted_rewards && result.granted_rewards.length > 0) {
        const rewardsText = result.granted_rewards
          .map((r) => {
            if (r.name) return `${r.amount ? `${r.amount}× ` : ''}${r.name}`
            const rewardType = r.reward_type ?? r.type
            const label = typeof rewardType === 'string' ? rewardType.toLowerCase() : 'reward'
            return `${r.amount ?? ''} ${label}`.trim()
          })
          .join(', ')
        toast.success(`Rewards claimed: ${rewardsText}`)
      } else {
        toast.success('Quest rewards claimed!')
      }
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to claim quest rewards'
      toast.error(errorMessage)
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

  async function assignParty(
    vaultId: string,
    questId: string,
    dwellerIds: string[]
  ): Promise<void> {
    try {
      await axios.post(`/api/v1/quests/${vaultId}/${questId}/assign-party`, {
        dweller_ids: dwellerIds,
      })
      toast.success('Party assigned successfully')
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to assign party'
      toast.error(errorMessage)
      throw error
    }
    // Refresh vault quests (silent — mutation already succeeded)
    try {
      await fetchVaultQuests(vaultId, { silent: true })
    } catch {
      toast.warning('Party was assigned, but the quest list could not refresh')
    }
  }

  async function getParty(vaultId: string, questId: string): Promise<QuestPartyMember[]> {
    try {
      const response = await axios.get<QuestPartyMember[]>(
        `/api/v1/quests/${vaultId}/${questId}/party`
      )
      return response.data
    } catch (error: unknown) {
      toast.error('Failed to load quest party')
      throw error
    }
  }

  async function getEligibleDwellers(vaultId: string, questId: string): Promise<EligibleDweller[]> {
    try {
      const url = `/api/v1/quests/${vaultId}/${questId}/eligible-dwellers`
      const response = await axios.get<EligibleDweller[]>(url)
      return response.data
    } catch (error: unknown) {
      toast.error('Failed to load eligible dwellers')
      throw error
    }
  }

  async function startQuest(vaultId: string, questId: string): Promise<void> {
    try {
      await axios.post(`/api/v1/quests/${vaultId}/${questId}/start`)
      toast.success('Quest started!')
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to start quest'
      toast.error(errorMessage)
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
    fetchAllQuests,
    fetchVaultQuests,
    fetchPartiesForActiveQuests,
    getQuest,
    assignQuest,
    claimQuestRewards,
    assignParty,
    getParty,
    getEligibleDwellers,
    startQuest,
  }
})
