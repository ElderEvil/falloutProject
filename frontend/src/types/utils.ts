import type { Component } from 'vue'

/**
 * Generic API response wrapper
 */
export interface ApiResponse<T> {
  data: T
  message?: string
  status: number
}

/**
 * Structured API error type
 */
export interface ApiError {
  message: string
  status?: number
  detail?: string
  errors?: Record<string, string[]>
}

/**
 * Type for icon components (Iconify, custom components, etc.)
 */
export type IconComponent = Component | string

/**
 * Paginated API response
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/**
 * Async operation result wrapper
 */
export type AsyncResult<T, E = ApiError> =
  | { success: true; data: T }
  | { success: false; error: E }

/**
 * Type guard to check if an error is an ApiError
 */
export function isApiError(error: unknown): error is ApiError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as ApiError).message === 'string'
  )
}

/**
 * Type guard to check if an error has a response property (Axios error)
 */
export function isAxiosError(error: unknown): error is { response: { data: { detail?: string; message?: string }; status: number } } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as any).response === 'object' &&
    (error as any).response !== null
  )
}

/**
 * Extract error message from unknown error type
 */
export function getErrorMessage(error: unknown): string {
  if (isAxiosError(error)) {
    return error.response.data.detail || error.response.data.message || 'An error occurred'
  }
  if (isApiError(error)) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  return 'An unknown error occurred'
}

/**
 * Convert unknown error to ApiError
 */
export function toApiError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error
  }
  if (isAxiosError(error)) {
    return {
      message: error.response.data.detail || error.response.data.message || 'An error occurred',
      status: error.response.status,
      detail: error.response.data.detail
    }
  }
  if (error instanceof Error) {
    return {
      message: error.message
    }
  }
  return {
    message: typeof error === 'string' ? error : 'An unknown error occurred'
  }
}
