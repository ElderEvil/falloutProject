<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/core/utils/cn'

interface SkeletonProps {
  class?: HTMLAttributes['class']
}

const props = defineProps<SkeletonProps>()
</script>

<template>
  <!-- @vue-ignore -->
  <div
    data-slot="skeleton"
    :class="cn('bg-muted rounded-md animate-pulse', props.class)"
  />
</template>
