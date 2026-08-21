<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { getEventIcon, getEventColor } from '../models/exploration'
import type { ExplorationEvent } from '../stores/exploration'

interface Props {
  events: ExplorationEvent[]
  reverse?: boolean
  showLoot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  reverse: false,
  showLoot: true,
})

const orderedEvents = computed(() => {
  if (!props.reverse) return props.events
  return [...props.events].reverse()
})

const formatEventTime = (hours: number): string => {
  const h = Math.floor(hours)
  const m = Math.floor((hours - h) * 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

const hasLoot = (event: ExplorationEvent): boolean => {
  return !!event.loot && (!!event.loot.item || !!event.loot.caps)
}

const getLootDisplay = (event: ExplorationEvent): string => {
  if (!event.loot) return ''
  const parts: string[] = []

  if (event.loot.item) {
    parts.push(`${event.loot.item.name} (${event.loot.item.rarity})`)
  }
  if (event.loot.caps) {
    parts.push(`${event.loot.caps} caps`)
  }

  return parts.join(' + ')
}
</script>

<template>
  <div
    class="mb-4 rounded-lg border-2 border-theme-primary bg-terminal-background p-4 shadow-[0_0_20px_var(--color-theme-glow)]"
  >
    <h3
      class="section-title mb-2 flex items-center text-base font-bold text-theme-primary [text-shadow:0_0_8px_var(--color-theme-glow)]"
    >
      <Icon icon="mdi:timeline-text" class="mr-2" />
      Event Log
    </h3>
    <div
      class="max-h-[250px] overflow-y-auto rounded-md border border-theme-primary/30 bg-terminal-background p-4"
    >
      <div
        v-if="orderedEvents.length === 0"
        class="no-events flex flex-col items-center gap-2 p-8 text-theme-primary/50"
      >
        <Icon icon="mdi:clock-outline" class="h-10 w-10" />
        <p>No events yet. Adventure is just beginning...</p>
      </div>
      <div v-else class="event-list flex flex-col gap-2">
        <div
          v-for="(event, index) in orderedEvents"
          :key="`${event.timestamp}-${event.type}-${event.description}-${index}`"
          class="event-row grid grid-cols-[55px_28px_1fr] items-start gap-2 rounded border-l-[3px] bg-terminal-background p-2.5 transition-all duration-200 hover:translate-x-[3px] hover:bg-theme-primary/10 hover:shadow-[0_0_12px_rgba(var(--color-theme-primary-rgb),0.2)] md:grid-cols-[60px_30px_1fr] md:p-3"
          :style="{
            borderLeftColor: getEventColor(event.type),
          }"
        >
          <span
            class="event-time pt-0.5 text-sm font-bold tabular-nums text-theme-primary [text-shadow:0_0_5px_var(--color-theme-glow)]"
            >{{ formatEventTime(event.time_elapsed_hours) }}</span
          >
          <Icon
            :icon="getEventIcon(event.type)"
            class="mt-0.5 h-5 w-5 drop-shadow-[0_0_3px_currentColor]"
            :style="{ color: getEventColor(event.type) }"
          />
          <div class="flex flex-col gap-1.5">
            <div class="flex items-center gap-1.5">
              <span
                class="event-type-badge inline-block rounded-[3px] border px-1.5 py-0.5 text-[0.5625rem] font-bold tracking-[0.03em] [text-shadow:0_0_5px_currentColor]"
                :style="{
                  backgroundColor: getEventColor(event.type) + '20',
                  borderColor: getEventColor(event.type),
                  color: getEventColor(event.type),
                }"
              >
                {{ event.type.toUpperCase() }}
              </span>
            </div>
            <span class="text-[0.8125rem] leading-[1.4] text-theme-primary/90">{{
              event.description
            }}</span>
            <div
              v-if="showLoot && hasLoot(event)"
              class="loot-line inline-flex items-center gap-1 self-start rounded-[3px] border border-rarity-legendary/30 bg-rarity-legendary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-rarity-legendary"
            >
              <Icon icon="mdi:treasure-chest" class="h-3.5 w-3.5" />
              {{ getLootDisplay(event) }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
