<script setup lang="ts">
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from '@/core/components/ui/tooltip'

import { computed, nextTick, ref, watch } from 'vue'
import { Zap } from '@lucide/vue'
import CombatSkillIcon from '@/modules/combat/components/CombatSkillIcon.vue'
import { parseUtcMs } from '@/core/utils/time'
import { formatDateTime } from '@/core/utils/format'
import { Button } from '@/core/components/ui/button'
import type { BattleLogEntry } from '../models/battleLog'

const props = defineProps<{
  entries: BattleLogEntry[]
  emptyText: string
  fill?: boolean
}>()

const groupedEntries = computed<Array<BattleLogEntry & { count: number }>>(() => {
  const grouped: Array<BattleLogEntry & { count: number }> = []
  for (const entry of props.entries) {
    const previous = grouped[grouped.length - 1]
    if (
      previous &&
      !entry.timestamp &&
      !previous.timestamp &&
      previous.kind === entry.kind &&
      previous.message === entry.message
    ) {
      // Presentation-level collapse: consecutive identical lines read as one
      // round summary; the first entry anchors the row's delta and meta.
      previous.count += 1
    } else {
      grouped.push({ ...entry, count: 1 })
    }
  }
  return grouped
})

const clock = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
})
const eventTime = (timestamp: string) => clock.format(new Date(parseUtcMs(timestamp)))
const eventDate = (timestamp: string) => formatDateTime(new Date(parseUtcMs(timestamp)))

const scrollEl = ref<HTMLElement | null>(null)
const isAtNewest = ref(true)
const hasNewEntries = ref(false)

const handleScroll = () => {
  const el = scrollEl.value
  if (!el) return
  isAtNewest.value = el.scrollHeight - el.scrollTop - el.clientHeight < 24
  if (isAtNewest.value) hasNewEntries.value = false
}

const scrollToNewest = () => {
  const el = scrollEl.value
  if (!el) return
  el.scrollTop = el.scrollHeight
  isAtNewest.value = true
  hasNewEntries.value = false
}

watch(
  () => props.entries.length,
  async () => {
    await nextTick()
    const el = scrollEl.value
    if (!el) return
    if (isAtNewest.value) el.scrollTop = el.scrollHeight
    else hasNewEntries.value = true
  },
  { immediate: true }
)
</script>

<template>
  <TooltipProvider :delay-duration="200">
    <div class="flex flex-col gap-1.5" :class="fill ? 'min-h-0 flex-1' : undefined">
      <div
        ref="scrollEl"
        class="overflow-y-auto border border-theme-primary/25 bg-surface-sunken/40 p-2"
        :class="fill ? 'min-h-0 flex-1' : 'max-h-56'"
        aria-live="polite"
        aria-label="Battle log"
        @scroll="handleScroll"
      >
        <ul v-if="groupedEntries.length" class="flex flex-col gap-1">
          <li
            v-for="entry in groupedEntries"
            :key="entry.id"
            class="flex items-start justify-between gap-2 rounded px-1.5 py-1 text-xs"
            :class="{
              'border-l-2 border-warning bg-warning/10 text-warning': entry.kind === 'SKILL',
              'text-muted-foreground': entry.kind === 'TURN',
              'text-info': entry.kind === 'REWARD',
              'text-theme-primary': entry.kind === 'FINISH',
              'text-terminal-green': !['SKILL', 'TURN', 'REWARD', 'FINISH'].includes(entry.kind),
            }"
          >
            <Tooltip v-if="entry.timestamp"
              ><TooltipTrigger as-child>
                <time
                  :datetime="entry.timestamp"
                  tabindex="0"
                  class="shrink-0 pt-0.5 text-[10px] tabular-nums text-muted-foreground"
                  >{{ eventTime(entry.timestamp) }}</time
                ></TooltipTrigger
              ><TooltipContent
                class="border border-theme-primary/40 bg-popover text-theme-primary"
                >{{ eventDate(entry.timestamp!) }}</TooltipContent
              ></Tooltip
            >
            <span class="flex min-w-0 flex-1 items-baseline gap-1.5">
              <CombatSkillIcon
                v-if="entry.kind === 'SKILL' && entry.skillIcon"
                :icon="entry.skillIcon"
                class="size-3.5 shrink-0 self-center"
              />
              <Zap
                v-else-if="entry.kind === 'SKILL'"
                class="size-3.5 shrink-0 self-center"
                aria-hidden="true"
              />
              <span
                class="shrink-0 rounded border border-current/30 px-1 text-[10px] font-bold tracking-wide"
              >
                {{ entry.kind }}
              </span>
              <span class="min-w-0 break-words">{{ entry.message }}</span>
              <span v-if="entry.meta" class="shrink-0 text-terminal-green-dim">{{
                entry.meta
              }}</span>
            </span>
            <span class="flex shrink-0 items-baseline gap-1.5">
              <span v-if="entry.delta" class="tabular-nums text-terminal-green-dim">
                {{ entry.delta }}
              </span>
              <span
                v-if="entry.count > 1"
                class="rounded border border-theme-primary/30 px-1 text-[10px] font-bold tabular-nums text-terminal-green-dim"
              >
                ×{{ entry.count }}
              </span>
            </span>
          </li>
        </ul>
        <p v-else class="text-xs text-terminal-green-dim">{{ emptyText }}</p>
      </div>

      <Button
        v-if="hasNewEntries"
        variant="link"
        class="battle-log-newest h-auto self-start px-0 text-xs underline"
        type="button"
        @click="scrollToNewest"
      >
        New events below
      </Button>
    </div>
  </TooltipProvider>
</template>

<style scoped>
.battle-log-newest {
  color: var(--color-terminal-green);
}
</style>
