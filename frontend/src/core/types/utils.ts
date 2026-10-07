import type { Component } from 'vue'

/**
 * Type for icon components (Iconify, custom components, etc.)
 */
export type IconComponent = Component | string

/**
 * Type guard to check if an error has a response property (Axios error)
 */
export function isAxiosError(
  error: unknown
): error is { response: { data?: { detail?: string; message?: string }; status: number } } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as any).response === 'object' &&
    (error as any).response !== null
  )
}

interface ApiErrorLike {
  name?: string
  message?: string
  detail?: unknown
  fields?: Record<string, string> | null
}

function isApiError(error: unknown): error is ApiErrorLike {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as ApiErrorLike).name === 'ApiError' &&
    'detail' in error
  )
}

function apiErrorDetailMessage(error: ApiErrorLike): string | null {
  const detail = error.detail
  if (typeof detail === 'string' && detail.length > 0) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === 'object') {
          const entry = item as { loc?: unknown[]; msg?: unknown }
          const field = Array.isArray(entry.loc) ? entry.loc.join('.') : 'field'
          return typeof entry.msg === 'string' ? `${field}: ${entry.msg}` : null
        }
        return typeof item === 'string' ? item : null
      })
      .filter((part): part is string => part !== null)
    if (parts.length > 0) return parts.join(', ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  if (error.fields) {
    const parts = Object.entries(error.fields).map(([field, message]) => `${field}: ${message}`)
    if (parts.length > 0) return parts.join(', ')
  }
  return null
}

/**
 * Extract error message from unknown error type
 */
export function getErrorMessage(error: unknown, fallback = 'An unknown error occurred'): string {
  if (isApiError(error)) {
    return apiErrorDetailMessage(error) || error.message || fallback
  }
  if (isAxiosError(error)) {
    return error.response.data?.detail || error.response.data?.message || fallback
  }
  if (error instanceof Error) {
    return error.message || fallback
  }
  if (typeof error === 'string') {
    return error || fallback
  }
  return fallback
}
