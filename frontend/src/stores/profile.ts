import { defineStore } from 'pinia'
import type { UserProfile, ProfileUpdate } from '@/models/profile'
import axios from '@/plugins/axios'

export const useProfileStore = defineStore('profile', {
  state: () => ({
    profile: null as UserProfile | null,
    loading: false,
    error: null as string | null
  }),

  getters: {
    hasProfile: (state) => state.profile !== null,
    statistics: (state) => {
      if (!state.profile) return null
      return {
        totalDwellersCreated: state.profile.total_dwellers_created,
        totalCapsEarned: state.profile.total_caps_earned,
        totalExplorations: state.profile.total_explorations,
        totalRoomsBuilt: state.profile.total_rooms_built
      }
    }
  },

  actions: {
    async fetchProfile() {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get<UserProfile>('/api/v1/users/me/profile')
        this.profile = response.data
      } catch (error: any) {
        this.error = error.response?.data?.detail || 'Failed to fetch profile'
        throw error
      } finally {
        this.loading = false
      }
    },

    async updateProfile(data: ProfileUpdate) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.put<UserProfile>('/api/v1/users/me/profile', data)
        this.profile = response.data
      } catch (error: any) {
        this.error = error.response?.data?.detail || 'Failed to update profile'
        throw error
      } finally {
        this.loading = false
      }
    },

    clearError() {
      this.error = null
    }
  }
})
