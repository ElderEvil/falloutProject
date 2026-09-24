<script setup lang="ts">
withDefaults(
  defineProps<{
    /** `wide` (1400px) for list/dashboard pages, `content` (1200px) for a narrow reading column. */
    width?: 'wide' | 'content'
  }>(),
  { width: 'wide' }
)
</script>

<template>
  <div
    class="mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8"
    :class="width === 'wide' ? 'max-w-[1400px]' : 'max-w-[1200px]'"
  >
    <slot />
  </div>
</template>
