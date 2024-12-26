import apiClient from '../plugins/axios'
import type { AxiosResponse } from 'axios'
import { type LoginForm, type RegisterForm, type Token } from '@/types/auth'
import type { User } from '@/types/user'

export const authService = {
  async login(form: LoginForm): Promise<AxiosResponse<Token>> {
    try {
      const formAsRecord: Record<string, string> = {
        username: form.username,
        password: form.password
      }
      return await apiClient.post('/login/access-token', new URLSearchParams(formAsRecord))
    } catch (error) {
      throw new AuthError('Login failed')
    }
  },
  async register(form: RegisterForm): Promise<AxiosResponse<User>> {
    try {
      return await apiClient.post('/users/open', form)
    } catch (error) {
      throw new AuthError('Registration failed')
    }
  },
  async refreshToken(refreshToken: string): Promise<AxiosResponse<Token>> {
    try {
      return await apiClient.post('/login/refresh-token', { refresh_token: refreshToken })
    } catch (error) {
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
    } catch (error) {
      throw new AuthError('Logout failed')
    }
  },
  async getCurrentUser(accessToken: string): Promise<AxiosResponse<User>> {
    try {
      return await apiClient.get('/users/me', {
        headers: { Authorization: `Bearer ${accessToken}` }
      })
    } catch (error) {
      throw new AuthError('Failed to fetch current user')
    }
  }
}
