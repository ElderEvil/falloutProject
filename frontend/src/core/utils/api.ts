import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import apiClient from '@/core/plugins/axios'

/**
 * Central HTTP boundary (Batch 1 of the axios -> fetch migration).
 *
 * Axios-backed shim: every call delegates to the shared `@/core/plugins/axios`
 * instance, so the existing auth-refresh interceptor and its notifications keep
 * working byte-for-byte. This layer only unwraps `response.data` and normalizes
 * failures to {@link ApiError}. Toasts stay caller-owned: the client throws and
 * callers keep feeding the error through `handleStoreError`/`getErrorMessage`.
 *
 * Bearer auth is injected by the interceptor; no call site passes a token.
 * `authHeaders()` exists for transports that bypass axios (SSE), which is a
 * later slice. See docs/frontend/HTTP_CLIENT_MIGRATION.md.
 */

export type ApiMethod = 'get' | 'post' | 'put' | 'patch' | 'delete'

export interface ApiRequestOptions {
  params?: Record<string, unknown>
  signal?: AbortSignal
  headers?: Record<string, string>
  skipErrorNotification?: boolean
}

export interface ApiErrorInit {
  status?: number | null
  detail?: unknown
  fields?: Record<string, string> | null
  headers?: Record<string, unknown>
  cause?: unknown
  message?: string
}

/**
 * Normalized failure shape thrown by the boundary. `detail` carries the raw
 * backend payload (string, FastAPI validation array, or object); `fields`
 * flattens a FastAPI validation array to `path -> message`.
 */
export class ApiError extends Error {
  readonly status: number | null
  readonly detail: unknown
  readonly fields: Record<string, string> | null
  readonly headers: Record<string, unknown>

  constructor(init: ApiErrorInit = {}) {
    super(init.message ?? 'Request failed')
    this.name = 'ApiError'
    this.status = init.status ?? null
    this.detail = init.detail ?? null
    this.fields = init.fields ?? null
    this.headers = init.headers ?? {}
    if (init.cause !== undefined) this.cause = init.cause
  }
}

interface FastApiValidationItem {
  loc?: unknown[]
  msg?: unknown
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.length > 0) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === 'object') {
          const entry = item as FastApiValidationItem
          const field = Array.isArray(entry.loc) ? entry.loc.join('.') : 'field'
          return typeof entry.msg === 'string' ? `${field}: ${entry.msg}` : null
        }
        return typeof item === 'string' ? item : null
      })
      .filter((part): part is string => part !== null)
    return parts.length > 0 ? parts.join(', ') : null
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return null
}

function extractFields(detail: unknown): Record<string, string> | null {
  if (!Array.isArray(detail)) return null
  const fields: Record<string, string> = {}
  for (const item of detail) {
    if (!item || typeof item !== 'object') continue
    const entry = item as FastApiValidationItem
    if (typeof entry.msg !== 'string') continue
    const field = Array.isArray(entry.loc) ? entry.loc.join('.') : 'field'
    fields[field] = entry.msg
  }
  return Object.keys(fields).length > 0 ? fields : null
}

function extractDetail(data: unknown): unknown {
  if (data && typeof data === 'object') {
    if ('detail' in data) return (data as { detail: unknown }).detail
    if ('message' in data) return (data as { message: unknown }).message
  }
  return data ?? null
}

function errorResponse(error: unknown): {
  status: number | null
  data: unknown
  headers: Record<string, unknown>
} | null {
  if (typeof error !== 'object' || error === null) return null
  const response = (error as { response?: unknown }).response
  if (typeof response !== 'object' || response === null) return null
  const payload = response as { status?: unknown; data?: unknown; headers?: unknown }
  return {
    status: typeof payload.status === 'number' ? payload.status : null,
    data: payload.data,
    headers:
      payload.headers && typeof payload.headers === 'object'
        ? (payload.headers as Record<string, unknown>)
        : {},
  }
}

/** Normalize any thrown value (axios error, ApiError, Error, …) to ApiError. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  const response = errorResponse(error)
  if (response) {
    const detail = extractDetail(response.data)
    const message =
      detailToMessage(detail) ?? (error instanceof Error ? error.message : 'Request failed')
    return new ApiError({
      status: response.status,
      detail,
      fields: extractFields(detail),
      headers: response.headers,
      cause: error,
      message,
    })
  }

  if (error instanceof Error) return new ApiError({ message: error.message, cause: error })
  return new ApiError({
    message: typeof error === 'string' ? error : 'Request failed',
    cause: error,
  })
}

/**
 * Escape hatch returning the full `AxiosResponse` for call sites that need
 * status/headers or non-data semantics (e.g. auth returning token payloads).
 */
export async function apiRequest<T = unknown>(
  method: ApiMethod,
  url: string,
  body?: unknown,
  options: ApiRequestOptions = {}
): Promise<AxiosResponse<T>> {
  const config: AxiosRequestConfig = {}
  if (options.params) config.params = options.params
  if (options.signal) config.signal = options.signal
  if (options.headers) config.headers = options.headers
  if (options.skipErrorNotification) config._skipErrorNotification = true
  const hasConfig = Object.keys(config).length > 0

  try {
    if (method === 'get')
      return hasConfig ? await apiClient.get<T>(url, config) : await apiClient.get<T>(url)
    if (method === 'delete')
      return hasConfig ? await apiClient.delete<T>(url, config) : await apiClient.delete<T>(url)
    if (method === 'post')
      return hasConfig ? await apiClient.post<T>(url, body, config) : await apiClient.post<T>(url, body)
    if (method === 'put')
      return hasConfig ? await apiClient.put<T>(url, body, config) : await apiClient.put<T>(url, body)
    return hasConfig
      ? await apiClient.patch<T>(url, body, config)
      : await apiClient.patch<T>(url, body)
  } catch (error) {
    throw toApiError(error)
  }
}

export async function apiGet<T = unknown>(
  url: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const response = await apiRequest<T>('get', url, undefined, options)
  return response.data
}

export async function apiPost<T = unknown>(
  url: string,
  body?: unknown,
  options: ApiRequestOptions = {}
): Promise<T> {
  const response = await apiRequest<T>('post', url, body, options)
  return response.data
}

export async function apiPut<T = unknown>(
  url: string,
  body?: unknown,
  options: ApiRequestOptions = {}
): Promise<T> {
  const response = await apiRequest<T>('put', url, body, options)
  return response.data
}

export async function apiPatch<T = unknown>(
  url: string,
  body?: unknown,
  options: ApiRequestOptions = {}
): Promise<T> {
  const response = await apiRequest<T>('patch', url, body, options)
  return response.data
}

export async function apiDelete<T = unknown>(
  url: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const response = await apiRequest<T>('delete', url, undefined, options)
  return response.data
}

function readStoredToken(): string | null {
  try {
    const stored = localStorage.getItem('token')
    if (!stored) return null
    return stored.replace(/^"|"$/g, '')
  } catch {
    return null
  }
}

/**
 * Authorization header for transports outside the axios interceptor (SSE).
 * Axios call sites must not use this: the interceptor owns the bearer token.
 */
export function authHeaders(): Record<string, string> {
  const token = readStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Sugar object over the named functions (single implementation). */
export const api = {
  get: apiGet,
  post: apiPost,
  put: apiPut,
  patch: apiPatch,
  delete: apiDelete,
  request: apiRequest,
}
