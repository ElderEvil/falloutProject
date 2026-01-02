<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Notification } from '@/stores/notification'

interface Props {
  notification: Notification
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'close'): void
}>()

const showDetails = ref(false)
const isVisible = ref(true)

const close = () => {
  isVisible.value = false
  setTimeout(() => {
    emit('close')
  }, 300)
}

const toggleDetails = () => {
  showDetails.value = !showDetails.value
}

const variantClasses = computed(() => {
  switch (props.notification.type) {
    case 'success':
      return 'bg-green-900 bg-opacity-40 text-green-300'
    case 'error':
      return 'bg-red-900 bg-opacity-50 border-red-500 text-red-200'
    case 'warning':
      return 'bg-yellow-900 bg-opacity-40 border-yellow-500 text-yellow-200'
    case 'info':
      return 'bg-blue-900 bg-opacity-40 border-blue-500 text-blue-200'
    default:
      return 'bg-blue-900 bg-opacity-40 border-blue-500 text-blue-200'
  }
})

const borderStyle = computed(() => {
  if (props.notification.type === 'success') {
    return { borderColor: 'var(--color-theme-primary)' }
  }
  return {}
})

const iconPath = computed(() => {
  switch (props.notification.type) {
    case 'success':
      return 'M5 13l4 4L19 7'
    case 'error':
      return 'M6 18L18 6M6 6l12 12'
    case 'warning':
      return 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z'
    case 'info':
      return 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
    default:
      return ''
  }
})
</script>

<template>
  <Transition name="notification">
    <div
      v-if="isVisible"
      :class="variantClasses"
      :style="borderStyle"
      class="rounded-lg border-2 p-4 shadow-lg min-w-[320px] max-w-md"
      role="alert"
    >
      <div class="flex items-start gap-3">
        <!-- Icon -->
        <svg class="h-6 w-6 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="iconPath" />
        </svg>

        <!-- Content -->
        <div class="flex-1 min-w-0">
          <h4 class="font-bold mb-1 text-sm">{{ notification.title }}</h4>
          <p class="text-sm break-words">{{ notification.message }}</p>

          <!-- Details toggle -->
          <div v-if="notification.details" class="mt-2">
            <button
              @click="toggleDetails"
              class="text-xs opacity-70 hover:opacity-100 transition-opacity underline"
            >
              {{ showDetails ? 'Hide details' : 'Show details' }}
            </button>
            <Transition name="details">
              <pre
                v-if="showDetails"
                class="mt-2 text-xs opacity-70 bg-black bg-opacity-20 p-2 rounded overflow-x-auto"
              >{{ notification.details }}</pre>
            </Transition>
          </div>
        </div>

        <!-- Close Button -->
        <button
          @click="close"
          class="flex-shrink-0 hover:opacity-70 transition-opacity"
          aria-label="Dismiss notification"
        >
          <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.notification-enter-active,
.notification-leave-active {
  transition: all 0.3s ease;
}

.notification-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.notification-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.details-enter-active,
.details-leave-active {
  transition: all 0.2s ease;
}

.details-enter-from,
.details-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
