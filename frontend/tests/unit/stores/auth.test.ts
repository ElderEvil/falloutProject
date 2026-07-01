import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import * as http from '@/core/plugins/httpClient'

vi.mock('@/core/plugins/httpClient')

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('State Initialization', () => {
    it('should initialize with null state when localStorage is empty', () => {
      const store = useAuthStore()
      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
    })

    it('should initialize from localStorage if data exists', () => {
      const mockToken = 'test-token'
      const mockRefreshToken = 'test-refresh-token'
      const mockUser = { id: '1', username: 'test', email: 'test@test.com' }

      localStorage.setItem('token', mockToken)
      localStorage.setItem('refreshToken', mockRefreshToken)
      localStorage.setItem('user', JSON.stringify(mockUser))

      const store = useAuthStore()
      expect(store.token).toBe(mockToken)
      expect(store.refreshToken).toBe(mockRefreshToken)
      expect(store.user).toEqual(mockUser)
    })

    it('should fetch user automatically if token exists but user data is missing', async () => {
      const mockToken = 'test-token'
      const mockRefreshToken = 'test-refresh-token'
      const mockUserResponse = {
        id: '1',
        username: 'testuser',
        email: 'test@test.com',
      }

      localStorage.setItem('token', mockToken)
      localStorage.setItem('refreshToken', mockRefreshToken)
      // User is NOT in localStorage (simulating the bug)

      vi.mocked(http.apiGet).mockResolvedValueOnce(mockUserResponse)

      const store = useAuthStore()

      // Wait for async fetchUser to complete
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(http.apiGet).toHaveBeenCalledWith('/api/v1/users/me')
      expect(store.user).toEqual(mockUserResponse)
    })

    it('should not fetch user if both token and user exist in localStorage', () => {
      const mockToken = 'test-token'
      const mockRefreshToken = 'test-refresh-token'
      const mockUser = { id: '1', username: 'test', email: 'test@test.com' }

      localStorage.setItem('token', mockToken)
      localStorage.setItem('refreshToken', mockRefreshToken)
      localStorage.setItem('user', JSON.stringify(mockUser))

      const store = useAuthStore()

      expect(http.apiGet).not.toHaveBeenCalled()
      expect(store.user).toEqual(mockUser)
    })
  })

  describe('Getters', () => {
    it('isAuthenticated should return true when token exists', () => {
      const store = useAuthStore()
      store.token = 'test-token'
      expect(store.isAuthenticated).toBe(true)
    })

    it('isAuthenticated should return false when token is null', () => {
      const store = useAuthStore()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('Login Action', () => {
    it('should login successfully with valid credentials', async () => {
      const store = useAuthStore()
      const mockResponse = {
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
      }
      const mockUserResponse = {
        id: '1',
        username: 'testuser',
        email: 'test@test.com',
      }

      vi.mocked(http.apiPost).mockResolvedValueOnce(mockResponse)
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockUserResponse)

      const result = await store.login('test@test.com', 'password')

      expect(result).toBe(true)
      expect(store.token).toBe('new-access-token')
      expect(store.refreshToken).toBe('new-refresh-token')
      expect(store.user).toEqual(mockUserResponse)
      expect(localStorage.getItem('token')).toBe('new-access-token')
      expect(localStorage.getItem('refreshToken')).toBe('new-refresh-token')
    })

    it('should return false on login failure', async () => {
      const store = useAuthStore()
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Login failed'))

      const result = await store.login('wrong@test.com', 'wrongpassword')

      expect(result).toBe(false)
      expect(store.token).toBeNull()
    })

    it('should return false when tokens are missing from response', async () => {
      const store = useAuthStore()
      vi.mocked(http.apiPost).mockResolvedValueOnce({} as any)

      const result = await store.login('test@test.com', 'password')

      expect(result).toBe(false)
    })
  })

  describe('Register Action', () => {
    it('should register successfully with valid data', async () => {
      const store = useAuthStore()
      const mockResponse = {
        id: '1',
        username: 'newuser',
        email: 'new@test.com',
        is_active: true,
        is_superuser: false,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        token_type: 'bearer',
      }

      vi.mocked(http.apiPost).mockResolvedValueOnce(mockResponse)

      const result = await store.register('newuser', 'new@test.com', 'password')

      expect(result).toBe(true)
      expect(store.token).toBe('new-access-token')
      expect(store.refreshToken).toBe('new-refresh-token')
      expect(store.user).toMatchObject({
        id: '1',
        username: 'newuser',
        email: 'new@test.com',
      })
    })

    it('should return false on registration failure', async () => {
      const store = useAuthStore()
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Registration failed'))

      const result = await store.register('newuser', 'new@test.com', 'password')

      expect(result).toBe(false)
      expect(store.token).toBeNull()
    })
  })

  describe('Fetch User Action', () => {
    it('should fetch user data successfully', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      const mockUserResponse = {
        id: '1',
        username: 'testuser',
        email: 'test@test.com',
      }

      vi.mocked(http.apiGet).mockResolvedValueOnce(mockUserResponse)

      await store.fetchUser()

      expect(store.user).toEqual(mockUserResponse)
      expect(localStorage.getItem('user')).toBe(JSON.stringify(mockUserResponse))
    })

    it('should not fetch if token is missing', async () => {
      const store = useAuthStore()
      await store.fetchUser()

      expect(http.apiGet).not.toHaveBeenCalled()
    })

    it('should logout on fetch user failure', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      vi.mocked(http.apiGet).mockRejectedValueOnce(new Error('Fetch failed'))
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await store.fetchUser()

      expect(store.token).toBeNull()
      expect(store.user).toBeNull()
    })
  })

  describe('Refresh Token Action', () => {
    it('should refresh access token successfully', async () => {
      const store = useAuthStore()
      store.refreshToken = 'old-refresh-token'
      const mockResponse = {
        access_token: 'new-access-token',
      }

      vi.mocked(http.apiPost).mockResolvedValueOnce(mockResponse)

      await store.refreshAccessToken()

      expect(store.token).toBe('new-access-token')
      expect(localStorage.getItem('token')).toBe('new-access-token')
    })

    it('should not refresh if refreshToken is missing', async () => {
      const store = useAuthStore()
      await store.refreshAccessToken()

      expect(http.apiPost).not.toHaveBeenCalled()
    })

    it('should logout on refresh failure', async () => {
      const store = useAuthStore()
      store.refreshToken = 'old-refresh-token'
      store.token = 'old-token'
      // First mock will be called by refreshAccessToken (refresh endpoint)
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Refresh failed'))
      // Second mock will be called by logout (logout endpoint)
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await store.refreshAccessToken()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
    })
  })

  describe('Logout Action', () => {
    it('should logout successfully and clear all data', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      store.refreshToken = 'test-refresh-token'
      store.user = { id: '1', username: 'test', email: 'test@test.com' }
      localStorage.setItem('token', 'test-token')
      localStorage.setItem('refreshToken', 'test-refresh-token')
      localStorage.setItem('user', JSON.stringify(store.user))

      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('refreshToken')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
    })

    it('should clear data even if logout API call fails', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Logout failed'))

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
    })
  })
})
