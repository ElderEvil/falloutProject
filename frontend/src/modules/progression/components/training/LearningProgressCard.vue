<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Progress } from '@/core/components/ui/progress'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
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
    class="learning-progress-card flex min-h-36 min-w-0 gap-3 rounded-lg border bg-transparent p-3 transition-colors duration-200"
    :class="{
      'border-theme-primary shadow-[0_0_10px_var(--color-theme-glow)]': !ready && !inactive,
      'completion-ready border-theme-accent shadow-[0_0_14px_var(--color-theme-glow)]': ready,
      'border-theme-glow opacity-60': inactive,
    }"
  >
    <div class="w-16 shrink-0">
      <DwellerPortrait
        :thumbnail-url="image"
        :alt="name"
        image-class="h-24 w-full rounded-md border border-theme-glow object-cover object-top [image-rendering:pixelated]"
        fallback-class="flex h-24 w-full items-center justify-center rounded-md border border-theme-glow bg-surface-sunken text-theme-primary"
      />
    </div>
    <div class="flex min-w-0 flex-1 flex-col">
      <div class="mb-2 flex items-start gap-2">
        <div class="min-w-0 flex-1">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger as-child>
                <p
                  tabindex="0"
                  class="truncate rounded-sm font-mono text-sm font-bold text-theme-primary focus-visible:outline-2 focus-visible:outline-theme-primary"
                >
                  {{ name }}
                </p>
              </TooltipTrigger>
              <TooltipContent>{{ name }}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
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
      <Progress
        class="mb-2 h-1.5"
        :fill="fill"
        :model-value="progress"
        :label="`${ability?.label ?? stat} ${kind} progress for ${name}`"
      />
      <div class="mt-auto flex flex-wrap items-center gap-2">
        <span
          class="completion-time font-mono text-xs text-theme-primary"
          :class="{ 'text-theme-accent': ready }"
          >{{ timeRemaining }}</span
        >
        <Badge v-if="soon" variant="secondary">Soon</Badge>
        <div v-if="$slots.actions" class="ml-auto flex gap-1"><slot name="actions" /></div>
      </div>
    </div>
  </article>
</template>
