import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createAxiosMock } from '../../helpers/mocks'
import { createPinia, disposePinia, getActivePinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import axios from '@/core/plugins/axios'
import { useNotificationInboxStore } from '@/modules/vault/stores/notificationInbox'
import { useAuthStore } from '@/modules/auth/stores/auth'

vi.mock('@/core/plugins/axios', () => createAxiosMock())

const notification = (id: string, isRead = false) => ({
  id,
  vault_id: 'vault-a',
  is_read: isRead,
  title: id,
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.mocked(axios.get).mockResolvedValue({ data: [] })
})

afterEach(() => {
  const pinia = getActivePinia()
  if (pinia) disposePinia(pinia)
})

describe('notification inbox', () => {
  it('keeps vault and read status when loading older pages', async () => {
    const store = useNotificationInboxStore()
    vi.mocked(axios.get)
      .mockResolvedValueOnce({
        data: Array.from({ length: 50 }, (_, i) => notification(String(i))),
      })
      .mockResolvedValueOnce({ data: [notification('older')] })
    await store.load('vault-a', 'unread')
    expect(store.hasMore).toBe(true)
    await store.load('vault-a', 'unread', true)
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: 'vault-a', is_read: false, offset: 50, limit: 50 },
    })
    expect(store.notifications).toHaveLength(51)
    expect(store.notifications.at(-1)?.id).toBe('older')
    expect(store.hasMore).toBe(false)
  })

  it('ignores a late response after changing vaults and resets pagination', async () => {
    const store = useNotificationInboxStore()
    let finish!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        })
      )
      .mockResolvedValueOnce({ data: [notification('new-vault')] })
    const first = store.load('vault-a', 'all')
    await store.load('vault-b', 'read')
    finish({ data: [notification('stale')] })
    await first
    expect(store.notifications.map((item) => item.id)).toEqual(['new-vault'])
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: 'vault-b', is_read: true, offset: 0, limit: 50 },
    })
  })

  it('marks only the selected vault read and reloads the current filter', async () => {
    const store = useNotificationInboxStore()
    await store.load('vault-a', 'unread')
    await store.markAllRead('vault-a')
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/notifications/mark-all-read',
      {},
      {
        params: { vault_id: 'vault-a' },
      }
    )
    expect(store.notifications).toEqual([])
    expect(store.readRevision).toBe(1)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/notifications/', {
      params: { vault_id: 'vault-a', is_read: false, offset: 0, limit: 50 },
    })
  })

  it('marks every vault read when the bell passes a null scope', async () => {
    const store = useNotificationInboxStore()
    await store.load(null, 'all')
    await store.markAllRead(null)
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/notifications/mark-all-read',
      {},
      {
        params: { vault_id: undefined },
      }
    )
    expect(store.readRevision).toBe(1)
  })

  it('discards a read that resolves after the account changed', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    const store = useNotificationInboxStore()
    await store.load(null, 'read')
    let finish!: () => void
    vi.mocked(axios.patch).mockReturnValue(
      new Promise<never>((resolve) => {
        finish = () => resolve(undefined as never)
      })
    )

    const pending = store.markRead('notification-a')
    auth.user = { id: 'user-b' } as NonNullable<typeof auth.user>
    await flushPromises()
    finish()

    expect(await pending).toBe(false)
    expect(store.readRevision).toBe(0)
  })

  it('discards an unread count that resolves after the account changed', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    const store = useNotificationInboxStore()
    let finish!: (value: { data: { count: number } }) => void
    vi.mocked(axios.get).mockReturnValueOnce(
      new Promise<never>((resolve) => {
        finish = (value) => resolve(value as never)
      })
    )

    vi.mocked(axios.get).mockResolvedValue({ data: { count: 0 } })

    const pending = store.refreshUnreadCount()
    auth.user = { id: 'user-b' } as NonNullable<typeof auth.user>
    await flushPromises()
    finish({ data: { count: 9 } })
    await pending

    expect(store.unreadCount).toBe(0)
  })

  it('marks individual notifications read and signals the bell', async () => {
    const store = useNotificationInboxStore()
    await store.load(null, 'all')
    expect(await store.markRead('one')).toBe(true)
    expect(axios.patch).toHaveBeenCalledWith('/api/v1/notifications/one/read', {})
    expect(store.readRevision).toBe(1)
  })

  it('does not fetch an unopened inbox when authentication changes', async () => {
    const auth = useAuthStore()
    useNotificationInboxStore()
    auth.token = 'signed-in'
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    await flushPromises()
    expect(axios.get).not.toHaveBeenCalled()
  })

  it('preserves history, pagination and an in-flight page when the token rotates', async () => {
    const auth = useAuthStore()
    auth.token = 'original-token'
    auth.user = { id: 'same-account' } as NonNullable<typeof auth.user>
    const store = useNotificationInboxStore()
    let finish!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get)
      .mockResolvedValueOnce({
        data: Array.from({ length: 50 }, (_, i) => notification(String(i))),
      })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        })
      )
    await store.load('vault-a', 'unread')
    const pending = store.load('vault-a', 'unread', true)
    auth.token = 'refreshed-token'
    await flushPromises()
    expect(store.notifications).toHaveLength(50)
    expect(store.hasMore).toBe(true)
    finish({ data: [notification('older')] })
    await pending
    expect(store.notifications).toHaveLength(51)
    expect(store.notifications.at(-1)?.id).toBe('older')
    expect(axios.get).toHaveBeenCalledTimes(2)
  })

  it('reloads for a different account and discards the previous account’s pending response', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    const store = useNotificationInboxStore()
    let finish!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get)
      .mockResolvedValueOnce({ data: [notification('private-a')] })
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finish = resolve
        })
      )
      .mockResolvedValueOnce({ data: [notification('private-b')] })
    await store.load(null, 'read')
    const pending = store.load(null, 'read', true)
    auth.user = { id: 'user-b' } as NonNullable<typeof auth.user>
    await flushPromises()
    expect(store.notifications.map((item) => item.id)).toEqual(['private-b'])
    expect(axios.get).toHaveBeenCalledWith('/api/v1/notifications/', {
      params: { vault_id: undefined, is_read: true, offset: 0, limit: 50 },
    })
    finish({ data: [notification('late-private-a')] })
    await pending
    expect(store.notifications.map((item) => item.id)).toEqual(['private-b'])
  })

  it('reloads a previously opened inbox on login after logout', async () => {
    const auth = useAuthStore()
    auth.token = 'first-session'
    const store = useNotificationInboxStore()
    await store.load(null, 'all')
    auth.token = null
    await flushPromises()
    vi.mocked(axios.get).mockResolvedValueOnce({ data: [notification('new-session')] })
    auth.token = 'next-session'
    await flushPromises()
    expect(store.notifications.map((item) => item.id)).toEqual(['new-session'])
  })

  it('clears notification history and discards pending requests on logout', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    const store = useNotificationInboxStore()
    let finish!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get).mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const pending = store.load(null, 'all')
    auth.token = null
    await Promise.resolve()
    finish({ data: [notification('private')] })
    await pending
    expect(store.notifications).toEqual([])
    expect(store.hasMore).toBe(false)
  })

  it('keeps an SSE arrival when an older unread-count request completes', async () => {
    const store = useNotificationInboxStore()
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { count: 2 } })
    await store.refreshUnreadCount()

    let finish!: (value: { data: { count: number } }) => void
    vi.mocked(axios.get).mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      })
    )
    const pending = store.refreshUnreadCount()
    store.noteUnreadArrival()
    expect(store.unreadCount).toBe(3)
    finish({ data: { count: 2 } })
    await pending
    expect(store.unreadCount).toBe(3)

    vi.mocked(axios.get).mockResolvedValueOnce({ data: { count: 3 } })
    await store.refreshUnreadCount()
    expect(store.unreadCount).toBe(3)
  })

  it('preserves the badge when user identity resolves without opening the inbox', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    const store = useNotificationInboxStore()
    vi.mocked(axios.get).mockResolvedValue({ data: { count: 7 } })
    await store.refreshUnreadCount()
    expect(store.unreadCount).toBe(7)
    auth.user = { id: 'current-user' } as NonNullable<typeof auth.user>
    await flushPromises()
    expect(store.unreadCount).toBe(7)
  })

  it.each([false, true])(
    'drops an old count across logout/login (same tick: %s)',
    async (sameTick) => {
      const auth = useAuthStore()
      auth.token = 'account-a-token'
      const store = useNotificationInboxStore()
      let finish!: (value: { data: { count: number } }) => void
      vi.mocked(axios.get)
        .mockReturnValueOnce(
          new Promise((resolve) => {
            finish = resolve
          })
        )
        .mockResolvedValue({ data: { count: 0 } })
      const pending = store.refreshUnreadCount()
      auth.token = null
      if (!sameTick) await flushPromises()
      auth.token = 'account-b-token'
      await flushPromises()
      finish({ data: { count: 19 } })
      await pending
      expect(store.unreadCount).toBe(0)
    }
  )

  it('marks read on open optimistically without reloading, then rolls back on failure', async () => {
    const store = useNotificationInboxStore()
    const item = notification('one')
    store.rememberNotifications([item])
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { count: 1 } })
    await store.refreshUnreadCount()
    const listRequests = vi.mocked(axios.get).mock.calls.length

    let rejectPatch!: (reason: unknown) => void
    vi.mocked(axios.patch).mockReturnValueOnce(
      new Promise<never>((_, reject) => {
        rejectPatch = reject
      })
    )

    store.markReadOnOpen(item)

    expect(store.isRead(item)).toBe(true)
    expect(store.unreadCount).toBe(0)
    expect(store.readRevision).toBe(0)
    expect(vi.mocked(axios.get).mock.calls).toHaveLength(listRequests)
    expect(axios.patch).toHaveBeenCalledWith('/api/v1/notifications/one/read', {})

    rejectPatch(new Error('offline'))
    await flushPromises()

    expect(store.isRead(item)).toBe(false)
    expect(store.unreadCount).toBe(1)
    expect(store.readRevision).toBe(0)
    expect(vi.mocked(axios.get).mock.calls).toHaveLength(listRequests)
  })

  it('handles a notification with no cached read state on open', async () => {
    const store = useNotificationInboxStore()
    const item = notification('uncached')
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { count: 2 } })
    await store.refreshUnreadCount()

    let rejectPatch!: (reason: unknown) => void
    vi.mocked(axios.patch).mockReturnValueOnce(
      new Promise<never>((_, reject) => {
        rejectPatch = reject
      })
    )

    expect(() => store.markReadOnOpen(item)).not.toThrow()
    expect(store.isRead(item)).toBe(true)
    expect(store.unreadCount).toBe(1)

    rejectPatch(new Error('offline'))
    await flushPromises()

    expect(store.isRead(item)).toBe(false)
    expect(store.unreadCount).toBe(2)
  })

  it.each([null, 'vault-a'])('applies mark-all read state only within scope %s', async (scope) => {
    const store = useNotificationInboxStore()
    const first = notification('first')
    const second = { ...notification('second'), vault_id: 'vault-b' }
    store.rememberNotifications([first, second])
    await store.markAllRead(scope)
    expect(store.isRead(first)).toBe(true)
    expect(store.isRead(second)).toBe(scope === null)
    // A delayed pre-read list cannot revert an accepted read.
    store.rememberNotifications([first, second])
    expect(store.isRead(first)).toBe(true)
    const arrival = notification('new-arrival')
    store.rememberNotifications([arrival])
    expect(store.isRead(arrival)).toBe(false)
  })
})

