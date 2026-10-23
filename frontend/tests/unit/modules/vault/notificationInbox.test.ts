import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createAxiosMock } from '../../helpers/mocks'
import { createPinia, setActivePinia } from 'pinia'
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
    await store.markRead()
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/notifications/mark-all-read',
      {},
      {
        params: { vault_id: 'vault-a' },
      }
    )
    expect(store.notifications).toEqual([])
    expect(store.readRevision).toBe(1)
    expect(axios.get).toHaveBeenLastCalledWith('/api/v1/notifications/', {
      params: { vault_id: 'vault-a', is_read: false, offset: 0, limit: 50 },
    })
  })

  it('marks individual notifications read and signals the bell', async () => {
    const store = useNotificationInboxStore()
    await store.load(null, 'all')
    expect(await store.markRead('one')).toBe(true)
    expect(axios.patch).toHaveBeenCalledWith('/api/v1/notifications/one/read', {})
    expect(store.readRevision).toBe(1)
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
})
