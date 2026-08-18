<script setup lang="ts">
import { ref, shallowRef, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSse, type SseEvent } from '@/core/composables/useEventStream'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import axios from '@/core/plugins/axios'

interface Notification {
  id: string
  vault_id?: string | null
  notification_type: string
  title: string
  message: string
  priority: string
  is_read: boolean
  created_at: string
  meta_data?: Record<string, any>
}

const authStore = useAuthStore()
const router = useRouter()
const showPopup = ref(false)
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
const { run: runFetchNotifications, isLoading } = useAsyncAction(
  async (token: string) => {
    const response = await axios.get('/api/v1/notifications/', {
      params: { limit: 20 },
      headers: { Authorization: `Bearer ${token}` },
    })
    notifications.value = response.data
  },
  { context: 'Failed to fetch notifications' }
)
const { run: runFetchUnreadCount } = useAsyncAction(
  async (token: string) => {
    const response = await axios.get('/api/v1/notifications/unread-count', {
      headers: { Authorization: `Bearer ${token}` },
    })
    unreadCount.value = response.data.count
  },
  { context: 'Failed to fetch unread count' }
)
const { run: runMarkAsRead } = useAsyncAction(
  async (notificationId: string, token: string) => {
    await axios.patch(
      `/api/v1/notifications/${notificationId}/read`,
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    )
    const notification = notifications.value.find((item) => item.id === notificationId)
    if (notification) notification.is_read = true
    await runFetchUnreadCount(token)
  },
  { context: 'Failed to mark notification as read' }
)
const { run: runMarkAllAsRead } = useAsyncAction(
  async (token: string) => {
    await axios.post(
      '/api/v1/notifications/mark-all-read',
      {},
      { headers: { Authorization: `Bearer ${token}` } }
    )
    notifications.value.forEach((notification) => (notification.is_read = true))
    unreadCount.value = 0
  },
  { context: 'Failed to mark all notifications as read' }
)

const hasUnread = computed(() => unreadCount.value > 0)

// SSE connection for live notifications
const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
// Keep the composable return value shallow so its nested event Ref is not unwrapped.
const sse = shallowRef<ReturnType<typeof useSse>>()

const startSse = () => {
  sse.value?.close()
  if (!authStore.token) {
    sse.value = undefined
    return
  }
  const instance = useSse(`${apiBase}/api/v1/stream/notifications`, {
    headers: () => ({ Authorization: `Bearer ${authStore.token}` }),
  })
  sse.value = instance
  instance.start()
}

// Restart SSE when the URL changes (login/logout)
watch(
  () => authStore.token,
  (token) => {
    if (token) startSse()
    else {
      sse.value?.close()
      sse.value = undefined
      notifications.value = []
      unreadCount.value = 0
    }
  }
)

const currentSseEvent = computed<SseEvent | null>(() => {
  const instance = sse.value
  return instance?.event.value ?? null
})

// Process incoming SSE notification events
watch(currentSseEvent, (evt) => {
    if (!evt || evt.event !== 'notification') return
    const notificationData = (evt.data as any)?.notification
    if (!notificationData) return

    const newNotif: Notification = {
      id: notificationData.id,
      vault_id: notificationData.vault_id ?? null,
      notification_type: notificationData.notification_type,
      title: notificationData.title,
      message: notificationData.message,
      priority: notificationData.priority,
      is_read: false,
      created_at: notificationData.created_at,
      meta_data: notificationData.meta_data,
    }
    notifications.value.unshift(newNotif)
    unreadCount.value++
})

const fetchNotifications = async () => {
  if (authStore.token) await runFetchNotifications(authStore.token)
}

const fetchUnreadCount = async () => {
  if (authStore.token) await runFetchUnreadCount(authStore.token)
}

const togglePopup = async () => {
  showPopup.value = !showPopup.value
  if (showPopup.value && notifications.value.length === 0) {
    await fetchNotifications()
  }
}

const markAsRead = async (notificationId: string) => {
  if (authStore.token) await runMarkAsRead(notificationId, authStore.token)
}

const markAllAsRead = async () => {
  if (authStore.token) await runMarkAllAsRead(authStore.token)
}

const getNotificationRoute = (notification: Notification): string | null => {
  if (!notification.vault_id) return null
  const vaultPath = `/vault/${notification.vault_id}`
  const dwellerId = notification.meta_data?.dweller_id as string | undefined

  switch (notification.notification_type) {
    case 'exploration_complete':
    case 'exploration_update':
      return `${vaultPath}/exploration`
    case 'training_complete':
    case 'training_started':
      return `${vaultPath}/training`
    case 'quest_complete':
      return `${vaultPath}/quests`
    case 'level_up':
      return dwellerId ? `${vaultPath}/dwellers/${dwellerId}` : `${vaultPath}/dwellers`
    case 'dweller_died':
    case 'dweller_injured':
    case 'baby_born':
    case 'relationship_formed':
    case 'pregnancy_detected':
    case 'radio_new_dweller':
      return `${vaultPath}/dwellers`
    case 'achievement_unlocked':
      return `${vaultPath}/objectives`
    default:
      return vaultPath
  }
}

