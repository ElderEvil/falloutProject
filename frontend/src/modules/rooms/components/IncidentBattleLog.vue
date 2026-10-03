<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Incident } from '@/modules/combat/models/incident'

const props = defineProps<{ events: Incident['events'] }>()

const scrollEl = ref<HTMLElement | null>(null)
const isAtNewest = ref(true)
const hasNewEntries = ref(false)

const KIND_LABELS: Record<string, string> = {
  spawned: 'ALERT',
  spread: 'SPREAD',
  responders_assigned: 'RESPONDERS',
  responders_dispatched: 'DISPATCHED',
  round: 'ROUND',
  containment: 'CONTAINMENT',
  resolved: 'RESOLVED',
  failed: 'FAILED',
  overflow: 'LOOT',
}

const kindLabel = (kind: string): string =>
  KIND_LABELS[kind] ?? kind.replace(/_/g, ' ').toUpperCase()

interface LogEntry {
  id: string
  kind: string
  message: string
  delta: string | null
  count: number
  skipped: string[]
}

const skippedNames = (data: Incident['events'][number]['data']): string[] => {
  const skipped = data?.skipped
  return Array.isArray(skipped) ? skipped.filter((name): name is string => typeof name === 'string') : []
}

const entries = computed<LogEntry[]>(() => {
  const grouped: LogEntry[] = []
  for (const event of props.events) {
    // Truncated to match the round summary the backend writes, so a line never
    // reads "dealt 4 damage" next to a fractional threat delta.
    const damageToThreat = Math.trunc(Number(event.data?.damage_to_threat ?? 0))
    const damageToDwellers = Math.trunc(Number(event.data?.damage_to_dwellers ?? 0))
    const containment = Number(event.data?.amount ?? 0)
    const delta =
      damageToThreat > 0
        ? `-${damageToThreat} threat`
        : damageToDwellers > 0
          ? `-${damageToDwellers} dwellers`
          : containment > 0
            ? `+${Math.round(containment * 100)}% contained`
            : null
    const kind = kindLabel(event.kind)
    const previous = grouped[grouped.length - 1]
    if (previous && previous.kind === kind && previous.message === event.message) {
      // Presentation-level collapse: consecutive identical lines read as one
      // round summary; the first entry anchors the row's delta and skipped list.
      previous.count += 1
    } else {
      grouped.push({
        id: event.id,
        kind,
        message: event.message,
        delta,
        count: 1,
        skipped: skippedNames(event.data),
      })
    }
  }
  return grouped
})

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
  () => entries.value.length,
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
  <section class="flex flex-col gap-1.5">
    <p class="text-xs text-terminal-green-dim">BATTLE LOG</p>

    <div
      ref="scrollEl"
      class="max-h-40 overflow-y-auto border border-theme-primary/25 bg-surface-sunken/40 p-2"
      aria-live="polite"
      aria-label="Battle log"
      @scroll="handleScroll"
    >
      <ul v-if="entries.length" class="flex flex-col gap-1">
        <li
          v-for="entry in entries"
          :key="entry.id"
          class="flex items-baseline justify-between gap-2 text-xs text-terminal-green"
        >
          <span class="flex min-w-0 items-baseline gap-1.5">
            <span class="shrink-0 rounded border border-theme-primary/30 px-1 text-[10px] font-bold tracking-wide text-terminal-green-dim">
              {{ entry.kind }}
            </span>
            <span class="min-w-0">{{ entry.message }}</span>
            <span v-if="entry.skipped.length" class="shrink-0 text-terminal-green-dim">
              Unavailable: {{ entry.skipped.join(', ') }}
            </span>
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
      <p v-else class="text-xs text-terminal-green-dim">No rounds fought yet.</p>
    </div>

    <button
      v-if="hasNewEntries"
      type="button"
      class="self-start text-xs text-terminal-green underline"
      @click="scrollToNewest"
    >
      New rounds below
    </button>
  </section>
</template>
