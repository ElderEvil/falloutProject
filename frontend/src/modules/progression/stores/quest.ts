import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Quest, QuestPartyMember, VaultQuest } from '../models/quest'
import { useToast } from '@/core/composables/useToast'
import { useAuthStore } from '@/modules/auth/stores/auth'

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
  const authStore = useAuthStore()

  // State
  const quests = ref<Quest[]>([])
  const vaultQuests = ref<VaultQuest[]>([])
  const unlockedVaultQuests = ref<VaultQuest[]>([])
  const isLoading = ref(false)
  const questPartyMap = ref<Record<string, QuestPartyMember[]>>({})

  const getAuthHeaders = () => {
    const token = authStore.token || localStorage.getItem('token')?.replace(/^"|"$/g, '')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  // Computed
  // Quest is available if visible and not started yet (can assign party)
  const activeQuests = computed(() =>
    vaultQuests.value.filter((quest) => quest.is_visible && quest.started_at != null && !quest.is_completed)
  )

  const completedQuests = computed(() => vaultQuests.value.filter((quest) => quest.is_completed))

  // Quest is available if visible but not started (can still assign party)
  const availableQuests = computed(() =>
    vaultQuests.value.filter((quest) => quest.is_visible && quest.started_at == null && !quest.is_completed)
  )

  // All visible quests (for "show all" toggle)
  const allVisibleQuests = computed(() =>
    vaultQuests.value.filter((quest) => quest.is_visible)
  )

  // Actions
  async function fetchAllQuests(): Promise<void> {
    try {
      isLoading.value = true
      const response = await axios.get<Quest[]>('/api/v1/quests/', { headers: getAuthHeaders() })
      quests.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch quests:', error)
      toast.error('Failed to load quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchVaultQuests(vaultId: string): Promise<void> {
    try {
      isLoading.value = true
      const response = await axios.get<VaultQuest[]>(`/api/v1/quests/${vaultId}/`, { headers: getAuthHeaders() })
      vaultQuests.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch vault quests:', error)
      toast.error('Failed to load vault quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchAvailableQuests(vaultId: string): Promise<void> {
    try {
      isLoading.value = true
      const url = `/api/v1/quests/${vaultId}/available`
      const response = await axios.get<VaultQuest[]>(url, {
        headers: getAuthHeaders(),
      })
      unlockedVaultQuests.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch available quests:', error)
      toast.error('Failed to load available quests')
      throw error
    } finally {
      isLoading.value = false
    }
  }

  async function fetchPartiesForActiveQuests(vaultId: string): Promise<void> {
    const active = vaultQuests.value.filter((q) => q.is_visible && q.started_at != null && !q.is_completed)
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
      const response = await axios.get<Quest>(`/api/v1/quests/${vaultId}/${questId}`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch quest:', error)
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
      // Refresh vault quests
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to assign quest'
      console.error('Failed to assign quest:', error)
      toast.error(errorMessage)
      throw error
    }
  }

  async function completeQuest(
    vaultId: string,
    questId: string
  ): Promise<QuestCompleteResponse | null> {
    try {
      const response = await axios.post<QuestCompleteResponse>(
        `/api/v1/quests/${vaultId}/${questId}/complete`
      )
      const result = response.data

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
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to complete quest'
      console.error('Failed to complete quest:', error)
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
      await axios.post(`/api/v1/quests/${vaultId}/${questId}/assign-party`, {
        dweller_ids: dwellerIds,
      })
      toast.success('Party assigned successfully')
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to assign party'
      console.error('Failed to assign party:', error)
      toast.error(errorMessage)
      throw error
    }
  }

  async function getParty(vaultId: string, questId: string): Promise<QuestPartyMember[]> {
    try {
      const response = await axios.get<QuestPartyMember[]>(`/api/v1/quests/${vaultId}/${questId}/party`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch party:', error)
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
      const response = await axios.get<EligibleDweller[]>(`/api/v1/quests/${vaultId}/${questId}/eligible-dwellers`)
      return response.data
    } catch (error: unknown) {
      console.error('Failed to fetch eligible dwellers:', error)
      throw error
    }
  }

  async function startQuest(vaultId: string, questId: string): Promise<void> {
    try {
      await axios.post(`/api/v1/quests/${vaultId}/${questId}/start`)
      toast.success('Quest started!')
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Failed to start quest'
      console.error('Failed to start quest:', error)
      toast.error(errorMessage)
      throw error
    }
  }

  return {
    quests,
    vaultQuests,
    unlockedVaultQuests,
    isLoading,
    questPartyMap,
    activeQuests,
    availableQuests,
    allVisibleQuests,
    completedQuests,
    fetchAllQuests,
    fetchVaultQuests,
    fetchAvailableQuests,
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
