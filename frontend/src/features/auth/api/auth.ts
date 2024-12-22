import { auth } from '@/shared/api/client'
import type { LoginCredentials, LoginResponse } from '@/shared/api/types'

export const authApi = {
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    return auth.login(credentials)
  },

  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    return auth.refreshToken(refreshToken)
  }
}
