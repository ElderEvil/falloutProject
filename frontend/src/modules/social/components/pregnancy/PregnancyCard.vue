<template>
  <UCard class="mb-2">
    <div class="flex items-center justify-between gap-4">
      <!-- Parent names -->
      <div class="flex-1">
        <div class="flex items-center gap-2">
          <span class="font-mono text-sm">{{ motherName }}</span>
          <span class="text-pink-400">+</span>
          <span class="font-mono text-sm">{{ fatherName }}</span>
        </div>

        <!-- Status badge -->
        <UBadge :color="statusColor" class="mt-1">
          {{ pregnancy.status }}
        </UBadge>
      </div>

      <!-- Progress bar -->
      <div class="flex-1 max-w-md">
        <div class="flex items-center justify-between text-xs mb-1" :style="{ color: 'var(--color-theme-primary)' }">
          <span>Progress: {{ Math.round(pregnancy.progress_percentage) }}%</span>
          <span v-if="!pregnancy.is_due">{{ timeRemaining }}</span>
          <span v-else class="text-yellow-400 font-bold">DUE NOW!</span>
        </div>
        <div class="h-3 bg-gray-800 border" :style="{ borderColor: 'var(--color-theme-primary)' }">
          <div
            class="h-full transition-all duration-500"
            :class="pregnancy.is_due ? 'bg-yellow-500 animate-pulse' : ''"
            :style="{
              width: `${pregnancy.progress_percentage}%`,
              backgroundColor: pregnancy.is_due ? undefined : 'var(--color-theme-primary)'
            }"
          ></div>
        </div>
      </div>

      <!-- Deliver button -->
      <UButton
        v-if="pregnancy.is_due"
        @click="$emit('deliver')"
        :disabled="isDelivering"
        class="animate-pulse"
      >
        {{ isDelivering ? 'Delivering...' : 'Deliver Baby' }}
      </UButton>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Pregnancy } from '@/models/pregnancy'
import { usePregnancyStore } from '@/stores/pregnancy'
import UCard from '@/core/components/ui/UCard.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import UButton from '@/core/components/ui/UButton.vue'

interface Props {
  pregnancy: Pregnancy
  motherName: string
  fatherName: string
  isDelivering?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isDelivering: false,
})

defineEmits<{
  deliver: []
}>()

const pregnancyStore = usePregnancyStore()

const statusColor = computed(() => {
  switch (props.pregnancy.status) {
    case 'pregnant':
      return props.pregnancy.is_due ? 'yellow' : 'green'
    case 'delivered':
      return 'blue'
    case 'miscarried':
      return 'red'
    default:
      return 'gray'
  }
})

const timeRemaining = computed(() => {
  return pregnancyStore.formatTimeRemaining(props.pregnancy.time_remaining_seconds)
})
</script>
