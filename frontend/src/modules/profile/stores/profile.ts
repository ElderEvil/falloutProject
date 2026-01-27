import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserProfile, ProfileUpdate } from '../models/profile'
import axios from '@/core/plugins/axios'
import { useTheme, type ThemeName } from '@/core/composables/useTheme'

// Death statistics type (matches backend response)
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
  // State
  const profile = ref<UserProfile | null>(null)
  const deathStatistics = ref<DeathStatistics | null>(null)
  const loading = ref(false)
  const deathStatsLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const hasProfile = computed(() => profile.value !== null)

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
      const response = await axios.get<UserProfile>('/api/v1/users/me/profile')
      profile.value = response.data

      // Load user's preferred theme if available
      const { loadUserTheme } = useTheme()
      if (profile.value.preferences?.theme) {
        loadUserTheme(profile.value.preferences.theme as ThemeName)
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to fetch profile'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function updateProfile(data: ProfileUpdate): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await axios.put<UserProfile>('/api/v1/users/me/profile', data)
      profile.value = response.data

      // Update theme if it changed
      const { loadUserTheme } = useTheme()
      if (profile.value.preferences?.theme) {
        loadUserTheme(profile.value.preferences.theme as ThemeName)
      }
    } catch (err: any) {
      error.value = err.response?.data?.detail || 'Failed to update profile'
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
    } catch (err: any) {
      console.error('Failed to fetch death statistics:', err)
      return null
    } finally {
      deathStatsLoading.value = false
    }
  }

  function clearError(): void {
    error.value = null
  }

  return {
    // State
    profile,
    deathStatistics,
    loading,
    deathStatsLoading,
    error,
    // Getters
    hasProfile,
    statistics,
    // Actions
    fetchProfile,
    updateProfile,
    fetchDeathStatistics,
    clearError,
  }
})
