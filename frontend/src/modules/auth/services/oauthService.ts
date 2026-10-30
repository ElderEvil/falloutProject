import { apiRequest } from '@/core/utils/api'
import type { AxiosResponse } from 'axios'
import type { Token } from '../types/auth'

export type OAuthProvider = 'google' | 'github'

export interface OAuthProviders {
  google: boolean
  github: boolean
}

export interface OAuthLinkedAccounts {
  providers: OAuthProvider[]
  has_password: boolean
}

export interface OAuthLinkAuthorize {
  authorize_url: string
}

function apiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
}

export const oauthService = {
  async getProviders(): Promise<OAuthProviders> {
    const response = await apiRequest<OAuthProviders>(
      'get',
      '/api/v1/auth/oauth/providers',
      undefined,
      {
        skipErrorNotification: true,
      }
    )
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
  async getLinkedAccounts(): Promise<OAuthLinkedAccounts> {
    const response = await apiRequest<OAuthLinkedAccounts>(
      'get',
      '/api/v1/auth/oauth/accounts',
      undefined,
      { skipErrorNotification: true }
    )
    return response.data
  },
  async linkProvider(provider: OAuthProvider): Promise<OAuthLinkAuthorize> {
    const response = await apiRequest<OAuthLinkAuthorize>(
      'post',
      `/api/v1/auth/oauth/${provider}/link`,
      {},
      { skipErrorNotification: true }
    )
    return response.data
  },
  async unlinkProvider(provider: OAuthProvider): Promise<void> {
    await apiRequest<void>('delete', `/api/v1/auth/oauth/${provider}`, undefined, {
      skipErrorNotification: true,
    })
  },
}
