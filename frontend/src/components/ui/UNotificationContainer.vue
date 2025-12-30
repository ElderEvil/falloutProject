<script setup lang="ts">
import { useNotificationStore } from '@/stores/notification'
import UNotification from './UNotification.vue'

const notificationStore = useNotificationStore()
</script>

<template>
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-3 pointer-events-none">
    <div
      v-for="notification in notificationStore.notifications"
      :key="notification.id"
      class="pointer-events-auto"
    >
      <UNotification
        :notification="notification"
        @close="notificationStore.remove(notification.id)"
      />
    </div>
  </div>
</template>
