import { getErrorMessage } from '@/core/types/utils'

export { getErrorMessage }

/**
 * Handle store errors with consistent logging and message extraction
 */
export function handleStoreError(error: unknown, context: string): string {
  const message = getErrorMessage(error)
  console.error(`${context}:`, error)
  return message
}