const handleNotificationClick = async (notification: Notification) => {
  if (!notification.is_read) await markAsRead(notification.id)
  showPopup.value = false
  const route = getNotificationRoute(notification)
  if (route) await router.push(route)
}

const getNotificationIcon = (type: string): string => {
  const iconMap: Record<string, string> = {
    baby_born: 'mdi:baby-face',
    dweller_died: 'mdi:skull',
    exploration_complete: 'mdi:map-marker-check',
    exploration_update: 'mdi:map-marker',
    level_up: 'mdi:arrow-up-bold',
    training_complete: 'mdi:school',
    combat_victory: 'mdi:sword',
    radio_new_dweller: 'mdi:radio',
    resource_low: 'mdi:alert',
  }
  return iconMap[type] || 'mdi:information'
}

const getPriorityColor = (priority: string): string => {
  const colorMap: Record<string, string> = {
    urgent: 'text-red-500',
    high: 'text-[--color-theme-accent]',
    normal: 'text-[--color-theme-primary]',
    info: 'text-gray-400',
  }
  return colorMap[priority] || 'text-gray-400'
}

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp + 'Z')
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (days > 0) return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (minutes > 0) return `${minutes}m ago`
  return 'Just now'
}

onMounted(() => {
  fetchUnreadCount()
  if (authStore.token) {
    startSse()
  }
})

onBeforeUnmount(() => {
  sse.value?.close()
})
</script>

<template>
  <div class="relative">
    <!-- Bell Button -->
    <button
      @click="togglePopup"
      class="relative flex items-center justify-center rounded p-2 transition-all duration-200 hover:bg-surface-warm-hover"
      :class="{ 'bg-surface-warm-dark': showPopup }"
      title="Notifications"
    >
      <Icon
        icon="mdi:bell"
        class="h-5 w-5"
        :class="hasUnread ? 'text-[--color-theme-primary]' : 'text-gray-400'"
      />

      <!-- Unread Badge -->
      <span
        v-if="hasUnread"
        class="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white shadow-lg"
      >
        {{ unreadCount > 99 ? '99+' : unreadCount }}
      </span>
    </button>

    <!-- Notification Pop-up -->
    <Transition name="fade">
      <div
        v-if="showPopup"
        class="absolute right-0 top-12 z-50 w-96 rounded border border-theme-primary/30 bg-surface-warm shadow-2xl"
      >
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-surface-warm-hover px-4 py-3">
          <h3 class="font-semibold text-theme-primary">
            Notifications
          </h3>
          <button
            v-if="notifications.length > 0"
            @click="markAllAsRead"
            class="text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            Mark all read
          </button>
        </div>

        <!-- Notification List -->
        <div class="max-h-96 overflow-y-auto">
          <div v-if="isLoading" class="p-8 text-center text-gray-400">
            <Icon icon="mdi:loading" class="h-6 w-6 animate-spin inline-block" />
            <p class="mt-2 text-sm">Loading...</p>
          </div>

          <div v-else-if="notifications.length === 0" class="p-8 text-center text-gray-400">
            <Icon icon="mdi:bell-off" class="h-12 w-12 mx-auto mb-2 opacity-50" />
            <p class="text-sm">No notifications yet</p>
          </div>

          <div v-else class="divide-y divide-surface-warm-hover">
            <button
              v-for="notification in notifications"
              :key="notification.id"
              type="button"
              @click="handleNotificationClick(notification)"
              class="w-full border-0 p-4 text-left transition-colors cursor-pointer"
              :class="{
                'bg-surface-warm-dark': !notification.is_read,
                'hover:bg-surface-warm-hover': true,
              }"
            >
              <div class="flex items-start space-x-3">
                <Icon
                  :icon="getNotificationIcon(notification.notification_type)"
                  class="h-5 w-5 mt-0.5 flex-shrink-0"
                  :class="getPriorityColor(notification.priority)"
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-start justify-between">
                    <p
                      class="text-sm font-semibold"
                      :class="notification.is_read ? 'text-gray-400' : 'text-white'"
                    >
                      {{ notification.title }}
                    </p>
                    <span class="text-xs text-gray-500 ml-2 whitespace-nowrap">
                      {{ formatTime(notification.created_at) }}
                    </span>
                  </div>
                  <p
                    class="mt-1 text-xs"
                    :class="notification.is_read ? 'text-gray-500' : 'text-gray-300'"
                  >
                    {{ notification.message }}
                  </p>
                  <div v-if="!notification.is_read" class="mt-2 flex items-center">
                    <div class="h-2 w-2 rounded-full bg-theme-primary"></div>
                    <span class="ml-2 text-xs text-theme-primary">New</span>
                  </div>
                </div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Backdrop -->
    <Transition name="fade">
      <div v-if="showPopup" @click="showPopup = false" class="fixed inset-0 z-40"></div>
    </Transition>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
