import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfile, ProfileUpdate } from '../models/profile'
import type { AIUsageStats } from '../models/aiUsage'
import { fetchAIUsage as fetchAIUsageRequest } from '../services/aiUsageService'
import { handleStoreError } from '@/core/utils/errorHandler'
import axios from '@/core/plugins/axios'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'
import type { DeathStatistics } from '@/core/types/death'

export type { DeathStatistics } from '@/core/types/death'

export const useProfileStore = defineStore('profile', () => {
  const profile = ref<UserProfile | null>(null)
  const deathStatistics = ref<DeathStatistics | null>(null)
  const aiUsageStats = ref<AIUsageStats | null>(null)
  const loading = ref(false)
  const profileRefreshing = ref(false)
  const deathStatsLoading = ref(false)
  const aiUsageLoading = ref(false)
  const error = ref<string | null>(null)
  let profileVersion = 0

  // Getters
  const hasProfile = computed(() => profile.value !== null)

  const quotaExceeded = computed(() => aiUsageStats.value?.quota_exceeded ?? false)
  const quotaWarning = computed(() => aiUsageStats.value?.quota_warning ?? false)

  const statistics = computed(() => {
    if (!profile.value) return null
    return {
      totalDwellersCreated: profile.value.total_dwellers_created,
      totalCapsEarned: profile.value.total_caps_earned,
      totalExplorations: profile.value.total_explorations,
      totalRoomsBuilt: profile.value.total_rooms_built,
    }
  })

  function applyProfile(nextProfile: UserProfile): void {
    profile.value = nextProfile
    const { loadUserTheme } = useTheme()
    if (profile.value.preferences?.theme) loadUserTheme(profile.value.preferences.theme as ThemeName)
  }

  async function loadProfile(): Promise<UserProfile> {
    const response = await axios.get<UserProfile>('/api/v1/users/me/profile')
    return response.data
  }

  async function fetchProfile(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      applyProfile(await loadProfile())
    } catch (err: unknown) {
      error.value = handleStoreError(err, 'Failed to fetch profile')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function refreshProfile(): Promise<void> {
    profileRefreshing.value = true
    const version = profileVersion
    try {
      const nextProfile = await loadProfile()
      if (version === profileVersion) applyProfile(nextProfile)
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to refresh profile')
    } finally {
      profileRefreshing.value = false
    }
  }

  async function updateProfile(data: ProfileUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await axios.put<UserProfile>('/api/v1/users/me/profile', data)
      profileVersion += 1
      applyProfile(response.data)
    } catch (err: unknown) {
      error.value = handleStoreError(err, 'Failed to update profile')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function fetchDeathStatistics(): Promise<DeathStatistics | null> {
    deathStatsLoading.value = true
    try {
      const response = await axios.get<DeathStatistics>('/api/v1/users/me/profile/statistics')
      deathStatistics.value = response.data
      return response.data
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to fetch death statistics')
      return null
    } finally {
      deathStatsLoading.value = false
    }
  }

  async function fetchAIUsage(): Promise<AIUsageStats | null> {
    aiUsageLoading.value = true
    try {
      const stats = await fetchAIUsageRequest()
      aiUsageStats.value = stats
      return stats
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to fetch AI usage')
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
    profileRefreshing,
    deathStatsLoading,
    aiUsageLoading,
    error,
    hasProfile,
    statistics,
    quotaExceeded,
    quotaWarning,
    fetchProfile,
    refreshProfile,
    updateProfile,
    fetchDeathStatistics,
    fetchAIUsage,
    fetchQuotaStatus,
    clearError,
  }
})
