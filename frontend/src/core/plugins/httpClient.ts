import { API_BASE_URL } from '@/core/config/api'
import { useToast } from '@/core/composables/useToast'

interface ValidationError {
  loc: string[]
  msg: string
  type: string
}

export interface RequestConfig {
  headers?: Record<string, string>
  _retry?: boolean
  _skipErrorNotification?: boolean
}

export class ApiError extends Error {
  status: number
  detail: string | Record<string, unknown>

  constructor(status: number, detail: string | Record<string, unknown>) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
    this.name = 'ApiError'
  }
}

// Auth sync callback to avoid circular dependency with auth store
let authSyncCallback: ((refreshToken: string) => void) | null = null

export function registerAuthSyncCallback(cb: (refreshToken: string) => void): void {
  authSyncCallback = cb
}

// Helper functions to access localStorage directly (avoid circular dependency with auth store)
function getStoredToken(): string | null {
  try {
    const tokenData = localStorage.getItem('token')
    if (!tokenData) return null
    return tokenData.replace(/^"|"$/g, '')
  } catch {
    return null
  }
}

function getStoredRefreshToken(): string | null {
  try {
    const refreshTokenData = localStorage.getItem('refreshToken')
    if (!refreshTokenData) return null
    return refreshTokenData.replace(/^"|"$/g, '')
  } catch {
    return null
  }
}

function updateStoredToken(token: string): void {
  try {
    localStorage.setItem('token', JSON.stringify(token))
  } catch {
    console.error('Failed to update token in localStorage')
  }
}

function clearAuthData(): void {
  try {
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
    localStorage.removeItem('user')
  } catch {
    console.error('Failed to clear auth data')
  }
}

function buildUrl(url: string): string {
  if (url.startsWith('http')) return url
  return `${API_BASE_URL}${url}`
}

function getAuthHeaders(): Record<string, string> {
  const token = getStoredToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

async function doRefresh(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken()
  if (!refreshToken) return null

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })

  if (!response.ok) {
    throw new ApiError(response.status, 'Token refresh failed')
  }

  const data = (await response.json()) as {
    access_token?: string
    refresh_token?: string
  }

  if (data.access_token) {
    updateStoredToken(data.access_token)
  }

  if (data.refresh_token) {
    authSyncCallback?.(data.refresh_token)
  }

  return data.access_token ?? null
}

function extractErrorMessage(
  status: number,
  data: Record<string, unknown> | undefined
): { title: string; message: string } {
  let title = 'Request Failed'
  let message = 'An unexpected error occurred'

  if (status === 400) {
    title = 'Invalid Request'
  } else if (status === 401) {
    title = 'Unauthorized'
    message = 'Please log in to continue'
  } else if (status === 403) {
    title = 'Access Denied'
    message = "You don't have permission to perform this action"
  } else if (status === 404) {
    title = 'Not Found'
    message = 'The requested resource was not found'
  } else if (status === 422) {
    title = 'Validation Error'
  } else if (status === 429) {
    title = 'Rate Limit Exceeded'
    message = 'Too many requests. Please slow down and try again.'
  } else if (status >= 500) {
    title = 'Server Error'
    message = 'Something went wrong on our end'
  }

  if (!data) {
    return { title, message }
  }

  if (typeof data.detail === 'string') {
    message = data.detail
  } else if (Array.isArray(data.detail)) {
    message = (data.detail as ValidationError[])
      .map((err) => {
        const field = err.loc?.join('.') || 'field'
        return `${field}: ${err.msg}`
      })
      .join(', ')
  } else if (typeof data.detail === 'object' && data.detail !== null) {
    message = JSON.stringify(data.detail)
  } else if (typeof data.message === 'string') {
    message = data.message
  }

  return { title, message }
}

function handleRateLimitMessage(
  message: string,
  headers: Headers
): string {
  const retryAfter = headers.get('retry-after')
  if (retryAfter) {
    const seconds = parseInt(retryAfter, 10)
    if (!isNaN(seconds) && seconds > 0) {
      return `Too many requests. Please wait ${seconds} seconds before trying again.`
    }
  }
  return message
}

function showErrorToast(
  status: number,
  data: Record<string, unknown> | undefined,
  headers: Headers
): void {
  const { error: showError } = useToast()
  let { title, message } = extractErrorMessage(status, data)

  if (status === 429) {
    message = handleRateLimitMessage(message, headers)
  }

  showError(`${title}: ${message}`)
}

function logErrorDetails(
  method: string,
  url: string,
  status: number,
  error: unknown
): void {
  console.error(`API Error: ${method} ${url} - Status ${status}`, error)
}

async function request<T>(
  method: string,
  url: string,
  body?: unknown,
  config?: RequestConfig
): Promise<T> {
  const fullUrl = buildUrl(url)
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...config?.headers,
  }

  const init: RequestInit = {
    method,
    headers,
  }

  if (body !== undefined) {
    if (body instanceof FormData) {
      init.body = body
      delete headers['Content-Type']
    } else {
      init.body = typeof body === 'string' ? body : JSON.stringify(body)
    }
  }

  let response: Response

  try {
    response = await fetch(fullUrl, init)
  } catch {
    if (!config?._skipErrorNotification) {
      const { error: showError } = useToast()
      showError(
        'Network Error: Unable to reach the server. Please check your connection.'
      )
    }
    throw new ApiError(0, 'Network Error')
  }

  if (response.ok) {
    const contentType = response.headers.get('content-type')
    if (contentType?.includes('application/json')) {
      return (await response.json()) as T
    }
    return undefined as T
  }

  // Handle 401 with token refresh
  if (response.status === 401 && !config?._retry) {
    try {
      const newToken = await doRefresh()
      if (newToken) {
        return request<T>(method, url, body, { ...config, _retry: true })
      }
    } catch {
      clearAuthData()
      window.location.href = '/login'
      throw new ApiError(401, 'Unauthorized')
    }

    clearAuthData()
    window.location.href = '/login'
    throw new ApiError(401, 'Unauthorized')
  }

  // Parse error body for notifications
  let errorData: Record<string, unknown> | undefined
  try {
    errorData = (await response.json()) as Record<string, unknown>
  } catch {
    errorData = undefined
  }

  if (!config?._skipErrorNotification) {
    showErrorToast(response.status, errorData, response.headers)
    logErrorDetails(method, url, response.status, errorData)
  }

  throw new ApiError(response.status, errorData?.detail ?? 'Request failed')
}

export async function apiGet<T>(url: string, config?: RequestConfig): Promise<T> {
  return request<T>('GET', url, undefined, config)
}

export async function apiPost<T>(
  url: string,
  data?: unknown,
  config?: RequestConfig
): Promise<T> {
  return request<T>('POST', url, data, config)
}

export async function apiPut<T>(
  url: string,
  data?: unknown,
  config?: RequestConfig
): Promise<T> {
  return request<T>('PUT', url, data, config)
}

export async function apiPatch<T>(
  url: string,
  data?: unknown,
  config?: RequestConfig
): Promise<T> {
  return request<T>('PATCH', url, data, config)
}

export async function apiDelete<T>(url: string, config?: RequestConfig): Promise<T> {
  return request<T>('DELETE', url, undefined, config)
}
