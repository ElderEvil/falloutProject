import type { components } from '@/core/types/api.generated'
import { apiGet, apiRequest } from '@/core/utils/api'

export type InboxNotification = components['schemas']['NotificationRead']
export type ReadFilter = 'all' | 'unread' | 'read'

export const notificationService = {
  async list(vaultId: string | null, status: ReadFilter, offset = 0, limit = 50) {
    return apiGet<InboxNotification[]>('/api/v1/notifications/', {
      params: {
        vault_id: vaultId ?? undefined,
        is_read: status === 'all' ? undefined : status === 'read',
        offset,
        limit,
      },
    })
  },
  async unreadCount() {
    const data = await apiGet<{ count: number }>('/api/v1/notifications/unread-count')
    return data.count
  },
  async markRead(id: string) {
    await apiRequest('patch', `/api/v1/notifications/${id}/read`, {})
  },
  async markAllRead(vaultId: string | null) {
    await apiRequest(
      'post',
      '/api/v1/notifications/mark-all-read',
      {},
      {
        params: { vault_id: vaultId ?? undefined },
      }
    )
  },
}
