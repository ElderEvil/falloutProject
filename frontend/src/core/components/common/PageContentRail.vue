<script setup lang="ts">
withDefaults(
  defineProps<{
    /** `wide` (1400px) list/dashboard, `content` (1200px) reading column, `narrow` (900px) chat. */
    width?: 'wide' | 'content' | 'narrow'
  }>(),
  { width: 'wide' }
)

const MAX_WIDTH: Record<'wide' | 'content' | 'narrow', string> = {
  wide: 'max-w-[1400px]',
  content: 'max-w-[1200px]',
  narrow: 'max-w-[900px]',
}
</script>

<template>
  <div class="mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8" :class="MAX_WIDTH[width]">
    <slot />
  </div>
</template>
