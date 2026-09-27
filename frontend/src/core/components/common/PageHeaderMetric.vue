<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'

defineProps<{
  label: string
  value: number | string
  icon: string
}>()
</script>

<template>
  <Card
    size="sm"
    class="min-w-28 flex-row items-center gap-2 rounded-md border border-theme-primary/20 bg-surface-sunken px-3 py-2 shadow-none ring-0"
  >
    <Icon :icon="icon" class="h-4 w-4 shrink-0 text-theme-primary/70" :ariaHidden="true" />
    <div class="min-w-0">
      <div class="page-header-metric-value text-lg font-bold leading-none text-theme-primary">
        {{ value }}
      </div>
      <div
        class="mt-1 text-[0.65rem] font-bold uppercase leading-tight tracking-[0.1em] text-theme-primary/55"
      >
        {{ label }}
      </div>
    </div>
  </Card>
</template>
