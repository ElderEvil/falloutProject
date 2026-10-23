import { describe, it, expect, beforeEach, vi, afterEach } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import axios from '@/core/plugins/axios'
import { useProfileStore } from '@/modules/profile/stores/profile'

vi.mock('@/core/plugins/axios')

const { handleStoreErrorMock } = vi.hoisted(() => ({ handleStoreErrorMock: vi.fn() }))

vi.mock('@/core/utils/errorHandler', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/core/utils/errorHandler')>()
  return { ...actual, handleStoreError: handleStoreErrorMock }
})

describe('Auth Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.resetAllMocks()
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
        data: {
          id: '1',
          username: 'testuser',
          email: 'test@test.com',
        },
      }

      localStorage.setItem('token', mockToken)
      localStorage.setItem('refreshToken', mockRefreshToken)
      localStorage.setItem('selectedVaultId', 'previous-account-vault')
      // User is NOT in localStorage (simulating the bug)

      vi.mocked(axios.get).mockResolvedValueOnce(mockUserResponse)

      const store = useAuthStore()

      // Wait for async fetchUser to complete
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me')
      expect(store.user).toEqual(mockUserResponse.data)
      expect(localStorage.getItem('selectedVaultId')).toBeNull()
    })

    it('should not fetch user if both token and user exist in localStorage', () => {
      const mockToken = 'test-token'
      const mockRefreshToken = 'test-refresh-token'
      const mockUser = { id: '1', username: 'test', email: 'test@test.com' }

      localStorage.setItem('token', mockToken)
      localStorage.setItem('refreshToken', mockRefreshToken)
      localStorage.setItem('user', JSON.stringify(mockUser))

      const store = useAuthStore()

      expect(axios.get).not.toHaveBeenCalled()
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
        data: {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token',
        },
      }
      const mockUserResponse = {
        data: {
          id: '1',
          username: 'testuser',
          email: 'test@test.com',
        },
      }

      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse)
      vi.mocked(axios.get).mockResolvedValueOnce(mockUserResponse)

      const result = await store.login('test@test.com', 'password')

      expect(result).toBe(true)
      expect(store.token).toBe('new-access-token')
      expect(store.refreshToken).toBe('new-refresh-token')
      expect(store.user).toEqual(mockUserResponse.data)
      expect(localStorage.getItem('token')).toBe('new-access-token')
      expect(localStorage.getItem('refreshToken')).toBe('new-refresh-token')
    })

    it('should return false on login failure', async () => {
      const store = useAuthStore()
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Login failed'))

      const result = await store.login('wrong@test.com', 'wrongpassword')

      expect(result).toBe(false)
      expect(store.token).toBeNull()
    })

    it('should return false when tokens are missing from response', async () => {
      const store = useAuthStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: {} })

      const result = await store.login('test@test.com', 'password')

      expect(result).toBe(false)
    })
  })

  it.each(['login', 'register', 'fetchUser', 'logout'] as const)(
    'clears the previous account profile during %s',
    async (action) => {
      const store = useAuthStore()
      store.token = 'old-token'
      store.user = { id: 'old-user' } as NonNullable<typeof store.user>
      const profiles = useProfileStore()
      profiles.profile = { user_id: 'old-user', avatar_url: '/old.png' } as NonNullable<
        typeof profiles.profile
      >
      vi.mocked(axios.post).mockResolvedValueOnce({
        data: { id: 'new-user', access_token: 'new-token', refresh_token: 'new-refresh' },
      })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: { id: 'new-user' } })

      if (action === 'login') await store.login('new-user', 'password')
      else if (action === 'register')
        await store.register('new-user', 'new@example.com', 'password')
      else await store[action]()

      expect(profiles.profile).toBeNull()
    }
  )

  describe('Register Action', () => {
    it('should register successfully with valid data', async () => {
      const store = useAuthStore()
      const mockResponse = {
        data: {
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
        },
      }

      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse)

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
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Registration failed'))

      const result = await store.register('newuser', 'new@test.com', 'password')

      expect(result).toBe(false)
      expect(store.token).toBeNull()
    })
  })

  describe('Account Update Action', () => {
    it('updates the email and stores the refreshed user', async () => {
      const store = useAuthStore()
      store.user = {
        id: '1',
        username: 'testuser',
        email: 'old@test.com',
      } as NonNullable<typeof store.user>
      vi.mocked(axios.put).mockResolvedValueOnce({
        data: { id: '1', username: 'testuser', email: 'new@test.com', email_verified: false },
      })

      const result = await store.updateAccount({ email: 'new@test.com' })

      expect(result).toBe(true)
      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/users/me',
        { email: 'new@test.com' },
        { _skipErrorNotification: true }
      )
      expect(store.user?.email).toBe('new@test.com')
      expect(store.user?.email_verified).toBe(false)
    })

    it('sends username and email in one request', async () => {
      const store = useAuthStore()
      store.user = {
        id: '1',
        username: 'oldname',
        email: 'old@test.com',
      } as NonNullable<typeof store.user>
      vi.mocked(axios.put).mockResolvedValueOnce({
        data: { id: '1', username: 'newname', email: 'new@test.com', email_verified: false },
      })

      const result = await store.updateAccount({ username: 'newname', email: 'new@test.com' })

      expect(result).toBe(true)
      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/users/me',
        { username: 'newname', email: 'new@test.com' },
        { _skipErrorNotification: true }
      )
    })

    it('refreshes the account when delivery fails after the change', async () => {
      const store = useAuthStore()
      store.token = 'session-token'
      store.user = {
        id: '1',
        username: 'testuser',
        email: 'old@test.com',
      } as NonNullable<typeof store.user>
      vi.mocked(axios.put).mockRejectedValueOnce({ response: { status: 502 } })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: { id: '1', username: 'testuser', email: 'new@test.com', email_verified: false },
      })

      const result = await store.updateAccount({ email: 'new@test.com' })

      expect(result).toBe(true)
      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me')
      expect(store.user?.email).toBe('new@test.com')
      expect(store.user?.email_verified).toBe(false)
      expect(handleStoreErrorMock).not.toHaveBeenCalled()
    })

    it('treats a 502 as failed when the refreshed account keeps the old email', async () => {
      const store = useAuthStore()
      store.token = 'session-token'
      store.user = {
        id: '1',
        username: 'testuser',
        email: 'old@test.com',
      } as NonNullable<typeof store.user>
      vi.mocked(axios.put).mockRejectedValueOnce({ response: { status: 502 } })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: { id: '1', username: 'testuser', email: 'old@test.com', email_verified: true },
      })

      const result = await store.updateAccount({ email: 'new@test.com' })

      expect(result).toBe(false)
      expect(store.user?.email).toBe('old@test.com')
      expect(handleStoreErrorMock).toHaveBeenCalledWith(expect.any(Error), expect.any(String))
    })

    it('returns false and reports failures through handleStoreError', async () => {
      const store = useAuthStore()
      vi.mocked(axios.put).mockRejectedValueOnce(new Error('Email already in use'))

      const result = await store.updateAccount({ email: 'taken@test.com' })

      expect(result).toBe(false)
      expect(handleStoreErrorMock).toHaveBeenCalledWith(expect.any(Error), expect.any(String))
    })
  })

  describe('Email Verification Actions', () => {
    it('verifies the email and refreshes the current user', async () => {
      const store = useAuthStore()
      store.token = 'session-token'
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { msg: 'Email verified' } })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: {
          id: '1',
          username: 'testuser',
          email: 'test@test.com',
          email_verified: true,
        },
      })

      const result = await store.verifyEmail('verify-token')

      expect(result).toBe(true)
      expect(axios.post).toHaveBeenCalledWith('/api/v1/auth/verify-email', {
        token: 'verify-token',
      })
      expect(axios.get).toHaveBeenCalledWith('/api/v1/users/me')
      expect(store.user?.email_verified).toBe(true)
    })

    it('does not fetch the user after verification without a session token', async () => {
      const store = useAuthStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { msg: 'Email verified' } })

      const result = await store.verifyEmail('verify-token')

      expect(result).toBe(true)
      expect(axios.get).not.toHaveBeenCalled()
    })

    it('returns false and reports failures when verification fails', async () => {
      const store = useAuthStore()
      const error = new Error('Invalid token')
      vi.mocked(axios.post).mockRejectedValueOnce(error)

      const result = await store.verifyEmail('bad-token')

      expect(result).toBe(false)
      expect(handleStoreErrorMock).toHaveBeenCalledWith(expect.any(Error), expect.any(String))
    })

    it('resends the verification email successfully', async () => {
      const store = useAuthStore()
      vi.mocked(axios.post).mockResolvedValueOnce({ data: { msg: 'Verification email sent' } })

      const result = await store.resendVerificationEmail()

      expect(result).toBe(true)
      expect(vi.mocked(axios.post).mock.calls[0]?.[0]).toBe('/api/v1/auth/resend-verification')
      expect(handleStoreErrorMock).not.toHaveBeenCalled()
    })

    it('returns false and routes resend failures through handleStoreError', async () => {
      const store = useAuthStore()
      const error = new Error('Already verified')
      vi.mocked(axios.post).mockRejectedValueOnce(error)

      const result = await store.resendVerificationEmail()

      expect(result).toBe(false)
      expect(handleStoreErrorMock).toHaveBeenCalledWith(expect.any(Error), expect.any(String))
    })
  })

  describe('Fetch User Action', () => {
    it('should fetch user data successfully', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      const mockUserResponse = {
        data: {
          id: '1',
          username: 'testuser',
          email: 'test@test.com',
        },
      }

      vi.mocked(axios.get).mockResolvedValueOnce(mockUserResponse)

      await store.fetchUser()

      expect(store.user).toEqual(mockUserResponse.data)
      expect(localStorage.getItem('user')).toBe(JSON.stringify(mockUserResponse.data))
    })

    it('should not fetch if token is missing', async () => {
      const store = useAuthStore()
      await store.fetchUser()

      expect(axios.get).not.toHaveBeenCalled()
    })

    it('should logout on fetch user failure', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Fetch failed'))
      vi.mocked(axios.post).mockResolvedValueOnce({})

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
        data: {
          access_token: 'new-access-token',
        },
      }

      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse)

      await store.refreshAccessToken()

      expect(store.token).toBe('new-access-token')
      expect(localStorage.getItem('token')).toBe('new-access-token')
    })

    it('should not refresh if refreshToken is missing', async () => {
      const store = useAuthStore()
      await store.refreshAccessToken()

      expect(axios.post).not.toHaveBeenCalled()
    })

    it('should logout on refresh failure', async () => {
      const store = useAuthStore()
      store.refreshToken = 'old-refresh-token'
      store.token = 'old-token'
      // First mock will be called by refreshAccessToken (refresh endpoint)
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Refresh failed'))
      // Second mock will be called by logout (logout endpoint)
      vi.mocked(axios.post).mockResolvedValueOnce({})

      await store.refreshAccessToken()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
    })
  })

  describe('Logout Action', () => {
    it('should logout successfully and clear all data', async () => {
      const store = useAuthStore()
      const vaultStore = useVaultStore()
      vaultStore.selectedVaultId = 'vault-1'
      store.token = 'test-token'
      store.refreshToken = 'test-refresh-token'
      store.user = { id: '1', username: 'test', email: 'test@test.com' }
      localStorage.setItem('token', 'test-token')
      localStorage.setItem('refreshToken', 'test-refresh-token')
      localStorage.setItem('user', JSON.stringify(store.user))

      vi.mocked(axios.post).mockResolvedValueOnce({})

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
      expect(localStorage.getItem('token')).toBeNull()
      expect(localStorage.getItem('refreshToken')).toBeNull()
      expect(localStorage.getItem('user')).toBeNull()
      expect(vaultStore.selectedVaultId).toBeNull()
      expect(localStorage.getItem('selectedVaultId')).toBeNull()
    })

    it('should clear data even if logout API call fails', async () => {
      const store = useAuthStore()
      store.token = 'test-token'
      vi.mocked(axios.post).mockRejectedValueOnce(new Error('Logout failed'))

      await store.logout()

      expect(store.token).toBeNull()
      expect(store.refreshToken).toBeNull()
      expect(store.user).toBeNull()
    })
  })
})
