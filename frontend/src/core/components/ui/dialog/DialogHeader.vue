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
    data-slot="dialog-header"
    :class="cn('gap-2 flex flex-col', props.class)"
  >
    <slot />
  </div>
</template>
