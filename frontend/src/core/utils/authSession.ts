import axios, { CanceledError, type AxiosResponse } from 'axios'
import type { components } from '@/core/types/api.generated'
import { jwtDecode } from 'jwt-decode'
import { getErrorStatus } from '@/core/types/utils'
import { claimErrorNotification } from './errorNotifications'
import { AUTH_SESSION_EXPIRED_EVENT, dispatchRefreshedAuthTokens } from './authSessionEvents'

function readStoredToken(key: string): string | null {
  const value = localStorage.getItem(key)?.replace(/^"|"$/g, '')
  return value && value !== 'null' ? value : null
}

export const getStoredToken = () => readStoredToken('token')

type Token = components['schemas']['Token']

let refreshInFlight: Promise<AxiosResponse<Token>> | null = null

export function expireSession(): void {
  const hadSession = !!(getStoredToken() || readStoredToken('refreshToken'))
  localStorage.removeItem('token')
  localStorage.removeItem('refreshToken')
  localStorage.removeItem('user')
  window.dispatchEvent(new Event(AUTH_SESSION_EXPIRED_EVENT))
  if (hadSession) window.location.href = '/login'
}

/** All HTTP, SSE and proactive refreshes share this one operation. */
export function refreshSession(): Promise<AxiosResponse<Token>> {
  if (refreshInFlight) return refreshInFlight
  const refreshToken = readStoredToken('refreshToken')
  if (!refreshToken) {
    expireSession()
    const error = Object.assign(new Error('Session expired'), { status: 401 })
    claimErrorNotification(error)
    return Promise.reject(error)
  }
  const previousToken = getStoredToken()
  refreshInFlight = axios
    .post<Token>(`${import.meta.env.VITE_API_BASE_URL}/api/v1/auth/refresh`, {
      refresh_token: refreshToken,
    })
    .then((response) => {
      const { data } = response
      // A second tab can rotate credentials before this response arrives.
      const storedRefresh = readStoredToken('refreshToken')
      const storedToken = getStoredToken()
      if (storedRefresh !== refreshToken || storedToken !== previousToken) {
        if (!storedRefresh || !storedToken)
          throw Object.assign(new Error('Session changed during refresh'), { status: 401 })
        const previousSubject = previousToken && decodeToken(previousToken)?.sub
        if (!previousSubject || decodeToken(storedToken)?.sub !== previousSubject)
          throw new CanceledError('Account changed during refresh')
        return {
          ...response,
          data: { ...data, access_token: storedToken, refresh_token: storedRefresh },
        }
      }
      if (!data.access_token) throw new Error('Refresh response has no access token')
      localStorage.setItem('token', JSON.stringify(data.access_token))
      if (data.refresh_token)
        localStorage.setItem('refreshToken', JSON.stringify(data.refresh_token))
      dispatchRefreshedAuthTokens({ token: data.access_token, refreshToken: data.refresh_token })
      return response
    })
    .catch((error: unknown) => {
      const status = getErrorStatus(error)
      if (status && [400, 401, 403, 404, 422].includes(status)) {
        claimErrorNotification(error)
        if (readStoredToken('refreshToken') === refreshToken) expireSession()
      }
      // Network/server failures leave the session intact for a later retry.
      throw error
    })
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

function decodeToken(token: string) {
  try {
    return jwtDecode<{ exp?: number; sub?: string }>(token)
  } catch {
    return undefined
  }
}

/** Opaque tokens are left for the server to validate. */
export async function ensureAccessToken(): Promise<string | null> {
  const token = getStoredToken()
  if (!token) return null
  const expiresAt = decodeToken(token)?.exp
  if (expiresAt === undefined || expiresAt * 1000 > Date.now() + 60_000) return token
  if (!readStoredToken('refreshToken') && expiresAt * 1000 > Date.now()) return token
  return (await refreshSession()).data.access_token
}
