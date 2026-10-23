import { apiRequest } from '@/core/utils/api'
import type { AxiosResponse } from 'axios'
import type { Token } from '../types/auth'

export type OAuthProvider = 'google' | 'github'

export interface OAuthProviders {
  google: boolean
  github: boolean
}

function apiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
}

export const oauthService = {
  async getProviders(): Promise<OAuthProviders> {
    const response = await apiRequest<OAuthProviders>('get', '/api/v1/auth/oauth/providers', undefined, {
      skipErrorNotification: true,
    })
    return response.data
  },
  authorizeUrl(provider: OAuthProvider): string {
    return `${apiBase()}/api/v1/auth/oauth/${provider}/authorize`
  },
  redeemHandoff(code: string): Promise<AxiosResponse<Token>> {
    return apiRequest<Token>(
      'post',
      '/api/v1/auth/oauth/handoff',
      { code },
      { withCredentials: true, skipErrorNotification: true }
    )
  },
}
