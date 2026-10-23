import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useAuthStore } from '@/modules/auth/stores/auth'
import {
  notificationService,
  type InboxNotification,
  type ReadFilter,
} from '@/modules/vault/services/notificationService'

const PAGE_SIZE = 50

export const useNotificationInboxStore = defineStore('notificationInbox', () => {
  const notifications = ref<InboxNotification[]>([])
  const hasMore = ref(false)
  const readRevision = ref(0)
  let generation = 0
  let vaultId: string | null = null
  let status: ReadFilter = 'all'
  let offset = 0

  const {
    run: load,
    isLoading,
    error,
  } = useAsyncAction(
    async (selectedVault: string | null, selectedStatus: ReadFilter, append = false) => {
      const requestGeneration = ++generation
      if (!append) {
        vaultId = selectedVault
        status = selectedStatus
        notifications.value = []
        offset = 0
        hasMore.value = false
      }
      const page = await notificationService.list(selectedVault, selectedStatus, offset, PAGE_SIZE)
      if (requestGeneration !== generation) return
      offset += page.length
      const ids = new Set(notifications.value.map((item) => item.id))
      notifications.value.push(...page.filter((item) => !ids.has(item.id)))
      hasMore.value = page.length === PAGE_SIZE
    },
    { context: 'Failed to load notifications' }
  )

  const { run: markRead, isLoading: isSaving } = useAsyncAction(
    async (id?: string) => {
      if (id) await notificationService.markRead(id)
      else await notificationService.markAllRead(vaultId)
      readRevision.value++
      await load(vaultId, status)
      return true
    },
    { context: 'Failed to mark notifications as read' }
  )

  watch(
    () => useAuthStore().token,
    () => {
      generation++
      notifications.value = []
      hasMore.value = false
      offset = 0
    }
  )

  return { notifications, hasMore, isLoading, error, isSaving, readRevision, load, markRead }
})
