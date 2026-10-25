import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useAuthStore } from '@/modules/auth/stores/auth'
import {
  notificationService,
  type InboxNotification,
  type ReadFilter,
} from '@/modules/vault/services/notificationService'

const PAGE_SIZE = 50

/**
 * Single owner of notification read state for the bell, the inbox view, and the badge.
 *
 * A read action applies optimistically, refreshes the server count, and bumps
 * ``readRevision`` so every mounted surface reloads. Each request captures the signed-in
 * account id first and discards its result if the session changed while it was in
 * flight, so a slow response cannot mark another account's notifications read.
 */
export const useNotificationInboxStore = defineStore('notificationInbox', () => {
  const auth = useAuthStore()
  const notifications = ref<InboxNotification[]>([])
  const hasMore = ref(false)
  const unreadCount = ref(0)
  const readRevision = ref(0)
  let hasLoaded = false
  let generation = 0
  let vaultId: string | null = null
  let status: ReadFilter = 'all'
  let offset = 0

  // Logout clears the token while the user object may linger, so identity alone is not
  // enough. A token *rotation* keeps both parts, and its in-flight requests must land.
  const currentSession = (): string =>
    `${auth.user?.id ?? ''}:${auth.isAuthenticated ? 'signed-in' : 'signed-out'}`
  const ownsSession = (captured: string): boolean => currentSession() === captured

  const {
    run: load,
    isLoading,
    error,
  } = useAsyncAction(
    async (selectedVault: string | null, selectedStatus: ReadFilter, append = false) => {
      hasLoaded = true
      const requestGeneration = ++generation
      const capturedSession = currentSession()
      if (!append) {
        vaultId = selectedVault
        status = selectedStatus
        notifications.value = []
        offset = 0
        hasMore.value = false
      }
      const page = await notificationService.list(selectedVault, selectedStatus, offset, PAGE_SIZE)
      if (requestGeneration !== generation || !ownsSession(capturedSession)) return
      offset += page.length
      const ids = new Set(notifications.value.map((item) => item.id))
      notifications.value.push(...page.filter((item) => !ids.has(item.id)))
      hasMore.value = page.length === PAGE_SIZE
    },
    { context: 'Failed to load notifications' }
  )

  const { run: refreshUnreadCount } = useAsyncAction(
    async () => {
      const capturedSession = currentSession()
      const count = await notificationService.unreadCount()
      if (!ownsSession(capturedSession)) return
      unreadCount.value = count
    },
    { context: 'Failed to load the unread count' }
  )

  const { run: markRead, isLoading: isSavingOne } = useAsyncAction(
    async (id: string) => {
      const capturedSession = currentSession()
      await notificationService.markRead(id)
      if (!ownsSession(capturedSession)) return false
      const notification = notifications.value.find((item) => item.id === id)
      if (notification && !notification.is_read) {
        notification.is_read = true
        unreadCount.value = Math.max(0, unreadCount.value - 1)
      }
      readRevision.value++
      await Promise.all([refreshUnreadCount(), load(vaultId, status)])
      return true
    },
    { context: 'Failed to mark notifications as read' }
  )

  const { run: markAllRead, isLoading: isSavingAll } = useAsyncAction(
    async (scopeVaultId: string | null) => {
      const capturedSession = currentSession()
      await notificationService.markAllRead(scopeVaultId)
      if (!ownsSession(capturedSession)) return false
      for (const notification of notifications.value) {
        if (scopeVaultId === null || notification.vault_id === scopeVaultId) {
          notification.is_read = true
        }
      }
      readRevision.value++
      await Promise.all([refreshUnreadCount(), load(vaultId, status)])
      return true
    },
    { context: 'Failed to mark notifications as read' }
  )

  const isSaving = computed(() => isSavingOne.value || isSavingAll.value)

  const noteUnreadArrival = () => {
    unreadCount.value++
  }

  watch([() => auth.isAuthenticated, () => auth.user?.id], ([isAuthenticated]) => {
    generation++
    notifications.value = []
    hasMore.value = false
    unreadCount.value = 0
    offset = 0
    if (isAuthenticated && hasLoaded) {
      void load(vaultId, status)
      void refreshUnreadCount()
    }
  })

  return {
    notifications,
    hasMore,
    unreadCount,
    isLoading,
    error,
    isSaving,
    readRevision,
    load,
    markRead,
    markAllRead,
    refreshUnreadCount,
    noteUnreadArrival,
  }
})
