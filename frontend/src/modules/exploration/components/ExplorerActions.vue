<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'

withDefaults(defineProps<{
  canComplete: boolean
  compact?: boolean
}>(), {
  compact: false,
})

const emit = defineEmits<{
  complete: []
  recall: []
}>()
</script>

<template>
  <div
    :class="compact ? 'flex gap-2 border-t border-theme-primary/20 pt-2' : 'grid grid-cols-1 gap-3 lg:grid-cols-2'"
    @click.stop
  >
    <Button
      v-if="canComplete"
      @click="emit('complete')"
      :size="compact ? 'sm' : 'lg'"
      :class="compact ? 'flex-1' : 'w-full'"
    >
      <Icon :class="compact ? 'h-5 w-5' : 'h-6 w-6'" icon="mdi:check-circle" />
      {{ compact ? 'Complete' : 'Complete Exploration' }}
    </Button>
    <Button
      @click="emit('recall')"
      variant="secondary"
      :size="compact ? 'sm' : 'lg'"
      :class="compact ? 'flex-1' : 'w-full'"
    >
      <Icon :class="compact ? 'h-5 w-5' : 'h-6 w-6'" icon="mdi:arrow-u-left-top" />
      {{ compact ? 'Recall' : 'Recall Dweller' }}
    </Button>
  </div>
</template>
