<script setup lang="ts">
import { Progress } from '@/core/components/ui/progress'
import type { CollectibleSetProgressRead } from '../models/map'

defineProps<{ sets: CollectibleSetProgressRead[] }>()

const percent = (set: CollectibleSetProgressRead): number =>
  set.required > 0 ? Math.min(100, Math.round((set.held / set.required) * 100)) : 0
</script>

<template>
  <section class="space-y-3 p-4 text-xs text-theme-primary" aria-label="Collectible sets">
    <p class="leading-relaxed text-theme-primary/65">
      Every collectible a vault finds closes its set. A completed set raises the bonus it pays.
    </p>
    <p
      v-for="set in sets"
      :key="set.set"
      class="collectible-set rounded border border-theme-primary/25 bg-surface-sunken p-3"
    >
      <span class="flex items-baseline justify-between gap-2">
        <span class="font-semibold">{{ set.name }}</span>
        <span class="tabular-nums text-theme-primary/70">{{ set.held }} / {{ set.required }}</span>
      </span>
      <Progress
        class="mt-2 h-1"
        size="xs"
        :model-value="percent(set)"
        :label="`${set.name} set progress`"
      />
      <span
        v-if="set.active"
        class="set-active mt-2 inline-block rounded-sm border border-theme-primary/40 px-1 text-[0.625rem] font-bold uppercase tracking-[0.05em]"
      >
        Bonus active
      </span>
    </p>
  </section>
</template>