describe('notification bell popup state', () => {
  it('loads and returns the twenty most recent notifications across all vaults', async () => {
    const store = useNotificationInboxStore()
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: [notification('newest'), notification('older')],
    })

    const page = await store.loadRecent()

    expect(axios.get).toHaveBeenCalledWith('/api/v1/notifications/', {
      params: { vault_id: undefined, is_read: undefined, offset: 0, limit: 20 },
    })
    expect(page.map((item) => item.id)).toEqual(['newest', 'older'])
    expect(store.recentNotifications.map((item) => item.id)).toEqual(['newest', 'older'])
    expect(store.hasLoadedRecent).toBe(true)
    expect(store.isRecentLoading).toBe(false)
  })

  it('merges a reload deduped by id without moving live arrivals off the page', async () => {
    const store = useNotificationInboxStore()
    store.receiveNotification(notification('live'))
    vi.mocked(axios.get).mockResolvedValueOnce({
      data: [notification('page-1'), notification('live', true)],
    })

    await store.loadRecent()

    expect(store.recentNotifications.map((item) => item.id)).toEqual(['page-1', 'live'])
  })

  it('prepends live arrivals only once and never caps the bell list', async () => {
    const store = useNotificationInboxStore()
    for (let index = 0; index < 25; index++) {
      store.receiveNotification(notification(`live-${index}`))
    }
    store.receiveNotification(notification('live-0'))

    expect(store.recentNotifications).toHaveLength(25)
    expect(store.recentNotifications[0]?.id).toBe('live-24')
    expect(store.recentNotifications.filter((item) => item.id === 'live-0')).toHaveLength(1)
  })

  it('applies the shared read overlay to bell rows', async () => {
    const store = useNotificationInboxStore()
    const item = notification('one')
    vi.mocked(axios.get).mockResolvedValueOnce({ data: [item] })
    await store.loadRecent()
    expect(store.recentNotifications[0]?.is_read).toBe(false)

    store.markReadOnOpen(item)

    expect(store.recentNotifications[0]?.is_read).toBe(true)
  })

  it('clears and reloads the bell list after an account switch', async () => {
    const auth = useAuthStore()
    auth.token = 'first-session'
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    const store = useNotificationInboxStore()
    vi.mocked(axios.get).mockResolvedValueOnce({ data: [notification('first')] })
    await store.loadRecent()

    vi.mocked(axios.get).mockResolvedValueOnce({ data: [notification('second')] })
    auth.user = { id: 'user-b' } as NonNullable<typeof auth.user>
    await flushPromises()

    expect(store.recentNotifications.map((item) => item.id)).toEqual(['second'])
  })

  it('clears the bell list on logout', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    const store = useNotificationInboxStore()
    vi.mocked(axios.get).mockResolvedValueOnce({ data: [notification('private')] })
    await store.loadRecent()

    auth.token = null
    await flushPromises()

    expect(store.recentNotifications).toEqual([])
  })

  it('keeps an in-flight bell load alive when the page reloads', async () => {
    const store = useNotificationInboxStore()
    let finishRecent!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finishRecent = resolve
        })
      )
      .mockResolvedValueOnce({ data: [notification('page')] })

    const recentPending = store.loadRecent()
    await store.load('vault-a', 'all')
    finishRecent({ data: [notification('recent')] })
    await recentPending

    expect(store.recentNotifications.map((item) => item.id)).toEqual(['recent'])
    expect(store.notifications.map((item) => item.id)).toEqual(['page'])
  })

  it('keeps an in-flight page load alive when the bell reloads', async () => {
    const store = useNotificationInboxStore()
    let finishPage!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get)
      .mockReturnValueOnce(
        new Promise((resolve) => {
          finishPage = resolve
        })
      )
      .mockResolvedValueOnce({ data: [notification('recent')] })

    const pagePending = store.load('vault-a', 'all')
    await store.loadRecent()
    finishPage({ data: [notification('page')] })
    await pagePending

    expect(store.notifications.map((item) => item.id)).toEqual(['page'])
    expect(store.recentNotifications.map((item) => item.id)).toEqual(['recent'])
  })

  it('discards a bell load that resolves after the account changed', async () => {
    const auth = useAuthStore()
    auth.token = 'signed-in'
    auth.user = { id: 'user-a' } as NonNullable<typeof auth.user>
    const store = useNotificationInboxStore()
    let finish!: (value: { data: ReturnType<typeof notification>[] }) => void
    vi.mocked(axios.get).mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      })
    )

    const pending = store.loadRecent()
    auth.user = { id: 'user-b' } as NonNullable<typeof auth.user>
    await flushPromises()
    finish({ data: [notification('private-a')] })

    expect(await pending).toEqual([])
    expect(store.recentNotifications).toEqual([])
  })
})
