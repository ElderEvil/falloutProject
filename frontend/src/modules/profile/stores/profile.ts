import { defineStore, acceptHMRUpdate } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfile, ProfileUpdate } from '../models/profile'
import type { AIUsageStats } from '../models/aiUsage'
import { apiGet, apiPut, ApiError } from '@/core/plugins/httpClient'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'

export interface DeathStatistics {
  total_dwellers_born: number
  total_dwellers_died: number
  deaths_by_cause: {
    health: number
    radiation: number
    incident: number
    exploration: number
    combat: number
  }
  revivable_count: number
  permanently_dead_count: number
}

export const useProfileStore = defineStore('profile', () => {
  const profile = ref<UserProfile | null>(null)
  const deathStatistics = ref<DeathStatistics | null>(null)
  const aiUsageStats = ref<AIUsageStats | null>(null)
  const loading = ref(false)
  const deathStatsLoading = ref(false)
  const aiUsageLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const hasProfile = computed(() => profile.value !== null)

  const quotaExceeded = computed(() => aiUsageStats.value?.quota?.quota_exceeded ?? false)
  const quotaWarning = computed(() => aiUsageStats.value?.quota?.quota_warning ?? false)

  const statistics = computed(() => {
    if (!profile.value) return null
    return {
      totalDwellersCreated: profile.value.total_dwellers_created,
      totalCapsEarned: profile.value.total_caps_earned,
      totalExplorations: profile.value.total_explorations,
      totalRoomsBuilt: profile.value.total_rooms_built,
    }
  })

  // Actions
  async function fetchProfile(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      profile.value = await apiGet<UserProfile>('/api/v1/users/me/profile')

      // Load user's preferred theme if available
      const { loadUserTheme } = useTheme()
      if (profile.value.preferences?.theme) {
        loadUserTheme(profile.value.preferences.theme as ThemeName)
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        error.value = typeof err.detail === 'string' ? err.detail : 'Failed to fetch profile'
      } else {
        error.value = 'Failed to fetch profile'
      }
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateProfile(data: ProfileUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      profile.value = await apiPut<UserProfile>('/api/v1/users/me/profile', data)

      // Update theme if it changed
      const { loadUserTheme } = useTheme()
      if (profile.value.preferences?.theme) {
        loadUserTheme(profile.value.preferences.theme as ThemeName)
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        error.value = typeof err.detail === 'string' ? err.detail : 'Failed to update profile'
      } else {
        error.value = 'Failed to update profile'
      }
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchDeathStatistics(): Promise<DeathStatistics | null> {
    deathStatsLoading.value = true
    try {
      const data = await apiGet<DeathStatistics>('/api/v1/users/me/profile/statistics')
      deathStatistics.value = data
      return data
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        console.error('Failed to fetch death statistics:', err.message)
      } else {
        console.error('Failed to fetch death statistics:', err)
      }
      return null
    } finally {
      deathStatsLoading.value = false
    }
  }

  async function fetchAIUsage(): Promise<AIUsageStats | null> {
    aiUsageLoading.value = true
    try {
      const data = await apiGet<AIUsageStats>('/api/v1/users/me/profile/ai-usage')
      aiUsageStats.value = data
      return data
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        console.error('Failed to fetch AI usage:', err.message)
      } else {
        console.error('Failed to fetch AI usage:', err)
      }
      return null
    } finally {
      aiUsageLoading.value = false
    }
  }

  async function fetchQuotaStatus(): Promise<AIUsageStats | null> {
    // Fetch fresh quota status from API (no caching)
    return fetchAIUsage()
  }

  function clearError(): void {
    error.value = null
  }

  return {
    profile,
    deathStatistics,
    aiUsageStats,
    loading,
    deathStatsLoading,
    aiUsageLoading,
    error,
    hasProfile,
    statistics,
    quotaExceeded,
    quotaWarning,
    fetchProfile,
    updateProfile,
    fetchDeathStatistics,
    fetchAIUsage,
    fetchQuotaStatus,
    clearError,
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useProfileStore, import.meta.hot))
}
