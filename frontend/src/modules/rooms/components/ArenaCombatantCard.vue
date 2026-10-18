<script setup lang="ts">
import { Card } from '@/core/components/ui/card'

defineProps<{
  name: string
  subtitle?: string
  health: number
  maxHealth: number
  power: number | null
  editable: boolean
  hostile?: boolean
}>()
</script>

<template>
  <Card size="sm" class="combatant-card min-w-0 flex-1 data-[size=sm]:gap-0 data-[size=sm]:py-2">
    <div
      class="grid min-w-0 grid-cols-[5rem_minmax(0,1fr)] items-center gap-x-2 gap-y-2 px-2 sm:grid-cols-[7rem_minmax(0,1fr)_auto]"
    >
      <div
        class="col-start-1 row-start-1 flex size-20 items-center justify-center overflow-hidden rounded border border-input bg-surface-raised sm:size-28"
      >
        <slot name="portrait" />
      </div>
      <div
        v-if="editable"
        class="col-start-2 row-start-1 flex flex-col items-end justify-center gap-1 sm:col-start-3"
      >
        <slot name="management" />
      </div>
      <div
        class="col-span-2 col-start-1 row-start-2 min-w-0 sm:col-span-1 sm:col-start-2 sm:row-start-1"
      >
        <p
          class="line-clamp-2 text-sm font-semibold sm:text-base"
          :class="hostile ? 'text-danger' : 'text-theme-primary'"
          :title="name"
        >
          {{ name }}
        </p>
        <p class="flex flex-wrap gap-x-2 text-xs text-muted-foreground">
          <span v-if="subtitle">{{ subtitle }}</span>
          <span v-if="power !== null">POW {{ power }}</span>
        </p>
        <p class="text-xs tabular-nums text-muted-foreground">{{ health }}/{{ maxHealth }} HP</p>
      </div>
    </div>
  </Card>
</template>
