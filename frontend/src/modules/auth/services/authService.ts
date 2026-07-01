import * as http from '@/core/plugins/httpClient'
import { AuthError, type Token, type UserWithTokens } from '../types/auth'
import type { User } from '../types/user'
import type { LoginFormData, RegisterFormData } from '../schemas/auth'

export const authService = {
  async login(form: LoginFormData): Promise<Token> {
    try {
      const formAsRecord: Record<string, string> = {
        username: form.username,
        password: form.password,
      }
      return await http.apiPost<Token>(
        '/api/v1/auth/login',
        new URLSearchParams(formAsRecord).toString(),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      )
    } catch {
      throw new AuthError('Login failed')
    }
  },
  async register(form: RegisterFormData): Promise<UserWithTokens> {
    try {
      return await http.apiPost<UserWithTokens>('/api/v1/users/open', form)
    } catch {
      throw new AuthError('Registration failed')
    }
  },
  async refreshToken(refreshToken: string): Promise<Token> {
    try {
      return await http.apiPost<Token>('/api/v1/auth/refresh', {
        refresh_token: refreshToken,
      })
    } catch {
      throw new AuthError('Token refresh failed')
    }
  },
  async logout(): Promise<void> {
    try {
      return await http.apiPost<void>('/api/v1/auth/logout', {})
    } catch {
      throw new AuthError('Logout failed')
    }
  },
  async getCurrentUser(): Promise<User> {
    try {
      return await http.apiGet<User>('/api/v1/users/me')
    } catch {
      throw new AuthError('Failed to fetch current user')
    }
  },
}
