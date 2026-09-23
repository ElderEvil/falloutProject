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
    data-slot="alert-title"
    :class="cn('font-medium group-has-[>svg]/alert:col-start-2 cn-font-heading [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-foreground', props.class)"
  >
    <slot />
  </div>
</template>
