import { computed } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import { authService } from '../services/authService'
import type { User } from '../types/user'

export const useAuthStore = defineStore('auth', () => {
  // State (using VueUse for reactive localStorage)
  const token = useLocalStorage<string | null>('token', null)
  const refreshToken = useLocalStorage<string | null>('refreshToken', null)
  const user = useLocalStorage<User | null>('user', null, {
    serializer: {
      read: (v: string) => {
        try {
          return JSON.parse(v)
        } catch {
          return null
        }
      },
      write: (v: User | null) => JSON.stringify(v)
    }
  })

  // Getters
  const isAuthenticated = computed(() => !!token.value)
  const isSuperuser = computed(() => user.value?.is_superuser ?? false)

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const response = await authService.login({ username, password })

      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token

      if (!token.value || !refreshToken.value) {
        return false
      }

      await fetchUser()
      return true
    } catch (error) {
      console.error('Login failed', error)
      return false
    }
  }

  async function register(username: string, email: string, password: string): Promise<boolean> {
    try {
      const response = await authService.register({ username, email, password })

      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token

      if (!token.value || !refreshToken.value) {
        return false
      }

      // Registration returns user data with tokens, so we can directly set it
      const { access_token: _access_token, refresh_token: _refresh_token, token_type: _token_type, ...userData } = response.data
      user.value = userData

      return true
    } catch (error) {
      console.error('Registration failed', error)
      return false
    }
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return

    try {
      const response = await authService.getCurrentUser()
      user.value = response.data
    } catch (error) {
      console.error('Failed to fetch user', error)
      await logout()
    }
  }

  async function refreshAccessToken(): Promise<void> {
    if (!refreshToken.value) return

    try {
      const response = await authService.refreshToken(refreshToken.value)
      token.value = response.data.access_token
      // Backend rotates refresh tokens, so update it
      if (response.data.refresh_token) {
        refreshToken.value = response.data.refresh_token
      }
    } catch (error) {
      console.error('Failed to refresh token', error)
      await logout()
    }
  }

  async function logout(): Promise<void> {
    try {
      if (token.value) {
        await authService.logout()
      }
    } catch (error) {
      console.error('Logout failed', error)
    } finally {
      // Clear all stored data (VueUse handles localStorage automatically)
      token.value = null
      refreshToken.value = null
      user.value = null
    }
  }

  // Initialize: fetch user if we have a token but no user data
  if (token.value && !user.value) {
    fetchUser()
  }

  return {
    // State
    token,
    refreshToken,
    user,
    // Getters
    isAuthenticated,
    isSuperuser,
    // Actions
    login,
    register,
    fetchUser,
    refreshAccessToken,
    logout
  }
})
