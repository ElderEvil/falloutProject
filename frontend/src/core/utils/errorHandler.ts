import { getErrorMessage } from '@/core/types/utils'
import { useToast } from '@/core/composables/useToast'
import { claimErrorNotification } from '@/core/utils/errorNotifications'

export { getErrorMessage }

export function notifyErrorOnce(error: unknown, message: string, duration?: number): void {
  if (!claimErrorNotification(error)) return
  if (duration === undefined) useToast().error(message)
  else useToast().error(message, duration)
}

/**
 * Handle store errors with consistent user-facing feedback and message extraction.
 */
export function handleStoreError(error: unknown, context: string, showToast = true): string {
  const message = getErrorMessage(error)
  if (showToast) notifyErrorOnce(error, `${context}: ${message}`)
  return message
}
