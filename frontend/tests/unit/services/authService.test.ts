import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { createApiClientMock } from '../helpers/mocks'
import rawAxios from 'axios'
import { authService } from '@/modules/auth/services/authService'
import { apiRequest } from '@/core/utils/api'
import { AuthError } from '@/modules/auth/types/auth'

vi.mock('@/core/utils/api', () => createApiClientMock())

describe('authService', () => {
  afterEach(() => vi.restoreAllMocks())
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('login', () => {
    it('should successfully login with valid credentials', async () => {
      const mockResponse = {
        data: {
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token',
        },
      }

      vi.mocked(apiRequest).mockResolvedValueOnce(mockResponse)

      const result = await authService.login({
        username: 'test@test.com',
        password: 'password123',
      })

      expect(result.data).toEqual(mockResponse.data)
      expect(apiRequest).toHaveBeenCalledWith(
        'post',
        '/api/v1/auth/login',
        expect.any(URLSearchParams),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      )

      const callArgs = vi.mocked(apiRequest).mock.calls[0]
      const formData = callArgs[2] as URLSearchParams
      expect(formData.get('username')).toBe('test@test.com')
      expect(formData.get('password')).toBe('password123')
    })

    it('should throw AuthError on login failure', async () => {
      vi.mocked(apiRequest).mockRejectedValue(new Error('Network error'))

      await expect(
        authService.login({
          username: 'test@test.com',
          password: 'wrong',
        })
      ).rejects.toThrow(AuthError)

      await expect(
        authService.login({
          username: 'test@test.com',
          password: 'wrong',
        })
      ).rejects.toThrow('Login failed')
    })

    it('should convert login form to URLSearchParams correctly', async () => {
      vi.mocked(apiRequest).mockResolvedValueOnce({ data: {} })

      await authService.login({
        username: 'user@example.com',
        password: 'secure-password',
      })

      const callArgs = vi.mocked(apiRequest).mock.calls[0]
      const formData = callArgs[2] as URLSearchParams

      expect(formData.get('username')).toBe('user@example.com')
      expect(formData.get('password')).toBe('secure-password')
    })
  })

  describe('register', () => {
    it('should successfully register with valid data', async () => {
      const mockResponse = {
        data: {
          id: '1',
          username: 'newuser',
          email: 'new@test.com',
          is_active: true,
          is_superuser: false,
        },
      }

      vi.mocked(apiRequest).mockResolvedValueOnce(mockResponse)

      const result = await authService.register({
        username: 'newuser',
        email: 'new@test.com',
        password: 'password123',
      })

      expect(result.data).toEqual(mockResponse.data)
      expect(apiRequest).toHaveBeenCalledWith('post', '/api/v1/users/open', {
        username: 'newuser',
        email: 'new@test.com',
        password: 'password123',
      })
    })

    it('should throw AuthError on registration failure', async () => {
      vi.mocked(apiRequest).mockRejectedValue(new Error('Email already exists'))

      await expect(
        authService.register({
          username: 'newuser',
          email: 'existing@test.com',
          password: 'password123',
        })
      ).rejects.toThrow(AuthError)

      await expect(
        authService.register({
          username: 'newuser',
          email: 'existing@test.com',
          password: 'password123',
        })
      ).rejects.toThrow('Registration failed')
    })

    it('should send registration data in correct format', async () => {
      vi.mocked(apiRequest).mockResolvedValueOnce({ data: {} })

      await authService.register({
        username: 'testuser',
        email: 'test@example.com',
        password: 'secret',
      })

      expect(apiRequest).toHaveBeenCalledWith('post', '/api/v1/users/open', {
        username: 'testuser',
        email: 'test@example.com',
        password: 'secret',
      })
    })
  })

  describe('refreshToken', () => {
    it('refreshes through the shared session boundary', async () => {
      localStorage.setItem('token', 'old-token')
      localStorage.setItem('refreshToken', 'old-refresh-token')
      const response = {
        data: { access_token: 'new-access-token', refresh_token: 'new-refresh-token' },
      }
      const post = vi.spyOn(rawAxios, 'post').mockResolvedValueOnce(response)
      const result = await authService.refreshToken()
      expect(result).toBe(response)
      expect(post).toHaveBeenCalledWith(expect.stringContaining('/api/v1/auth/refresh'), {
        refresh_token: 'old-refresh-token',
      })
    })

    it('preserves refresh failure status so temporary failures remain recoverable', async () => {
      localStorage.setItem('token', 'old-token')
      localStorage.setItem('refreshToken', 'old-refresh-token')
      const failure = Object.assign(new Error('Unavailable'), { response: { status: 503 } })
      vi.spyOn(rawAxios, 'post').mockRejectedValueOnce(failure)
      await expect(authService.refreshToken()).rejects.toBe(failure)
      expect(localStorage.getItem('refreshToken')).toBe('old-refresh-token')
    })
  })

  describe('logout', () => {
    it('should successfully logout', async () => {
      vi.mocked(apiRequest).mockResolvedValueOnce({ data: undefined })

      await authService.logout()

      expect(apiRequest).toHaveBeenCalledWith('post', '/api/v1/auth/logout', {})
    })

    it('should throw AuthError on logout failure', async () => {
      vi.mocked(apiRequest).mockRejectedValue(new Error('Network error'))

      await expect(authService.logout()).rejects.toThrow(AuthError)
      await expect(authService.logout()).rejects.toThrow('Logout failed')
    })

    it('should not include manual authorization header', async () => {
      vi.mocked(apiRequest).mockResolvedValueOnce({ data: undefined })

      await authService.logout()

      const callArgs = vi.mocked(apiRequest).mock.calls[0]
      // Authorization header is added by the axios interceptor, not manually
      expect(callArgs[2]).toEqual({})
    })
  })

  describe('getCurrentUser', () => {
    it('should successfully fetch current user', async () => {
      const mockResponse = {
        data: {
          id: '1',
          username: 'testuser',
          email: 'test@test.com',
          is_active: true,
          is_superuser: false,
        },
      }

      vi.mocked(apiRequest).mockResolvedValueOnce(mockResponse)

      const result = await authService.getCurrentUser()

      expect(result.data).toEqual(mockResponse.data)
      expect(apiRequest).toHaveBeenCalledWith('get', '/api/v1/users/me')
    })

    it('should throw AuthError on fetch failure', async () => {
      vi.mocked(apiRequest).mockRejectedValue(new Error('Unauthorized'))

      await expect(authService.getCurrentUser()).rejects.toThrow(AuthError)
      await expect(authService.getCurrentUser()).rejects.toThrow('Failed to fetch current user')
    })

    it('should not include manual authorization header', async () => {
      vi.mocked(apiRequest).mockResolvedValueOnce({ data: {} })

      await authService.getCurrentUser()

      const callArgs = vi.mocked(apiRequest).mock.calls[0]
      // Authorization header is added by the axios interceptor, not manually
      expect(callArgs[0]).toEqual('get')
      expect(callArgs[1]).toEqual('/api/v1/users/me')
      expect(callArgs[3]).toBeUndefined()
    })
  })

  describe('Error Handling', () => {
    it('should wrap all errors in AuthError', async () => {
      const methods = [
        () => authService.login({ username: 'test', password: 'test' }),
        () => authService.register({ username: 'test', email: 'test', password: 'test' }),
        () => authService.logout(),
        () => authService.getCurrentUser(),
      ]

      vi.mocked(apiRequest).mockRejectedValue(new Error('Generic error'))

      for (const method of methods) {
        await expect(method()).rejects.toBeInstanceOf(AuthError)
      }
    })
  })
})
