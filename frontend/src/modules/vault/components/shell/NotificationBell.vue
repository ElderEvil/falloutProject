<script setup lang="ts">
import { ref, shallowRef, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSse, type SseEvent } from '@/core/composables/useEventStream'
import { useSound } from '@/core/composables/useSound'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import { FEEDBACK_TIMING_MS } from '@/core/config/feedback'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useToast } from '@/core/composables/useToast'
import { useBlockingOverlay } from '@/core/composables/useBlockingOverlay'
import { addPendingReport } from '@/modules/exploration/composables/usePendingReports'
import type { RewardsSummary } from '@/modules/exploration/stores/exploration'
import {
  getNotificationRoute,
  getNotificationSound,
  getNotificationAnimation,
} from '@/modules/vault/utils/notificationRouting'
import { formatRelativeTime } from '@/core/utils/time'
import { Button } from '@/core/components/ui/button'
import { useNotificationInboxStore } from '@/modules/vault/stores/notificationInbox'
import type { InboxNotification } from '@/modules/vault/services/notificationService'
import { useStorageStore } from '@/modules/storage/stores/storage'

const inboxStore = useNotificationInboxStore()
const authStore = useAuthStore()
const objectivesStore = useObjectivesStore()
const router = useRouter()
const { playSound } = useSound()
const toast = useToast()
const vaultStore = useVaultStore()
const feedback = useVaultBoyFeedback()
const POPUP_ID = 'notifications-popup'
const showPopup = ref(false)
useBlockingOverlay(() => showPopup.value)
const bellButtonRef = ref<HTMLButtonElement | null>(null)
const popupRef = ref<HTMLElement | null>(null)
const unreadCount = computed(() => inboxStore.unreadCount)
const seenNotificationIds = new Set<string>()
let hasConnected = false
const hasUnread = computed(() => unreadCount.value > 0)

// Delayed rush results must not land in a later session's bell or outlive the
// component, so the timers are tracked and cleared on unmount.
const rushTimers = new Set<ReturnType<typeof setTimeout>>()
const scheduleRushNotification = (callback: () => void): void => {
  const timer = setTimeout(() => {
    rushTimers.delete(timer)
    callback()
  }, FEEDBACK_TIMING_MS.rushDelay)
  rushTimers.add(timer)
}

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
    if (token) {
      startSse()
      // Rotation can invalidate the initial response before SSE has ever connected.
      void inboxStore.refreshUnreadCount()
    } else {
      sse.value?.close()
      sse.value = undefined
      seenNotificationIds.clear()
      hasConnected = false
    }
  }
)

const currentSseEvent = computed<SseEvent | null>(() => {
  const instance = sse.value
  return instance?.event.value ?? null
})

function isAdoptionNotification(notification: InboxNotification): boolean {
  return (
    notification.notification_type === 'relationship_formed' &&
    notification.meta_data?.event === 'child_adopted'
  )
}

