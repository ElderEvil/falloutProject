import { computed } from 'vue'
import { useStorageStore } from '@/modules/storage/stores/storage'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import {
  AUTH_TOKENS_REFRESHED_EVENT,
  type RefreshedAuthTokens,
} from '@/core/utils/authSessionEvents'
import { authService } from '../services/authService'
import type { User } from '../types/user'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useProfileStore } from '@/modules/profile/stores/profile'

export const useAuthStore = defineStore('auth', () => {
  const toast = useToast()

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
      write: (v: User | null) => JSON.stringify(v),
    },
  })

  if (typeof window !== 'undefined') {
    window.addEventListener(AUTH_TOKENS_REFRESHED_EVENT, (event) => {
      const { token: refreshedToken, refreshToken: refreshedRefreshToken } = (
        event as CustomEvent<RefreshedAuthTokens>
      ).detail
      token.value = refreshedToken
      if (refreshedRefreshToken) refreshToken.value = refreshedRefreshToken
    })
  }

  // Getters
  const isAuthenticated = computed(() => !!token.value)
  const isSuperuser = computed(() => user.value?.is_superuser ?? false)

  // Invalidate account-owned state before replacing credentials or user identity.
  function clearSession(): void {
    useVaultStore().clearSession()
    useStorageStore().reset()
    useProfileStore().clearProfile()
  }

  // Actions
  async function login(username: string, password: string): Promise<boolean> {
    try {
      const response = await authService.login({ username, password })

      clearSession()
      user.value = null
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token

      if (!token.value || !refreshToken.value) {
        return false
      }

      await fetchUser()
      return true
    } catch (error) {
      handleStoreError(error, 'Login failed')
      return false
    }
  }

  async function register(username: string, email: string, password: string): Promise<boolean> {
    try {
      const response = await authService.register({ username, email, password })

      clearSession()
      user.value = null
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token

      if (!token.value || !refreshToken.value) {
        return false
      }

      // Registration returns user data with tokens, so we can directly set it
      const {
        access_token: _access_token,
        refresh_token: _refresh_token,
        token_type: _token_type,
        ...userData
      } = response.data
      user.value = userData

      return true
    } catch (error) {
      handleStoreError(error, 'Registration failed')
      return false
    }
  }

  async function fetchUser(): Promise<void> {
    if (!token.value) return

    try {
      const response = await authService.getCurrentUser()
      if (user.value?.id && user.value.id !== response.data.id) {
        clearSession()
      }
      user.value = response.data
    } catch (error) {
      handleStoreError(error, 'Failed to fetch user')
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
      handleStoreError(error, 'Failed to refresh token')
      await logout()
    }
  }

  async function updateAccount(payload: {
    username?: string | null
    email?: string | null
  }): Promise<boolean> {
    const requestedEmail = payload.email ?? null
    const previousEmail = user.value?.email ?? null
    const emailChanging =
      requestedEmail !== null &&
      requestedEmail.toLowerCase() !== (previousEmail ?? '').toLowerCase()

    const body: { username?: string; email?: string } = {}
    if (payload.username) body.username = payload.username
    if (requestedEmail) body.email = requestedEmail

    try {
      const response = await authService.updateAccount(body)
      user.value = response.data
      if (emailChanging) toast.success(`Verification link sent to ${requestedEmail}`)
      return true
    } catch (error) {
      const status = (error as { status?: number | null }).status
      if (status === 502 && requestedEmail) {
        await fetchUser()
        if (user.value?.email?.toLowerCase() === requestedEmail.toLowerCase()) {
          toast.warning('Email updated; verification email could not be sent.')
          return true
        }
      }
      handleStoreError(error, 'Failed to update account')
      return false
    }
  }

  async function verifyEmail(verificationToken: string): Promise<boolean> {
    try {
      await authService.verifyEmail(verificationToken)
      if (token.value) await fetchUser()
      return true
    } catch (error) {
      handleStoreError(error, 'Email verification failed')
      return false
    }
  }

  async function resendVerificationEmail(): Promise<boolean> {
    try {
      await authService.resendVerificationEmail()
      return true
    } catch (error) {
      handleStoreError(error, 'Failed to resend verification email')
      return false
    }
  }

  async function logout(): Promise<void> {
    try {
      if (token.value) {
        await authService.logout()
      }
    } catch (error) {
      handleStoreError(error, 'Logout failed')
    } finally {
      // Clear all stored data (VueUse handles localStorage automatically)
      clearSession()
      token.value = null
      refreshToken.value = null
      user.value = null
    }
  }

  // Initialize: fetch user if we have a token but no user data
  if (token.value && !user.value) {
    clearSession()
    void fetchUser()
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
    updateAccount,
    verifyEmail,
    resendVerificationEmail,
    logout,
  }
})
