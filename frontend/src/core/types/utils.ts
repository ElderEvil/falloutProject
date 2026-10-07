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

interface FastApiValidationItem {
  loc?: unknown[]
  msg?: unknown
}

/** Render a backend validation payload (string, FastAPI array, or object) as text. */
export function formatValidationDetail(detail: unknown): string | null {
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
    if (parts.length > 0) return parts.join(', ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return null
}

/** Flatten a FastAPI validation array to path -> message. */
export function extractValidationFields(detail: unknown): Record<string, string> | null {
  if (!Array.isArray(detail)) return null
  const fields: Record<string, string> = {}
  for (const item of detail) {
    if (!item || typeof item !== 'object') continue
    const entry = item as FastApiValidationItem
    if (typeof entry.msg !== 'string') continue
    fields[Array.isArray(entry.loc) ? entry.loc.join('.') : 'field'] = entry.msg
  }
  return Object.keys(fields).length > 0 ? fields : null
}

function apiErrorDetailMessage(error: ApiErrorLike): string | null {
  return (
    formatValidationDetail(error.detail) ??
    (error.fields
      ? Object.entries(error.fields)
          .map(([field, message]) => `${field}: ${message}`)
          .join(', ') || null
      : null)
  )
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
