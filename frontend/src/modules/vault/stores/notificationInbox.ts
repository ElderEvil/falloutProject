import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { handleStoreError, notifyErrorOnce } from '@/core/utils/errorHandler'
import { getErrorMessage } from '@/core/types/utils'
import { useAuthStore } from '@/modules/auth/stores/auth'
import {
  notificationService,
  type InboxNotification,
  type ReadFilter,
} from '@/modules/vault/services/notificationService'

const PAGE_SIZE = 50
const RECENT_PAGE_SIZE = 20

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
  // The bell popup is a separate, capped-at-load window that may grow past
  // RECENT_PAGE_SIZE as live notifications arrive; the page list stays paged.
  const recentRows = ref<InboxNotification[]>([])
  const recentNotifications = computed(() =>
    recentRows.value.map((item) => ({ ...item, is_read: isRead(item) }))
  )
  const hasLoadedRecent = ref(false)
  const hasMore = ref(false)
  const unreadCount = ref(0)
  const readRevision = ref(0)
  let hasLoaded = false
  let hasRequestedCount = false
  const sessionGeneration = ref(0)
  let countGeneration = 0
  let generation = 0
  let recentGeneration = 0
  let vaultId: string | null = null
  let status: ReadFilter = 'all'
  let offset = 0

  // A logout/login must invalidate requests even if the same identity returns.
  // Before identity resolves, credentials distinguish otherwise anonymous sessions.
  const sessionKey = computed(() => (auth.isAuthenticated ? (auth.user?.id ?? auth.token) : null))
  watch(
    () => sessionKey.value,
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

  // `useAsyncAction` counts every pending call, so a superseded account's slow request
  // would keep the bell on "Loading..." after the current account's rows arrived.
  // Loading follows the active request generation instead.
  const isRecentLoading = ref(false)

  /**
   * Load the bell popup page and return it so the caller can run reconnect
   * catch-up effects for events that arrived while the stream was paused.
   */
  const loadRecent = async (): Promise<InboxNotification[]> => {
    hasLoadedRecent.value = true
    const requestGeneration = ++recentGeneration
    const capturedSession = currentSession()
    isRecentLoading.value = true
    try {
      const page = await notificationService.list(null, 'all', 0, RECENT_PAGE_SIZE)
      if (requestGeneration !== recentGeneration || !ownsSession(capturedSession)) return []
      rememberNotifications(page)
      const loadedIds = new Set(page.map((item) => item.id))
      recentRows.value = [...recentRows.value.filter((item) => !loadedIds.has(item.id)), ...page]
      return page
    } catch (caught: unknown) {
      handleStoreError(caught, 'Failed to fetch notifications', false)
      notifyErrorOnce(caught, getErrorMessage(caught))
      return []
    } finally {
      if (requestGeneration === recentGeneration) isRecentLoading.value = false
    }
  }

  const receiveNotification = (notification: InboxNotification) => {
    rememberNotifications([notification])
    if (recentRows.value.some((item) => item.id === notification.id)) return
    recentRows.value = [notification, ...recentRows.value]
  }

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
        countGeneration++
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
      countGeneration++
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

  type OpenReadTarget = Pick<InboxNotification, 'id' | 'vault_id'> & { is_read?: boolean }

  /**
   * Optimistically mark a notification read when the player clicks through it.
   *
   * These click-through paths must navigate immediately. Awaiting `markRead`
   * would sequence PATCH -> unread-count GET -> list GET before `router.push`,
   * so the player would watch a spinner instead of the destination screen.
   * Updating the cached flag and badge is enough for the UI; the PATCH settles
   * behind the route change and deliberately skips `readRevision`, which is
   * the signal that triggers that reload chain. A failed PATCH rolls the
   * optimistic state back and reports the error.
   */
  const markReadOnOpen = (item: OpenReadTarget) => {
    const capturedSession = currentSession()
    const existing = readStates.value.get(item.id)
    if (existing?.is_read || item.is_read) return
    if (existing) existing.is_read = true
    else readStates.value.set(item.id, { id: item.id, vault_id: item.vault_id, is_read: true })
    const decremented = unreadCount.value > 0
    countGeneration++
    unreadCount.value = Math.max(0, unreadCount.value - 1)
    void notificationService.markRead(item.id).catch((caught: unknown) => {
      if (!ownsSession(capturedSession)) return
      if (existing) existing.is_read = false
      else readStates.value.delete(item.id)
      if (decremented) unreadCount.value++
      handleStoreError(caught, 'Failed to mark notifications as read')
    })
  }

  const isSaving = computed(() => isSavingOne.value || isSavingAll.value)

  const noteUnreadArrival = () => {
    countGeneration++
    unreadCount.value++
  }

  watch(sessionGeneration, () => {
    generation++
    recentGeneration++
    pageNotifications.value = []
    recentRows.value = []
    // The superseded request's finalizer is generation-guarded and cannot clear
    // this flag, so the session end owns the reset.
    isRecentLoading.value = false
    readStates.value.clear()
    hasMore.value = false
    unreadCount.value = 0
    offset = 0
    if (auth.isAuthenticated) {
      if (hasLoaded) void load(vaultId, status)
      if (hasLoadedRecent.value) void loadRecent()
      if (hasRequestedCount) void refreshUnreadCount()
    }
  })

  return {
    notifications,
    recentNotifications,
    sessionKey,
    hasLoadedRecent,
    isRecentLoading,
    loadRecent,
    receiveNotification,
    hasMore,
    unreadCount,
    isLoading,
    error,
    isSaving,
    readRevision,
    load,
    markRead,
    markReadOnOpen,
    markAllRead,
    refreshUnreadCount,
    noteUnreadArrival,
    rememberNotifications,
    isRead,
  }
})
