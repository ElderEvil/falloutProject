<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Progress } from '@/core/components/ui/progress'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'

const props = withDefaults(
  defineProps<{
    name?: string
    image?: string | null
    stat: string
    currentStat: number
    targetStat: number
    progress: number
    timeRemaining: string
    kind?: 'training' | 'apprentice'
    roomName?: string
    ready?: boolean
    soon?: boolean
    inactive?: boolean
  }>(),
  { name: 'Dweller', kind: 'training' }
)

const ability = computed(() => getAbilityConfig(props.stat))
const fill = computed(() =>
  props.ready
    ? 'linear-gradient(to right, var(--color-theme-accent), var(--color-theme-primary), var(--color-theme-accent))'
    : 'linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent), var(--color-theme-primary))'
)
</script>

<template>
  <article
    class="learning-progress-card min-w-0 rounded-lg border bg-transparent p-3 transition-colors duration-200"
    :class="{
      'border-theme-primary shadow-[0_0_10px_var(--color-theme-glow)]': !ready && !inactive,
      'completion-ready border-theme-accent shadow-[0_0_14px_var(--color-theme-glow)]': ready,
      'border-theme-glow opacity-60': inactive,
    }"
  >
    <div class="mb-2 flex items-center gap-2">
      <DwellerPortrait
        :thumbnail-url="image"
        :alt="name"
        image-class="size-9 shrink-0 rounded-md border border-theme-glow object-cover [image-rendering:pixelated]"
        fallback-class="flex size-9 shrink-0 items-center justify-center rounded-md border border-theme-glow bg-surface-sunken text-theme-primary"
      />
      <div class="min-w-0 flex-1">
        <p class="truncate font-mono text-sm font-bold text-theme-primary" :title="name">
          {{ name }}
        </p>
        <p v-if="roomName" class="truncate font-mono text-xs text-muted-foreground">
          {{ roomName }}
        </p>
      </div>
      <Badge :variant="kind === 'apprentice' ? 'secondary' : 'outline'" class="shrink-0 gap-1">
        <Icon :icon="kind === 'apprentice' ? 'mdi:school' : 'mdi:dumbbell'" class="size-3" />
        {{ kind === 'apprentice' ? 'Apprentice' : 'Training' }}
      </Badge>
    </div>
    <div
      class="mb-2 flex flex-wrap items-center justify-between gap-2 font-mono text-xs text-theme-primary"
    >
      <span class="inline-flex items-center gap-1">
        <Icon :icon="ability?.icon ?? 'mdi:star'" class="completion-stat-icon size-4 shrink-0" />
        {{ ability?.label ?? stat }} {{ currentStat }} → {{ targetStat }}
      </span>
      <slot name="goal" />
    </div>
    <Progress class="mb-2 h-1.5" :fill="fill" :model-value="progress" />
    <div class="flex flex-wrap items-center gap-2">
      <span
        class="completion-time font-mono text-xs text-theme-primary"
        :class="{ 'text-theme-accent': ready }"
        >{{ timeRemaining }}</span
      >
      <Badge v-if="soon" variant="secondary">Soon</Badge>
      <div v-if="$slots.actions" class="ml-auto flex gap-1"><slot name="actions" /></div>
    </div>
  </article>
</template>
