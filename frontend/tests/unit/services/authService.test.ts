import { describe, it, expect, beforeEach, vi } from 'vitest'
import { authService } from '@/services/authService'
import apiClient from '@/plugins/axios'
import { AuthError } from '@/types/auth'

vi.mock('@/plugins/axios')

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('login', () => {
    it('should successfully login with valid credentials', async () => {
      const mockResponse = {
        data: {
          access_token: 'test-access-token',
          refresh_token: 'test-refresh-token'
        }
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse)

      const result = await authService.login({
        username: 'test@test.com',
        password: 'password123'
      })

      expect(result.data).toEqual(mockResponse.data)
      expect(apiClient.post).toHaveBeenCalledWith(
        '/auth/login',
        expect.any(URLSearchParams)
      )

      // Verify URLSearchParams content
      const callArgs = vi.mocked(apiClient.post).mock.calls[0]
      const formData = callArgs[1] as URLSearchParams
      expect(formData.get('username')).toBe('test@test.com')
      expect(formData.get('password')).toBe('password123')
    })

    it('should throw AuthError on login failure', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'))

      await expect(
        authService.login({
          username: 'test@test.com',
          password: 'wrong'
        })
      ).rejects.toThrow(AuthError)

      await expect(
        authService.login({
          username: 'test@test.com',
          password: 'wrong'
        })
      ).rejects.toThrow('Login failed')
    })

    it('should convert login form to URLSearchParams correctly', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} })

      await authService.login({
        username: 'user@example.com',
        password: 'secure-password'
      })

      const callArgs = vi.mocked(apiClient.post).mock.calls[0]
      const formData = callArgs[1] as URLSearchParams

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
          is_superuser: false
        }
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse)

      const result = await authService.register({
        username: 'newuser',
        email: 'new@test.com',
        password: 'password123'
      })

      expect(result.data).toEqual(mockResponse.data)
      expect(apiClient.post).toHaveBeenCalledWith('/users/open', {
        username: 'newuser',
        email: 'new@test.com',
        password: 'password123'
      })
    })

    it('should throw AuthError on registration failure', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Email already exists'))

      await expect(
        authService.register({
          username: 'newuser',
          email: 'existing@test.com',
          password: 'password123'
        })
      ).rejects.toThrow(AuthError)

      await expect(
        authService.register({
          username: 'newuser',
          email: 'existing@test.com',
          password: 'password123'
        })
      ).rejects.toThrow('Registration failed')
    })

    it('should send registration data in correct format', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} })

      await authService.register({
        username: 'testuser',
        email: 'test@example.com',
        password: 'secret'
      })

      expect(apiClient.post).toHaveBeenCalledWith('/users/open', {
        username: 'testuser',
        email: 'test@example.com',
        password: 'secret'
      })
    })
  })

  describe('refreshToken', () => {
    it('should successfully refresh token', async () => {
      const mockResponse = {
        data: {
          access_token: 'new-access-token',
          refresh_token: 'new-refresh-token'
        }
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse)

      const result = await authService.refreshToken('old-refresh-token')

      expect(result.data).toEqual(mockResponse.data)
      expect(apiClient.post).toHaveBeenCalledWith('/auth/refresh', {
        refresh_token: 'old-refresh-token'
      })
    })

    it('should throw AuthError on refresh failure', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Invalid token'))

      await expect(authService.refreshToken('invalid-token')).rejects.toThrow(AuthError)
      await expect(authService.refreshToken('invalid-token')).rejects.toThrow(
        'Token refresh failed'
      )
    })
  })

  describe('logout', () => {
    it('should successfully logout', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: undefined })

      await authService.logout('test-access-token')

      expect(apiClient.post).toHaveBeenCalledWith(
        '/auth/logout',
        {},
        {
          headers: { Authorization: 'Bearer test-access-token' }
        }
      )
    })

    it('should throw AuthError on logout failure', async () => {
      vi.mocked(apiClient.post).mockRejectedValue(new Error('Network error'))

      await expect(authService.logout('test-token')).rejects.toThrow(AuthError)
      await expect(authService.logout('test-token')).rejects.toThrow('Logout failed')
    })

    it('should include authorization header', async () => {
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: undefined })

      await authService.logout('my-token')

      const callArgs = vi.mocked(apiClient.post).mock.calls[0]
      expect(callArgs[2]?.headers).toEqual({ Authorization: 'Bearer my-token' })
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
          is_superuser: false
        }
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      const result = await authService.getCurrentUser('test-access-token')

      expect(result.data).toEqual(mockResponse.data)
      expect(apiClient.get).toHaveBeenCalledWith('/users/me', {
        headers: { Authorization: 'Bearer test-access-token' }
      })
    })

    it('should throw AuthError on fetch failure', async () => {
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Unauthorized'))

      await expect(authService.getCurrentUser('invalid-token')).rejects.toThrow(AuthError)
      await expect(authService.getCurrentUser('invalid-token')).rejects.toThrow(
        'Failed to fetch current user'
      )
    })

    it('should include authorization header', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: {} })

      await authService.getCurrentUser('my-access-token')

      const callArgs = vi.mocked(apiClient.get).mock.calls[0]
      expect(callArgs[1]?.headers).toEqual({ Authorization: 'Bearer my-access-token' })
    })
  })

  describe('Error Handling', () => {
    it('should wrap all errors in AuthError', async () => {
      const methods = [
        () => authService.login({ username: 'test', password: 'test' }),
        () => authService.register({ username: 'test', email: 'test', password: 'test' }),
        () => authService.refreshToken('token'),
        () => authService.logout('token'),
        () => authService.getCurrentUser('token')
      ]

      vi.mocked(apiClient.post).mockRejectedValue(new Error('Generic error'))
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Generic error'))

      for (const method of methods) {
        await expect(method()).rejects.toBeInstanceOf(AuthError)
      }
    })
  })
})
