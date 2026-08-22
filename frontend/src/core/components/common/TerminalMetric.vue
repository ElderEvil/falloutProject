<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface Props {
  label: string
  value: string | number
  icon?: string
  compact?: boolean
  tone?: 'primary' | 'accent' | 'danger' | 'caps'
}

const { compact = false, tone = 'primary' } = defineProps<Props>()

const iconToneClasses = {
  primary: 'text-theme-primary',
  accent: 'text-theme-accent',
  danger: 'text-danger',
  caps: 'text-(--color-caps)',
}
</script>

<template>
  <article
    class="terminal-metric flex min-w-0 items-center rounded border border-theme-primary/20 bg-surface-sunken"
    :class="compact ? 'gap-2 px-2.5 py-2' : 'gap-2 p-2'"
  >
    <Icon
      v-if="icon"
      :icon="icon"
      class="shrink-0"
      :class="[compact ? 'h-4 w-4' : 'h-6 w-6', iconToneClasses[tone]]"
    />
    <div class="min-w-0">
      <p
        class="font-bold tracking-[0.12em] text-theme-primary/60"
        :class="compact ? 'text-[0.6rem]' : 'text-xs'"
      >
        {{ label }}
      </p>
      <p class="mt-0.5 font-bold tabular-nums text-theme-primary" :class="compact ? 'text-sm' : 'text-base'">
        {{ value }}
      </p>
    </div>
  </article>
</template>
