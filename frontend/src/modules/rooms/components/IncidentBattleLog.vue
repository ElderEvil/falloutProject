<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { Incident } from '@/modules/combat/models/incident'

const props = defineProps<{ events: Incident['events'] }>()

const scrollEl = ref<HTMLElement | null>(null)
const isAtNewest = ref(true)
const hasNewEntries = ref(false)

const entries = computed(() =>
  props.events.map((event) => {
    const damageToThreat = Number(event.data?.damage_to_threat ?? 0)
    const damageToDwellers = Number(event.data?.damage_to_dwellers ?? 0)
    const containment = Number(event.data?.amount ?? 0)
    const delta =
      damageToThreat > 0
        ? `-${damageToThreat} threat`
        : damageToDwellers > 0
          ? `-${damageToDwellers} dwellers`
          : containment > 0
            ? `+${Math.round(containment * 100)}% contained`
            : null
    return { id: event.id, message: event.message, delta }
  })
)

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
  }
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
          <span>{{ entry.message }}</span>
          <span v-if="entry.delta" class="shrink-0 tabular-nums text-terminal-green-dim">
            {{ entry.delta }}
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
