/**
 * Centralized error handling utilities for stores and components
 */

/**
 * Extract error message from unknown error type
 * @param error - The caught error
 * @returns User-friendly error message
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  return 'An unknown error occurred'
}

/**
 * Handle store errors with consistent logging and message extraction
 * @param error - The caught error
 * @param context - Context description for logging (e.g., "Failed to fetch dwellers")
 * @returns User-friendly error message
 */
export function handleStoreError(error: unknown, context: string): string {
  const message = getErrorMessage(error)
  console.error(`${context}:`, error)
  return message
}