// The same delivery path surfaces live events and unread events missed while paused.
function processNotification(notificationData: InboxNotification) {
  if (seenNotificationIds.has(notificationData.id)) return
  seenNotificationIds.add(notificationData.id)
  const newNotif: InboxNotification = {
    ...notificationData,
    vault_id: notificationData.vault_id ?? null,
    from_dweller_id: notificationData.from_dweller_id ?? null,
    is_read: false,
  }
  inboxStore.rememberNotifications([newNotif])
  const isRushResult =
    notificationData.notification_type === 'rush_succeeded' ||
    notificationData.notification_type === 'rush_failed'
  if (isRushResult) {
    const isSuccess = notificationData.notification_type === 'rush_succeeded'
    const vaultId = notificationData.vault_id
    const message = notificationData.message
    const session = inboxStore.sessionKey
    scheduleRushNotification(() => {
      if (inboxStore.sessionKey !== session) return
      inboxStore.receiveNotification(newNotif)
      inboxStore.noteUnreadArrival()
      if (vaultId && vaultId !== vaultStore.activeVaultId) return
      if (isSuccess) toast.success(message)
      else toast.error(message)
    })
    return
  }
  inboxStore.receiveNotification(newNotif)
  inboxStore.noteUnreadArrival()
  playSound(getNotificationSound(notificationData.notification_type))
  const animation = getNotificationAnimation(notificationData.notification_type)
  if (
    animation &&
    notificationData.vault_id &&
    notificationData.vault_id === vaultStore.activeVaultId
  ) {
    feedback.show({
      animation,
      title: notificationData.title,
      message: notificationData.message,
      vaultId: notificationData.vault_id,
      key: animation === 'baby' ? `birth:${notificationData.id}` : 'celebration',
    })
  }
  if (notificationData.notification_type === 'baby_born') toast.success(notificationData.message)
  if (
    notificationData.notification_type === 'exploration_update' &&
    notificationData.meta_data?.event === 'site_found'
  ) {
    toast.info(notificationData.message, 10_000)
  }
  // A hazard team join surfaces beyond the bell (progression red line).
  if (
    ['storage_item_degraded', 'storage_item_upgraded'].includes(notificationData.notification_type)
  ) {
    if (notificationData.notification_type === 'storage_item_upgraded')
      toast.success(notificationData.message)
    else toast.info(notificationData.message)
    if (notificationData.vault_id) useStorageStore().refreshIfActive(notificationData.vault_id)
  }

  if (
    ['hazard_team_joined', 'training_complete', 'room_unlocked'].includes(
      notificationData.notification_type
    ) ||
    isAdoptionNotification(notificationData)
  ) {
    toast.success(notificationData.message)
  }
  // An arena morale boost is vault-wide and asynchronous; announce it beyond the bell
  // (progression red line).
  if (notificationData.notification_type === 'arena_morale_boost') {
    toast.success(notificationData.message)
  }
  // Arrival is asynchronous, so away from the exploration routes this would be bell-only
  // (progression red line): announce it and queue the reward report without a bell click.
  if (notificationData.notification_type === 'exploration_complete') {
    enqueuePendingReport(newNotif)
    toast.success(notificationData.message)
  }
  // A quest party arrival is also asynchronous; toast it when the rewards are claimable.
  if (
    notificationData.notification_type === 'quest_complete' &&
    notificationData.meta_data?.ready_to_claim
  ) {
    toast.success(notificationData.message)
  }
  // A cleared point's loot haul is asynchronous; announce it (progression red line).
  if (notificationData.notification_type === 'location_cleared') {
    const locationName = notificationData.meta_data?.location_name
    toast.success(
      typeof locationName === 'string'
        ? `${locationName} cleared — loot hauled`
        : notificationData.message
    )
  }
  // A point is re-lootable; announce it (progression red line).
  if (notificationData.notification_type === 'location_ready') {
    const locationName = notificationData.meta_data?.location_name
    toast.info(
      typeof locationName === 'string'
        ? `${locationName} is ready to be cleared again`
        : notificationData.message
    )
  }
  // A recipe unlock is asynchronous (scrapping happens elsewhere); announce it (progression red line).
  if (notificationData.notification_type === 'recipe_unlocked') {
    toast.success(notificationData.message)
  }
  // Objective completion is asynchronous; announce it beyond the bell (progression red line).
  if (
    ['objective_completed', 'objectives_refreshed'].includes(notificationData.notification_type)
  ) {
    toast.success(notificationData.message)
    if (newNotif.vault_id && objectivesStore.objectivesVaultId === newNotif.vault_id) {
      void objectivesStore.fetchObjectives(newNotif.vault_id).catch((error) => {
        handleStoreError(error, 'Failed to reload objectives after progression')
      })
    }
  }
}

watch(currentSseEvent, (evt) => {
  if (!evt || evt.event !== 'notification') return
  const notification = (evt.data as { notification?: InboxNotification })?.notification
  if (notification) processNotification(notification)
})

const fetchNotifications = async (catchUp = false) => {
  const token = authStore.token
  if (!token) return
  const loaded = await inboxStore.loadRecent()
  if (authStore.token !== token) return
  if (catchUp)
    loaded
      .filter((notification) => !inboxStore.isRead(notification))
      .reverse()
      .forEach(processNotification)
  loaded.forEach((notification) => seenNotificationIds.add(notification.id))
}

// Reconnecting cannot replay Redis pub/sub history. Only reload after the
// connection actually opens, including a new stream after token rotation.
watch(
  () => sse.value?.status.value,
  async (status) => {
    if (status !== 'open' || !authStore.token) return
    if (hasConnected) {
      await fetchNotifications(true)
      await fetchUnreadCount()
    }
    hasConnected = true
  }
)

const fetchUnreadCount = async () => {
  if (authStore.token) await inboxStore.refreshUnreadCount()
}

const isActionable = (notification: InboxNotification): boolean =>
  getNotificationRoute(notification) !== null

