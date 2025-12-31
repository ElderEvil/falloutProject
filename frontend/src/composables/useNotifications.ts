import { computed } from 'vue'
import { useNotificationStore } from '@/stores/notification'

/**
 * Composable for managing notifications
 *
 * Provides easy access to the notification store with
 * helper methods for showing different types of notifications
 *
 * @example
 * ```ts
 * const { notify, notifySuccess, notifyError } = useNotifications()
 *
 * // Show success notification
 * notifySuccess('Saved!', 'Your changes have been saved')
 *
 * // Show error with details
 * notifyError('Failed to save', 'An error occurred', 'Error: 404')
 * ```
 */
export function useNotifications() {
  const notificationStore = useNotificationStore()

  return {
    // State
    notifications: computed(() => notificationStore.notifications),

    // Actions
    notify: notificationStore.add,
    notifySuccess: notificationStore.success,
    notifyError: notificationStore.error,
    notifyWarning: notificationStore.warning,
    notifyInfo: notificationStore.info,
    removeNotification: notificationStore.remove,
    clearAll: notificationStore.clear
  }
}
