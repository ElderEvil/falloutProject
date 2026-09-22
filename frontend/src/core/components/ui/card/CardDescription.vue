<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/core/utils/cn'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <!-- @vue-ignore -->
  <div
    data-slot="card-description"
    :class="cn('text-muted-foreground text-sm', props.class)"
  >
    <slot />
  </div>
</template>
