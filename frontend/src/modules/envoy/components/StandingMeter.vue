<script setup lang="ts">
import { computed } from 'vue'
import { Progress } from '@/core/components/ui/progress'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'

const props = withDefaults(defineProps<{ standing: number; compact?: boolean }>(), {
  compact: false,
})

type LadderLabel = 'IDOLIZED' | 'LIKED' | 'ACCEPTED' | 'NEUTRAL' | 'SHUNNED' | 'HATED' | 'VILIFIED'

/** Fallout: New Vegas' ladder, with this repo's bounds. */
function ladderLabel(value: number): LadderLabel {
  if (value >= 80) return 'IDOLIZED'
  if (value >= 60) return 'LIKED'
  if (value >= 25) return 'ACCEPTED'
  if (value > -25) return 'NEUTRAL'
  if (value > -60) return 'SHUNNED'
  if (value >= -80) return 'HATED'
  return 'VILIFIED'
}

const MEANING: Record<LadderLabel, string> = {
  IDOLIZED: 'They open the gate on your word.',
  LIKED: 'Filings land in your favour and terms read fairly.',
  ACCEPTED: 'The line holds; your filings are answered on merit.',
  NEUTRAL: 'No credit either way. Every filing stands alone.',
  SHUNNED: 'Filings cost more and answers arrive late.',
  HATED: 'Expect a refusal before a hearing.',
  VILIFIED: 'Open hostility. Any filing reads as a provocation.',
}

const TONE: Record<LadderLabel, 'default' | 'warning' | 'danger' | 'success'> = {
  IDOLIZED: 'success',
  LIKED: 'success',
  ACCEPTED: 'default',
  NEUTRAL: 'default',
  SHUNNED: 'warning',
  HATED: 'danger',
  VILIFIED: 'danger',
}

const label = computed(() => ladderLabel(props.standing))
const meaning = computed(() => MEANING[label.value])
const percent = computed(() => Math.max(0, Math.min(100, ((props.standing + 100) / 200) * 100)))
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <div class="flex items-center justify-between gap-2">
      <span class="text-xs font-bold tracking-[0.12em] text-theme-primary/60">STANDING</span>
      <TooltipProvider :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <span
              class="cursor-help text-xs font-bold tracking-[0.12em] text-theme-primary"
              tabindex="0"
            >
              {{ label }}
            </span>
          </TooltipTrigger>
          <TooltipContent>{{ meaning }}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
    <Progress
      :model-value="percent"
      :size="compact ? 'xs' : 'sm'"
      :tone="TONE[label]"
      label="Standing"
      :value-text="`${standing}, ${label}`"
      segmented
    />
  </div>
</template>
