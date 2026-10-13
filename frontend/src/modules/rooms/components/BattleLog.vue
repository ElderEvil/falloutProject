<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Button } from '@/core/components/ui/button'
import type { BattleLogEntry } from '../models/battleLog'

const props = defineProps<{
  entries: BattleLogEntry[]
  emptyText: string
}>()

const groupedEntries = computed<Array<BattleLogEntry & { count: number }>>(() => {
  const grouped: Array<BattleLogEntry & { count: number }> = []
  for (const entry of props.entries) {
    const previous = grouped[grouped.length - 1]
    if (previous && previous.kind === entry.kind && previous.message === entry.message) {
      // Presentation-level collapse: consecutive identical lines read as one
      // round summary; the first entry anchors the row's delta and meta.
      previous.count += 1
    } else {
      grouped.push({ ...entry, count: 1 })
    }
  }
  return grouped
})

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
  () => groupedEntries.value.length,
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
  <div class="flex flex-col gap-1.5">
    <div
      ref="scrollEl"
      class="max-h-40 overflow-y-auto border border-theme-primary/25 bg-surface-sunken/40 p-2"
      aria-live="polite"
      aria-label="Battle log"
      @scroll="handleScroll"
    >
      <ul v-if="groupedEntries.length" class="flex flex-col gap-1">
        <li
          v-for="entry in groupedEntries"
          :key="entry.id"
          class="flex items-baseline justify-between gap-2 text-xs text-terminal-green"
        >
          <span class="flex min-w-0 items-baseline gap-1.5">
            <span class="shrink-0 rounded border border-theme-primary/30 px-1 text-[10px] font-bold tracking-wide text-terminal-green-dim">
              {{ entry.kind }}
            </span>
            <span class="min-w-0">{{ entry.message }}</span>
            <span v-if="entry.meta" class="shrink-0 text-terminal-green-dim">{{ entry.meta }}</span>
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
      New rounds below
    </Button>
  </div>
</template>

<style scoped>
.battle-log-newest {
  color: var(--color-terminal-green);
}
</style>
