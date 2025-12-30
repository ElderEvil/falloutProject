import apiClient from '../plugins/axios'
import type { AxiosResponse } from 'axios'
import { AuthError, type LoginForm, type RegisterForm, type Token } from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  async login(form: LoginForm): Promise<AxiosResponse<Token>> {
    try {
      const formAsRecord: Record<string, string> = {
        username: form.username,
        password: form.password
      }
      return await apiClient.post('/login/access-token', new URLSearchParams(formAsRecord))
    } catch {
      throw new AuthError('Login failed')
    }
  },
  async register(form: RegisterForm): Promise<AxiosResponse<User>> {
    try {
      return await apiClient.post('/users/open', form)
    } catch {
      throw new AuthError('Registration failed')
    }
  },
  async refreshToken(refreshToken: string): Promise<AxiosResponse<Token>> {
    try {
      return await apiClient.post('/login/refresh-token', { refresh_token: refreshToken })
    } catch {
      throw new AuthError('Token refresh failed')
    }
  },
  async logout(accessToken: string): Promise<AxiosResponse<void>> {
    try {
      return await apiClient.post(
        '/logout',
        {},
        {
          headers: { Authorization: `Bearer ${accessToken}` }
        }
      )
    } catch {
      throw new AuthError('Logout failed')
    }
  },
  async getCurrentUser(accessToken: string): Promise<AxiosResponse<User>> {
    try {
      return await apiClient.get('/users/me', {
        headers: { Authorization: `Bearer ${accessToken}` }
      })
    } catch {
      throw new AuthError('Failed to fetch current user')
    }
  },
  async verifyEmail(token: string): Promise<AxiosResponse<{ msg: string }>> {
    try {
      return await apiClient.post('/api/v1/auth/verify-email', { token })
    } catch {
      throw new AuthError('Email verification failed')
    }
  },
  async forgotPassword(email: string): Promise<AxiosResponse<{ msg: string }>> {
    try {
      return await apiClient.post('/api/v1/auth/forgot-password', { email })
    } catch {
      throw new AuthError('Failed to send password reset email')
    }
  },
  async resetPassword(token: string, new_password: string): Promise<AxiosResponse<{ msg: string }>> {
    try {
      return await apiClient.post('/api/v1/auth/reset-password', { token, new_password })
    } catch {
      throw new AuthError('Password reset failed')
    }
  },
  async resendVerification(accessToken: string): Promise<AxiosResponse<{ msg: string }>> {
    try {
      return await apiClient.post(
        '/api/v1/auth/resend-verification',
        {},
        {
          headers: { Authorization: `Bearer ${accessToken}` }
        }
      )
    } catch {
      throw new AuthError('Failed to resend verification email')
    }
  },
  async changePassword(
    accessToken: string,
    current_password: string,
    new_password: string
  ): Promise<AxiosResponse<{ msg: string }>> {
    try {
      return await apiClient.put(
        '/api/v1/auth/change-password',
        { current_password, new_password },
        {
          headers: { Authorization: `Bearer ${accessToken}` }
        }
      )
    } catch {
      throw new AuthError('Failed to change password')
    }
  }
}
