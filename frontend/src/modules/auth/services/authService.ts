import { apiRequest } from '@/core/utils/api'
import type { AxiosResponse } from 'axios'
import { AuthError, type Token, type UserWithTokens } from '../types/auth'
import type { User } from '../types/user'
import type { LoginFormData, RegisterFormData } from '../schemas/auth'

export const authService = {
  async login(form: LoginFormData): Promise<AxiosResponse<Token>> {
    try {
      const formAsRecord: Record<string, string> = {
        username: form.username,
        password: form.password,
      }
      return await apiRequest<Token>('post', '/api/v1/auth/login', new URLSearchParams(formAsRecord), {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      })
    } catch {
      throw new AuthError('Login failed')
    }
  },
  async register(form: RegisterFormData): Promise<AxiosResponse<UserWithTokens>> {
    try {
      return await apiRequest<UserWithTokens>('post', '/api/v1/users/open', form)
    } catch {
      throw new AuthError('Registration failed')
    }
  },
  async refreshToken(refreshToken: string): Promise<AxiosResponse<Token>> {
    try {
      return await apiRequest<Token>('post', '/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      })
    } catch {
      throw new AuthError('Token refresh failed')
    }
  },
  async logout(): Promise<AxiosResponse<void>> {
    try {
      return await apiRequest<void>('post', '/api/v1/auth/logout', {})
    } catch {
      throw new AuthError('Logout failed')
    }
  },
  async getCurrentUser(): Promise<AxiosResponse<User>> {
    try {
      return await apiRequest<User>('get', '/api/v1/users/me')
    } catch {
      throw new AuthError('Failed to fetch current user')
    }
  },
}