const closePopup = () => {
  if (!showPopup.value) return
  showPopup.value = false
  // Every close path (Escape, backdrop, activation) returns focus to the bell.
  nextTick(() => bellButtonRef.value?.focus())
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') closePopup()
}

const togglePopup = async () => {
  if (showPopup.value) {
    closePopup()
    return
  }
  showPopup.value = true
  // Move focus into the popup so keyboard users can traverse the list.
  nextTick(() => popupRef.value?.focus())
  if (inboxStore.recentNotifications.length === 0) {
    await fetchNotifications()
  }
}

const markAllAsRead = async () => {
  if (authStore.token) await inboxStore.markAllRead(null)
}

const enqueuePendingReport = (notification: InboxNotification): void => {
  if (notification.notification_type !== 'exploration_complete') return
  const meta = notification.meta_data
  const rewards = meta?.rewards
  const explorationId = meta?.exploration_id
  const dwellerId = meta?.dweller_id
  const dwellerName = meta?.dweller_name
  if (
    !rewards ||
    !notification.vault_id ||
    typeof explorationId !== 'string' ||
    typeof dwellerId !== 'string' ||
    typeof dwellerName !== 'string'
  )
    return
  addPendingReport({
    explorationId,
    vaultId: notification.vault_id,
    dwellerId,
    dwellerName,
    rewards: rewards as RewardsSummary,
  })
}

const handleNotificationClick = (notification: InboxNotification) => {
  const route = getNotificationRoute(notification)
  if (!route) return
  closePopup()
  enqueuePendingReport(notification)
  void router.push(route)
  if (!inboxStore.isRead(notification)) inboxStore.markReadOnOpen(notification)
}

const getNotificationIcon = (notification: InboxNotification): string => {
  if (isAdoptionNotification(notification)) return 'mdi:account-heart'
  const iconMap: Record<string, string> = {
    baby_born: 'mdi:baby-face',
    storage_item_degraded: 'mdi:tools',
    storage_item_upgraded: 'mdi:arrow-up-bold',
    dweller_died: 'mdi:skull',
    dweller_exit_requested: 'mdi:exit-run',
    exploration_complete: 'mdi:map-marker-check',
    exploration_update: 'mdi:map-marker',
    hazard_team_joined: 'mdi:shield-account',
    room_unlocked: 'mdi:door-open',
    level_up: 'mdi:arrow-up-bold',
    quest_complete: 'mdi:treasure-chest',
    training_complete: 'mdi:school',
    combat_started: 'mdi:sword-cross',
    combat_victory: 'mdi:sword',
    combat_defeat: 'mdi:skull-crossbones',
    radio_new_dweller: 'mdi:radio',
    radio_auto_switched_to_happiness: 'mdi:radio-tower',
    resource_low: 'mdi:alert',
    location_cleared: 'mdi:flag-checkered',
    location_ready: 'mdi:map-marker-refresh',
  }
  return iconMap[notification.notification_type] || 'mdi:information'
}

const getPriorityColor = (priority: string): string => {
  const colorMap: Record<string, string> = {
    urgent: 'text-danger',
    high: 'text-theme-accent',
    normal: 'text-theme-primary',
    info: 'text-muted-foreground',
  }
  return colorMap[priority] || 'text-muted-foreground'
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  fetchUnreadCount()
  fetchNotifications()
  if (authStore.token) {
    startSse()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  rushTimers.forEach((timer) => clearTimeout(timer))
  rushTimers.clear()
  sse.value?.close()
})
</script>

