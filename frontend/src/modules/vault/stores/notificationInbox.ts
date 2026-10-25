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
 * An accepted read updates cached flags, refreshes the server count, and bumps
 * ``readRevision`` so every mounted surface reloads. Each request captures the signed-in
 * session first and discards its result if the session changed while it was in
 * flight, so a slow response cannot mark another account's notifications read.
 */
export const useNotificationInboxStore = defineStore('notificationInbox', () => {
  const auth = useAuthStore()
  const pageNotifications = ref<InboxNotification[]>([])
  type ReadState = Pick<InboxNotification, 'id' | 'vault_id' | 'is_read'>
  const readStates = ref(new Map<string, ReadState>())
  const rememberNotifications = (items: ReadState[]) => {
    for (const { id, vault_id, is_read } of items) {
      readStates.value.set(id, {
        id,
        vault_id,
        is_read: is_read || !!readStates.value.get(id)?.is_read,
      })
    }
  }
  const isRead = (item: ReadState) => readStates.value.get(item.id)?.is_read ?? item.is_read
  const notifications = computed(() =>
    pageNotifications.value.map((item) => ({ ...item, is_read: isRead(item) }))
  )
  const hasMore = ref(false)
  const unreadCount = ref(0)
  const readRevision = ref(0)
  let hasLoaded = false
  let hasRequestedCount = false
  const sessionGeneration = ref(0)
  let countGeneration = 0
  let generation = 0
  let vaultId: string | null = null
  let status: ReadFilter = 'all'
  let offset = 0

  // A logout/login must invalidate requests even if the same identity returns.
  // Before identity resolves, credentials distinguish otherwise anonymous sessions.
  watch(
    () => (auth.isAuthenticated ? (auth.user?.id ?? auth.token) : null),
    () => sessionGeneration.value++,
    { flush: 'sync' }
  )
  const currentSession = (): number => sessionGeneration.value
  const ownsSession = (captured: number): boolean => currentSession() === captured

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
        pageNotifications.value = []
        offset = 0
        hasMore.value = false
      }
      const page = await notificationService.list(selectedVault, selectedStatus, offset, PAGE_SIZE)
      if (requestGeneration !== generation || !ownsSession(capturedSession)) return
      offset += page.length
      const ids = new Set(pageNotifications.value.map((item) => item.id))
      rememberNotifications(page)
      pageNotifications.value.push(...page.filter((item) => !ids.has(item.id)))
      hasMore.value = page.length === PAGE_SIZE
    },
    { context: 'Failed to load notifications' }
  )

  const { run: refreshUnreadCount } = useAsyncAction(
    async () => {
      const capturedSession = currentSession()
      hasRequestedCount = true
      const requestGeneration = ++countGeneration
      const count = await notificationService.unreadCount()
      if (!ownsSession(capturedSession) || requestGeneration !== countGeneration) return
      unreadCount.value = count
    },
    { context: 'Failed to load the unread count' }
  )

  const { run: markRead, isLoading: isSavingOne } = useAsyncAction(
    async (id: string) => {
      const capturedSession = currentSession()
      await notificationService.markRead(id)
      if (!ownsSession(capturedSession)) return false
      const notification = readStates.value.get(id)
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
      for (const notification of readStates.value.values()) {
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

  watch(sessionGeneration, () => {
    generation++
    pageNotifications.value = []
    readStates.value.clear()
    hasMore.value = false
    unreadCount.value = 0
    offset = 0
    if (auth.isAuthenticated) {
      if (hasLoaded) void load(vaultId, status)
      if (hasRequestedCount) void refreshUnreadCount()
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
    rememberNotifications,
    isRead,
  }
})
