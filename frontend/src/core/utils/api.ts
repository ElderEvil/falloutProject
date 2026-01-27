import type { AxiosResponse } from 'axios'
import axios from '@/core/plugins/axios'
import type { ApiResponse, ApiError, AsyncResult } from '@/core/types/utils'
import { toApiError, isAxiosError } from '@/core/types/utils'

/**
 * Generic wrapper for API calls with automatic error handling
 *
 * @param fn - The async function to execute
 * @returns AsyncResult with either success data or error
 *
 * @example
 * ```ts
 * const result = await apiCall(async () => {
 *   const response = await axios.get<User>('/api/users/me')
 *   return response.data
 * })
 *
 * if (result.success) {
 *   // Use result.data
 * } else {
 *   // Handle result.error.message
 * }
 * ```
 */
export async function apiCall<T>(fn: () => Promise<T>): Promise<AsyncResult<T>> {
  try {
    const data = await fn()
    return { success: true, data }
  } catch (error: unknown) {
    return { success: false, error: toApiError(error) }
  }
}

/**
 * Makes a GET request with generic typing
 */
export async function apiGet<T>(url: string): Promise<T> {
  const response: AxiosResponse<T> = await axios.get(url)
  return response.data
}

/**
 * Makes a POST request with generic typing
 */
export async function apiPost<T, D = unknown>(url: string, data?: D): Promise<T> {
  const response: AxiosResponse<T> = await axios.post(url, data)
  return response.data
}

/**
 * Makes a PUT request with generic typing
 */
export async function apiPut<T, D = unknown>(url: string, data?: D): Promise<T> {
  const response: AxiosResponse<T> = await axios.put(url, data)
  return response.data
}

/**
 * Makes a PATCH request with generic typing
 */
export async function apiPatch<T, D = unknown>(url: string, data?: D): Promise<T> {
  const response: AxiosResponse<T> = await axios.patch(url, data)
  return response.data
}

/**
 * Makes a DELETE request with generic typing
 */
export async function apiDelete<T = void>(url: string): Promise<T> {
  const response: AxiosResponse<T> = await axios.delete(url)
  return response.data
}

/**
 * Handles API errors and extracts meaningful error messages
 *
 * @param error - The error to handle
 * @param fallback - Fallback message if error cannot be parsed
 * @returns Formatted error message
 */
export function handleApiError(error: unknown, fallback = 'An error occurred'): string {
  if (isAxiosError(error)) {
    return error.response.data.detail || error.response.data.message || fallback
  }
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  return fallback
}

/**
 * Type guard to check if a value is an ApiError
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
 * Create a typed API response wrapper
 */
export function createApiResponse<T>(data: T, message?: string, status = 200): ApiResponse<T> {
  return {
    data,
    message,
    status,
  }
}
