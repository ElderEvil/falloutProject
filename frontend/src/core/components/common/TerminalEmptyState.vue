<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  icon: string
  title: string
  description?: string
  compact?: boolean
}

withDefaults(defineProps<Props>(), { compact: false, description: undefined })
</script>

<template>
  <section
    class="flex flex-col items-center justify-center rounded-lg border border-theme-primary/15 bg-surface px-6 text-center"
    :class="compact ? 'gap-2 py-8' : 'gap-3 py-12 sm:py-16'"
  >
    <Icon :icon="icon" class="text-theme-primary/35" :class="compact ? 'h-12 w-12' : 'h-16 w-16'" />
    <h3 class="text-xl font-bold text-theme-primary">{{ title }}</h3>
    <p v-if="description" class="max-w-lg text-sm leading-relaxed text-theme-primary/60">
      {{ description }}
    </p>
    <div v-if="$slots.actions" class="mt-2"><slot name="actions" /></div>
  </section>
</template>
