<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'

withDefaults(
  defineProps<{
    canComplete: boolean
    canRecall?: boolean
    isReturning?: boolean
    compact?: boolean
  }>(),
  {
    canRecall: true,
    isReturning: false,
    compact: false,
  }
)

const emit = defineEmits<{
  complete: []
  recall: []
}>()
</script>

<template>
  <div
    :class="
      compact
        ? 'flex gap-2 border-t border-theme-primary/20 pt-2'
        : 'grid grid-cols-1 gap-3 lg:grid-cols-2'
    "
    @click.stop
  >
    <UButton
      v-if="isReturning"
      disabled
      variant="secondary"
      :size="compact ? 'sm' : 'lg'"
      :block="!compact"
      class="flex-1"
    >
      <Icon :class="compact ? 'h-5 w-5' : 'h-6 w-6'" icon="mdi:home-import-outline" />
      {{ compact ? 'Returning' : 'Returning Home…' }}
    </UButton>
    <UButton
      v-else-if="canComplete"
      @click="emit('complete')"
      :size="compact ? 'sm' : 'lg'"
      :block="!compact"
      class="flex-1"
    >
      <Icon :class="compact ? 'h-5 w-5' : 'h-6 w-6'" icon="mdi:check-circle" />
      {{ compact ? 'Complete' : 'Complete Exploration' }}
    </UButton>
    <UButton
      v-if="!isReturning && canRecall"
      @click="emit('recall')"
      variant="secondary"
      :size="compact ? 'sm' : 'lg'"
      :block="!compact"
      class="flex-1"
    >
      <Icon :class="compact ? 'h-5 w-5' : 'h-6 w-6'" icon="mdi:arrow-u-left-top" />
      {{ compact ? 'Recall' : 'Recall Dweller' }}
    </UButton>
  </div>
</template>
