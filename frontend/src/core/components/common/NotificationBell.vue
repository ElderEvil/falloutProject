<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import axios from '@/core/plugins/axios'

interface Notification {
  id: string
  notification_type: string
  title: string
  message: string
  priority: string
  is_read: boolean
  created_at: string
  meta_data?: Record<string, any>
}

const authStore = useAuthStore()
const showPopup = ref(false)
const notifications = ref<Notification[]>([])
const unreadCount = ref(0)
const isLoading = ref(false)
let pollIntervalId: number | null = null

const hasUnread = computed(() => unreadCount.value > 0)

const fetchNotifications = async () => {
  if (!authStore.token) return

  isLoading.value = true
  try {
    const response = await axios.get('/api/v1/notifications/', {
      params: { limit: 20 },
      headers: {
        Authorization: `Bearer ${authStore.token}`,
      },
    })

    notifications.value = response.data
  } catch (error) {
    console.error('Failed to fetch notifications:', error)
  } finally {
    isLoading.value = false
  }
}

const fetchUnreadCount = async () => {
  if (!authStore.token) return

  try {
    const response = await axios.get('/api/v1/notifications/unread-count', {
      headers: {
        Authorization: `Bearer ${authStore.token}`,
      },
    })

    unreadCount.value = response.data.count
  } catch (error) {
    console.error('Failed to fetch unread count:', error)
  }
}

const togglePopup = async () => {
  showPopup.value = !showPopup.value
  if (showPopup.value && notifications.value.length === 0) {
    await fetchNotifications()
  }
}

const markAsRead = async (notificationId: string) => {
  if (!authStore.token) return

  try {
    await axios.patch(
      `/api/v1/notifications/${notificationId}/read`,
      {},
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`,
        },
      }
    )

    const notification = notifications.value.find((n) => n.id === notificationId)
    if (notification) {
      notification.is_read = true
    }
    await fetchUnreadCount()
  } catch (error) {
    console.error('Failed to mark notification as read:', error)
  }
}

const markAllAsRead = async () => {
  if (!authStore.token) return

  try {
    await axios.post(
      '/api/v1/notifications/mark-all-read',
      {},
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`,
        },
      }
    )

    notifications.value.forEach((n) => (n.is_read = true))
    unreadCount.value = 0
  } catch (error) {
    console.error('Failed to mark all as read:', error)
  }
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
  const date = new Date(timestamp)
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
  // Poll for new notifications every 30 seconds
  pollIntervalId = setInterval(fetchUnreadCount, 30000)
})

onBeforeUnmount(() => {
  if (pollIntervalId !== null) {
    clearInterval(pollIntervalId)
    pollIntervalId = null
  }
})
</script>

<template>
  <div class="relative">
    <!-- Bell Button -->
    <button
      @click="togglePopup"
      class="relative flex items-center justify-center rounded p-2 transition-all duration-200 hover:bg-gray-800/50"
      :class="{ 'bg-gray-800/50': showPopup }"
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
        class="absolute right-0 top-12 z-50 w-96 rounded border bg-gray-900 shadow-2xl"
        :style="{
          borderColor: 'rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3)',
        }"
      >
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-gray-800 px-4 py-3">
          <h3 class="font-semibold" :style="{ color: 'var(--color-theme-primary)' }">
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

          <div v-else class="divide-y divide-gray-800">
            <div
              v-for="notification in notifications"
              :key="notification.id"
              @click="!notification.is_read && markAsRead(notification.id)"
              class="p-4 transition-colors cursor-pointer"
              :class="{
                'bg-gray-800/30': !notification.is_read,
                'hover:bg-gray-800/50': true,
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
                    <div class="h-2 w-2 rounded-full bg-blue-500"></div>
                    <span class="ml-2 text-xs text-blue-400">New</span>
                  </div>
                </div>
              </div>
            </div>
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