<template>
  <div class="relative">
    <!-- Bell Button -->
    <TooltipProvider :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <button
            ref="bellButtonRef"
            @click="togglePopup"
            class="relative flex items-center justify-center rounded p-2 transition-all duration-200 hover:bg-surface-warm-hover"
            :class="{ 'bg-surface-warm-dark': showPopup }"
            :aria-label="
              hasUnread
                ? `Notifications ${unreadCount > 99 ? '99+' : unreadCount} unread`
                : 'Notifications'
            "
            aria-haspopup="dialog"
            :aria-expanded="showPopup"
            :aria-controls="POPUP_ID"
          >
            <Icon
              icon="mdi:bell"
              class="h-5 w-5"
              :class="hasUnread ? 'text-theme-primary' : 'text-muted-foreground'"
            />

            <!-- Unread Badge -->
            <span
              v-if="hasUnread"
              class="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-theme-primary text-xs font-bold text-black shadow-lg"
            >
              {{ unreadCount > 99 ? '99+' : unreadCount }}
            </span>
          </button>
        </TooltipTrigger>
        <TooltipContent>Notifications</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <!-- Notification Pop-up -->
    <Transition name="fade">
      <div
        v-if="showPopup"
        :id="POPUP_ID"
        ref="popupRef"
        role="dialog"
        aria-label="Notifications"
        tabindex="-1"
        class="fixed left-2 top-[var(--chrome-height)] z-50 mt-2 w-[min(24rem,calc(100vw_-_1rem))] rounded border border-theme-primary/30 bg-surface-warm shadow-2xl focus:outline-none sm:absolute sm:left-auto sm:right-0 sm:top-12 sm:mt-0"
      >
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-surface-warm-hover px-4 py-3">
          <h3 class="font-semibold text-theme-primary">Notifications</h3>
          <!-- Raw popup buttons: bespoke popup styling; migrate with the component (docs/frontend/RAW_NATIVE_CONTROLS.md). -->
          <button
            v-if="inboxStore.recentNotifications.length > 0"
            @click="markAllAsRead"
            :disabled="inboxStore.isSaving"
            class="text-xs text-muted-foreground hover:text-white transition-colors"
          >
            Mark all read
          </button>
        </div>

        <div class="border-b border-surface-warm-hover px-4 py-2">
          <Button variant="link" as-child>
            <RouterLink to="/notifications" @click="closePopup">View all notifications</RouterLink>
          </Button>
        </div>

        <!-- Notification List -->
        <div class="max-h-96 overflow-y-auto">
          <div v-if="inboxStore.isRecentLoading" class="p-8 text-center text-muted-foreground">
            <Icon icon="mdi:loading" class="h-6 w-6 animate-spin inline-block" />
            <p class="mt-2 text-sm">Loading...</p>
          </div>

          <div
            v-else-if="inboxStore.recentNotifications.length === 0"
            class="p-8 text-center text-muted-foreground"
          >
            <Icon icon="mdi:bell-off" class="h-12 w-12 mx-auto mb-2 opacity-50" />
            <p class="text-sm">No notifications yet</p>
          </div>

          <div v-else class="divide-y divide-surface-warm-hover">
            <!-- Actionable rows (getNotificationRoute resolves) are buttons;
                 informational rows render as plain content, never dead buttons. -->
            <component
              :is="isActionable(notification) ? 'button' : 'div'"
              v-for="notification in inboxStore.recentNotifications"
              :key="notification.id"
              :data-notification-id="notification.id"
              :type="isActionable(notification) ? 'button' : null"
              class="block w-full border-0 p-4 text-left"
              :class="{
                'bg-surface-warm-dark': !inboxStore.isRead(notification),
                'cursor-pointer transition-colors hover:bg-surface-warm-hover':
                  isActionable(notification),
              }"
              v-on="
                isActionable(notification)
                  ? { click: () => handleNotificationClick(notification) }
                  : {}
              "
            >
              <div class="flex items-start space-x-3">
                <Icon
                  :icon="getNotificationIcon(notification)"
                  class="h-5 w-5 mt-0.5 flex-shrink-0"
                  :class="getPriorityColor(notification.priority)"
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-start justify-between">
                    <p
                      class="text-sm font-semibold"
                      :class="
                        inboxStore.isRead(notification) ? 'text-muted-foreground' : 'text-white'
                      "
                    >
                      {{ notification.title }}
                    </p>
                    <span class="text-xs text-muted-foreground ml-2 whitespace-nowrap">
                      {{ formatRelativeTime(notification.created_at) }}
                    </span>
                  </div>
                  <p class="mt-1 text-xs text-muted-foreground">
                    {{ notification.message }}
                  </p>
                  <div v-if="!inboxStore.isRead(notification)" class="mt-2 flex items-center">
                    <div class="h-2 w-2 rounded-full bg-theme-primary"></div>
                    <span class="ml-2 text-xs text-theme-primary">New</span>
                  </div>
                </div>
                <Icon
                  v-if="isActionable(notification)"
                  icon="mdi:chevron-right"
                  class="h-5 w-5 mt-0.5 flex-shrink-0 text-muted-foreground"
                  :ariaHidden="true"
                />
              </div>
            </component>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Backdrop -->
    <Transition name="fade">
      <div
        v-if="showPopup"
        @click="closePopup"
        class="notification-backdrop fixed inset-0 z-40"
        aria-hidden="true"
      ></div>
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
