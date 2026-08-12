import { getErrorMessage } from '@/core/types/utils'
import { useToast } from '@/core/composables/useToast'

export { getErrorMessage }

/**
 * Handle store errors with consistent user-facing feedback and message extraction.
 */
export function handleStoreError(error: unknown, context: string, showToast = true): string {
  const message = getErrorMessage(error)
  if (showToast) useToast().error(`${context}: ${message}`)
  return message
}
