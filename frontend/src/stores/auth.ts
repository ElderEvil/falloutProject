import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import axios from '@/plugins/axios'
import type { User } from '@/types/user'

export const useAuthStore = defineStore('auth', () => {
  // State (using VueUse for reactive localStorage)
  const token = useLocalStorage<string | null>('token', null)
  const refreshToken = useLocalStorage<string | null>('refreshToken', null)
  const user = useLocalStorage<User | null>('user', null)

  // Getters
  const isAuthenticated = computed(() => !!token.value)

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const formData = new URLSearchParams()
      formData.append('username', username)
      formData.append('password', password)

      const response = await axios.post('/api/v1/login/access-token', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      })

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
      const response = await axios.post('/api/v1/users/open', {
        username,
        email,
        password
      })

      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token

      if (!token.value || !refreshToken.value) {
        return false
      }

      await fetchUser()
      return true
    } catch (error) {
      console.error('Registration failed', error)
      return false
    }
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return

    try {
      const response = await axios.get('/api/v1/users/me', {
        headers: {
          Authorization: `Bearer ${token.value}`
        }
      })
      user.value = response.data
    } catch (error) {
      console.error('Failed to fetch user', error)
      await logout()
    }
  }

  async function refreshAccessToken(): Promise<void> {
    if (!refreshToken.value) return

    try {
      const formData = new URLSearchParams()
      formData.append('refresh_token', refreshToken.value)

      const response = await axios.post('/api/v1/login/refresh-token', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      })

      token.value = response.data.access_token
    } catch (error) {
      console.error('Failed to refresh token', error)
      await logout()
    }
  }

  async function logout(): Promise<void> {
    try {
      if (token.value) {
        await axios.post(
          '/api/v1/logout',
          {},
          {
            headers: {
              Authorization: `Bearer ${token.value}`
            }
          }
        )
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

  return {
    // State
    token,
    refreshToken,
    user,
    // Getters
    isAuthenticated,
    // Actions
    login,
    register,
    fetchUser,
    refreshAccessToken,
    logout
  }
})
