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
  let session = 0
  let saveChain: Promise<void> = Promise.resolve()

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
    if (profile.value.preferences?.theme)
      loadUserTheme(profile.value.preferences.theme as ThemeName)
  }

  async function loadProfile(): Promise<UserProfile> {
    const response = await axios.get<UserProfile>('/api/v1/users/me/profile')
    return response.data
  }

  async function fetchProfile(): Promise<void> {
    const requestSession = session
    loading.value = true
    error.value = null
    try {
      const nextProfile = await loadProfile()
      if (requestSession !== session) return
      applyProfile(nextProfile)
    } catch (err: unknown) {
      error.value = handleStoreError(err, 'Failed to fetch profile')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function refreshProfile(): Promise<void> {
    const requestSession = session
    profileRefreshing.value = true
    const version = profileVersion
    try {
      const nextProfile = await loadProfile()
      if (requestSession === session && version === profileVersion) applyProfile(nextProfile)
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to refresh profile')
    } finally {
      profileRefreshing.value = false
    }
  }

  async function updateProfile(data: ProfileUpdate): Promise<void> {
    const requestSession = session
    loading.value = true
    error.value = null
    try {
      const response = await axios.put<UserProfile>('/api/v1/users/me/profile', data)
      if (requestSession !== session) return
      profileVersion += 1
      applyProfile(response.data)
    } catch (err: unknown) {
      error.value = handleStoreError(err, 'Failed to update profile')
      throw err
    } finally {
      loading.value = false
    }
  }

  async function ensureProfileLoaded(): Promise<void> {
    if (profile.value !== null || loading.value) return
    try {
      await fetchProfile()
    } catch {
      // fetchProfile already records the error and rethrows; swallow here so
      // boot-time callers can proceed without crashing.
    }
  }

  function clearProfile(): void {
    session += 1
    saveChain = Promise.resolve()
    profile.value = null
    deathStatistics.value = null
    aiUsageStats.value = null
    error.value = null
  }

  async function savePreferences(patch: Record<string, unknown>): Promise<void> {
    const requestSession = session
    const run = saveChain.then(async () => {
      const response = await axios.put<UserProfile>('/api/v1/users/me/profile', {
        preferences: { ...profile.value?.preferences, ...patch },
      })
      if (requestSession !== session) return
      profileVersion += 1
      applyProfile(response.data)
    })
    saveChain = run.catch(() => {})
    return run
  }

  async function fetchDeathStatistics(): Promise<DeathStatistics | null> {
    const requestSession = session
    deathStatsLoading.value = true
    try {
      const response = await axios.get<DeathStatistics>('/api/v1/users/me/profile/statistics')
      if (requestSession !== session) return null
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
    const requestSession = session
    aiUsageLoading.value = true
    try {
      const stats = await fetchAIUsageRequest()
      if (requestSession !== session) return null
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
    ensureProfileLoaded,
    clearProfile,
    savePreferences,
    fetchDeathStatistics,
    fetchAIUsage,
    fetchQuotaStatus,
    clearError,
  }
})

/**
 * Whether routine exploration-update notifications are disabled by the user's
 * notification preferences. Defaults to enabled (false) when there is no
 * profile, notifications object, or disabled_categories list — matching the
 * server-side default.
 */
export function explorationUpdatesDisabled(): boolean {
  const profileStore = useProfileStore()
  const settings = profileStore.profile?.preferences?.notifications
  if (!settings || typeof settings !== 'object' || Array.isArray(settings)) return false
  const disabled = (settings as Record<string, unknown>).disabled_categories
  return Array.isArray(disabled) && disabled.includes('exploration_updates')
}
