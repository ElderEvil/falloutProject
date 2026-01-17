import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { jwtDecode } from 'jwt-decode'

interface JWTPayload {
  exp: number
  sub: string
}

const REFRESH_BEFORE_EXPIRY_MS = 5 * 60 * 1000 // 5 minutes before expiry
const CHECK_INTERVAL_MS = 60 * 1000 // Check every minute

export function useTokenRefresh() {
  const authStore = useAuthStore()
  const refreshTimer = ref<ReturnType<typeof setInterval> | null>(null)
  const isRefreshing = ref(false)

  /**
   * Decode JWT and get expiration timestamp
   */
  function getTokenExpiration(token: string): number | null {
    try {
      const decoded = jwtDecode<JWTPayload>(token)
      return decoded.exp * 1000 // Convert to milliseconds
    } catch (error) {
      console.error('Failed to decode token:', error)
      return null
    }
  }

  /**
   * Check if token needs refresh (within 5 minutes of expiry)
   */
  function shouldRefreshToken(token: string | null): boolean {
    if (!token) return false

    const expiresAt = getTokenExpiration(token)
    if (!expiresAt) return false

    const now = Date.now()
    const timeUntilExpiry = expiresAt - now

    // Refresh if token expires in less than 5 minutes
    return timeUntilExpiry < REFRESH_BEFORE_EXPIRY_MS && timeUntilExpiry > 0
  }

  /**
   * Check if token is already expired
   * Returns false for opaque tokens (defers validation to backend)
   */
  function isTokenExpired(token: string | null): boolean {
    if (!token) return true

    const expiresAt = getTokenExpiration(token)
    // If token can't be decoded (opaque token), defer to backend validation
    if (!expiresAt) return false

    return Date.now() >= expiresAt
  }

  /**
   * Attempt to refresh the access token
   */
  async function refreshToken(): Promise<void> {
    if (isRefreshing.value) {
      console.debug('Token refresh already in progress, skipping')
      return
    }

    const currentToken = authStore.token
    const currentRefreshToken = authStore.refreshToken

    if (!currentToken || !currentRefreshToken) {
      console.debug('No tokens available, skipping refresh')
      return
    }

    // Check if access token needs refresh
    if (!shouldRefreshToken(currentToken) && !isTokenExpired(currentToken)) {
      console.debug('Token still valid, skipping refresh')
      return
    }

    // Check if refresh token is expired
    if (isTokenExpired(currentRefreshToken)) {
      console.warn('Refresh token expired, logging out')
      await authStore.logout()
      return
    }

    isRefreshing.value = true

    try {
      console.debug('Refreshing access token proactively')
      await authStore.refreshAccessToken()
      console.debug('Access token refreshed successfully')
    } catch (error) {
      console.error('Failed to refresh token:', error)
      // If refresh fails, log out the user
      await authStore.logout()
    } finally {
      isRefreshing.value = false
    }
  }

  /**
   * Start periodic token refresh checks
   */
  function startTokenRefreshTimer(): void {
    if (refreshTimer.value) {
      console.debug('Token refresh timer already running')
      return
    }

    console.debug('Starting token refresh timer')

    // Check immediately on start
    refreshToken()

    // Then check every minute
    refreshTimer.value = setInterval(() => {
      refreshToken()
    }, CHECK_INTERVAL_MS)
  }

  /**
   * Stop periodic token refresh checks
   */
  function stopTokenRefreshTimer(): void {
    if (refreshTimer.value) {
      console.debug('Stopping token refresh timer')
      clearInterval(refreshTimer.value)
      refreshTimer.value = null
    }
  }

  /**
   * Handle visibility change (tab active/inactive)
   */
  function handleVisibilityChange(): void {
    if (document.hidden) {
      console.debug('Tab hidden, pausing token refresh')
      stopTokenRefreshTimer()
    } else {
      console.debug('Tab visible, resuming token refresh')
      // When tab becomes visible, check immediately and restart timer
      refreshToken()
      startTokenRefreshTimer()
    }
  }

  /**
   * Initialize token refresh mechanism
   */
  function initialize(): void {
    // Always register visibility listener regardless of auth state
    document.addEventListener('visibilitychange', handleVisibilityChange)

    if (!authStore.isAuthenticated) {
      console.debug('User not authenticated, skipping token refresh setup')
      return
    }

    startTokenRefreshTimer()
  }

  /**
   * Cleanup token refresh mechanism
   */
  function cleanup(): void {
    stopTokenRefreshTimer()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }

  // Lifecycle hooks for Vue components
  onMounted(() => {
    initialize()

    // Watch auth state and start/stop refresh based on authentication
    watch(
      () => authStore.isAuthenticated,
      (isAuthenticated) => {
        if (isAuthenticated) {
          console.debug('User authenticated, starting token refresh')
          startTokenRefreshTimer()
        } else {
          console.debug('User logged out, stopping token refresh')
          stopTokenRefreshTimer()
        }
      }
    )
  })

  onUnmounted(() => {
    cleanup()
  })

  return {
    refreshToken,
    shouldRefreshToken,
    isTokenExpired,
    isRefreshing,
    initialize,
    cleanup
  }
}
