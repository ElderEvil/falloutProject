import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export function useAuth() {
  const authStore = useAuthStore()

  return {
    // State
    isAuthenticated: computed(() => authStore.isAuthenticated),
    user: computed(() => authStore.user),
    token: computed(() => authStore.token),
    // Actions
    login: authStore.login,
    logout: authStore.logout,
    register: authStore.register,
    fetchUser: authStore.fetchUser,
    refreshAccessToken: authStore.refreshAccessToken
  }
}
