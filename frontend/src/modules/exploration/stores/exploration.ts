import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '@/core/plugins/axios'
import { useToast } from '@/core/composables/useToast'

export interface ExplorationEvent {
  type: string;
  description: string;
  timestamp: string;
  time_elapsed_hours: number;
  loot?: {
    item: {
      name: string
      rarity: string
      value: number
    }
    caps: number
  };
}

export interface LootItem {
  item_name: string;
  quantity: number;
  rarity: string;
  item_type?: string; // 'junk', 'weapon', or 'outfit'
  found_at: string;
}

export interface Exploration {
  id: string;
  vault_id: string;
  dweller_id: string;
  status: 'active' | 'completed' | 'recalled';
  duration: number;
  start_time: string;
  end_time: string | null;
  events: ExplorationEvent[];
  loot_collected: LootItem[];
  total_distance: number;
  total_caps_found: number;
  enemies_encountered: number;
  created_at: string;
  updated_at: string;
  dweller_strength: number;
  dweller_perception: number;
  dweller_endurance: number;
  dweller_charisma: number;
  dweller_intelligence: number;
  dweller_agility: number;
  dweller_luck: number;
  stimpaks: number;
  radaways: number;
}

export interface ExplorationProgress {
  id: string;
  status: 'ACTIVE' | 'COMPLETED' | 'RECALLED';
  progress_percentage: number;
  time_remaining_seconds: number;
  elapsed_time_seconds: number;
  events: ExplorationEvent[];
  loot_collected: LootItem[];
  stimpaks: number;
  radaways: number;
}

export interface RewardsSummary {
  caps: number;
  items: LootItem[];
  experience: number;
  distance: number;
  enemies_defeated: number;
  events_encountered: number;
  overflow_items?: LootItem[];
  progress_percentage?: number;
  recalled_early?: boolean;
}

export const useExplorationStore = defineStore('exploration', () => {
  const toast = useToast()

  // State
  const explorations = ref<Exploration[]>([])
  const activeExplorations = ref<Record<string, Exploration>>({})
  const lastRewards = ref<RewardsSummary | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const getExplorationByDwellerId = computed(() => (dwellerId: string) => {
    return explorations.value.find((e) => e.dweller_id === dwellerId && e.status === 'active')
  })

  const getActiveExplorationsForVault = computed(() => (vaultId: string) => {
    return explorations.value.filter((e) => e.vault_id === vaultId && e.status === 'active')
  })

  const isDwellerExploring = computed(() => (dwellerId: string) => {
    return explorations.value.some((e) => e.dweller_id === dwellerId && e.status === 'active')
  })

  // Actions
  async function sendDwellerToWasteland(
    vaultId: string,
    dwellerId: string,
    duration: number,
    token: string,
    stimpaks: number = 0,
    radaways: number = 0
  ): Promise<Exploration> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.post(
        `/api/v1/explorations/send?vault_id=${vaultId}`,
        {
          dweller_id: dwellerId,
          duration,
          stimpaks,
          radaways
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )

      const exploration = response.data
      explorations.value.push(exploration)
      activeExplorations.value[exploration.id] = exploration

      return exploration
    } catch (err) {
      console.error('Failed to send dweller to wasteland:', err)
      error.value = 'Failed to send dweller to wasteland'
      toast.error('Failed to send dweller to wasteland')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchExplorationsByVault(vaultId: string, token: string, activeOnly = true): Promise<Exploration[]> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.get(
        `/api/v1/explorations/vault/${vaultId}?active_only=${activeOnly}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )

      explorations.value = response.data
      // Update active explorations map
      activeExplorations.value = {}
      response.data
        .filter((e: Exploration) => e.status === 'active')
        .forEach((e: Exploration) => {
          activeExplorations.value[e.id] = e
        })

      return response.data
    } catch (err) {
      console.error('Failed to fetch explorations:', err)
      error.value = 'Failed to fetch explorations'
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function fetchExplorationDetails(explorationId: string, token: string): Promise<Exploration> {
    try {
      const response = await axios.get(`/api/v1/explorations/${explorationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      // Update in explorations list
      const index = explorations.value.findIndex((e) => e.id === explorationId)
      if (index !== -1) {
        explorations.value[index] = response.data
      }

      // Update in active explorations
      if (response.data.status === 'active') {
        activeExplorations.value[explorationId] = response.data
      } else {
        delete activeExplorations.value[explorationId]
      }

      return response.data
    } catch (err) {
      console.error('Failed to fetch exploration details:', err)
      throw err
    }
  }

  async function fetchExplorationProgress(explorationId: string, token: string): Promise<ExplorationProgress> {
    try {
      const response = await axios.get(`/api/v1/explorations/${explorationId}/progress`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      return response.data as ExplorationProgress
    } catch (err) {
      console.error('Failed to fetch exploration progress:', err)
      throw err
    }
  }

  async function recallDweller(explorationId: string, token: string): Promise<any> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.post(
        `/api/v1/explorations/${explorationId}/recall`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )

      const { exploration, rewards_summary } = response.data
      lastRewards.value = rewards_summary

      // Update exploration in state
      const index = explorations.value.findIndex((e) => e.id === explorationId)
      if (index !== -1) {
        explorations.value[index] = exploration
      }

      // Remove from active explorations
      delete activeExplorations.value[explorationId]

      toast.success('Dweller recalled from wasteland!')
      return response.data
    } catch (err) {
      console.error('Failed to recall dweller:', err)
      error.value = 'Failed to recall dweller'
      toast.error('Failed to recall dweller')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  async function completeExploration(explorationId: string, token: string): Promise<any> {
    isLoading.value = true
    error.value = null
    try {
      const response = await axios.post(
        `/api/v1/explorations/${explorationId}/complete`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      )

      const { exploration, rewards_summary } = response.data
      lastRewards.value = rewards_summary

      // Update exploration in state
      const index = explorations.value.findIndex((e) => e.id === explorationId)
      if (index !== -1) {
        explorations.value[index] = exploration
      }

      // Remove from active explorations
      delete activeExplorations.value[explorationId]

      toast.success('Exploration completed successfully!')
      return response.data
    } catch (err) {
      console.error('Failed to complete exploration:', err)
      error.value = 'Failed to complete exploration'
      toast.error('Failed to complete exploration')
      throw err
    } finally {
      isLoading.value = false
    }
  }

  function clearLastRewards(): void {
    lastRewards.value = null
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    explorations,
    activeExplorations,
    lastRewards,
    isLoading,
    error,
    // Getters
    getExplorationByDwellerId,
    getActiveExplorationsForVault,
    isDwellerExploring,
    // Actions
    sendDwellerToWasteland,
    fetchExplorationsByVault,
    fetchExplorationDetails,
    fetchExplorationProgress,
    recallDweller,
    completeExploration,
    clearLastRewards,
    clearError
  }
})
