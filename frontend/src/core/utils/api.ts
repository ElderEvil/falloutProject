import type { AxiosRequestConfig, AxiosResponse } from 'axios'
import apiClient from '@/core/plugins/axios'
import { extractValidationFields, formatValidationDetail } from '@/core/types/utils'

/**
 * Central HTTP boundary (Batch 1 of the axios call-site consolidation).
 * Every call delegates to the shared `@/core/plugins/axios` instance, so the
 * working byte-for-byte. This layer only unwraps `response.data` and normalizes
 * failures to {@link ApiError}. Toasts stay caller-owned: the client throws and
 * callers keep feeding the error through `handleStoreError`/`getErrorMessage`.
 *
 * Bearer auth is injected by the interceptor; no call site passes a token.
 * See docs/frontend/HTTP_CLIENT_MIGRATION.md.
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
  declare cause: unknown

  constructor(init: ApiErrorInit = {}) {
    super(init.message ?? 'Request failed')
    this.name = 'ApiError'
    this.status = init.status ?? null
    this.detail = init.detail ?? null
    this.fields = init.fields ?? null
    this.headers = init.headers ?? {}
    this.cause = init.cause
  }
}

function extractDetail(data: unknown): unknown {
  if (data && typeof data === 'object') {
    const payload = data as { detail?: unknown; message?: unknown }
    return payload.detail ?? payload.message ?? data
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
function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  const response = errorResponse(error)
  if (response) {
    const detail = extractDetail(response.data)
    const message =
      formatValidationDetail(detail) ?? (error instanceof Error ? error.message : 'Request failed')
    return new ApiError({
      status: response.status,
      detail,
      fields: extractValidationFields(detail),
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
      return hasConfig
        ? await apiClient.post<T>(url, body, config)
        : await apiClient.post<T>(url, body)
    if (method === 'put')
      return hasConfig
        ? await apiClient.put<T>(url, body, config)
        : await apiClient.put<T>(url, body)
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

/** Sugar object over the named helpers; patch/delete inline their single use. */
export const api = {
  get: apiGet,
  post: apiPost,
  put: apiPut,
  patch: async <T = unknown>(url: string, body?: unknown, options: ApiRequestOptions = {}) =>
    (await apiRequest<T>('patch', url, body, options)).data,
  delete: async <T = unknown>(url: string, options: ApiRequestOptions = {}) =>
    (await apiRequest<T>('delete', url, undefined, options)).data,
  request: apiRequest,
}
