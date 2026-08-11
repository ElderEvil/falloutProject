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
): error is { response: { data: { detail?: string; message?: string }; status: number } } {
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
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  return 'An unknown error occurred'
}
