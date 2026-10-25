import axios from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type InboxNotification = components['schemas']['NotificationRead']
export type ReadFilter = 'all' | 'unread' | 'read'

export const notificationService = {
  async list(vaultId: string | null, status: ReadFilter, offset = 0, limit = 50) {
    const { data } = await axios.get<InboxNotification[]>('/api/v1/notifications/', {
      params: {
        vault_id: vaultId ?? undefined,
        is_read: status === 'all' ? undefined : status === 'read',
        offset,
        limit,
      },
    })
    return data
  },
  async unreadCount() {
    const { data } = await axios.get<{ count: number }>('/api/v1/notifications/unread-count')
    return data.count
  },
  async markRead(id: string) {
    await axios.patch(`/api/v1/notifications/${id}/read`, {})
  },
  async markAllRead(vaultId: string | null) {
    await axios.post(
      '/api/v1/notifications/mark-all-read',
      {},
      {
        params: { vault_id: vaultId ?? undefined },
      }
    )
  },
}
