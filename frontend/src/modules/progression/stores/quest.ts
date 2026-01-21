import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from '@/core/plugins/axios'
import type { Quest, VaultQuest } from '../models/quest'
import { useToast } from '@/core/composables/useToast'

export const useQuestStore = defineStore('quest', () => {
  const toast = useToast()

  // State
  const quests = ref<Quest[]>([])
  const vaultQuests = ref<VaultQuest[]>([])
  const isLoading = ref(false)

  // Computed
  const activeQuests = computed(() =>
    vaultQuests.value.filter((quest) => quest.is_visible && !quest.is_completed)
  )

  const completedQuests = computed(() =>
    vaultQuests.value.filter((quest) => quest.is_completed)
  )

  const availableQuests = computed(() => {
    const assignedQuestIds = new Set(vaultQuests.value.map((vq) => vq.id))
    return quests.value.filter((quest) => !assignedQuestIds.has(quest.id))
  })

  // Actions
  async function fetchAllQuests(): Promise<void> {
    try {
      isLoading.value = true
      const response = await axios.get<Quest[]>('/api/v1/quests/')
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
      const response = await axios.get<VaultQuest[]>(`/api/v1/quests/${vaultId}/`)
      vaultQuests.value = response.data
    } catch (error: unknown) {
      console.error('Failed to fetch vault quests:', error)
      toast.error('Failed to load vault quests')
      throw error
    } finally {
      isLoading.value = false
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
        params: { is_visible: isVisible }
      })
      toast.success('Quest assigned successfully')
      // Refresh vault quests
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage = (error as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to assign quest'
      console.error('Failed to assign quest:', error)
      toast.error(errorMessage)
      throw error
    }
  }

  async function completeQuest(vaultId: string, questId: string): Promise<void> {
    try {
      await axios.post(`/api/v1/quests/${vaultId}/${questId}/complete`)
      toast.success('Quest completed! Rewards claimed.')
      // Refresh vault quests
      await fetchVaultQuests(vaultId)
    } catch (error: unknown) {
      const errorMessage = (error as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail || 'Failed to complete quest'
      console.error('Failed to complete quest:', error)
      toast.error(errorMessage)
      throw error
    }
  }

  return {
    // State
    quests,
    vaultQuests,
    isLoading,
    // Computed
    activeQuests,
    availableQuests,
    completedQuests,
    // Actions
    fetchAllQuests,
    fetchVaultQuests,
    getQuest,
    assignQuest,
    completeQuest
  }
})
