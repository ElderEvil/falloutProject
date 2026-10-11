<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'

const states = [
  { label: 'Locked', icon: 'mdi:lock-question' },
  { label: 'Cleared', icon: 'mdi:check' },
  { label: 'Cooldown', icon: 'mdi:clock-outline' },
  { label: 'Exploring', icon: 'mdi:circle-double' },
]

// The legend overlays the map pane, so it stays collapsed on first view and
// remembers its state: a revealed area under it is otherwise invisible.
const LEGEND_COLLAPSED_KEY = 'map:legend-collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(LEGEND_COLLAPSED_KEY) !== 'false'
  } catch {
    return true
  }
}

const collapsed = ref(readCollapsed())

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  try {
    localStorage.setItem(LEGEND_COLLAPSED_KEY, String(collapsed.value))
  } catch {
    // Storage unavailable (private mode, blocked cookies): the visible
    // state still toggles, it just won't persist.
  }
}
</script>

<template>
  <div
    class="map-legend absolute bottom-2 left-2 z-10 max-w-[calc(100%-1rem)] rounded-sm border border-theme-primary/40 bg-surface/95 px-2 py-1 font-mono text-xs text-theme-primary"
    role="complementary"
    aria-label="Map legend"
  >
    <Button
      variant="ghost"
      size="xs"
      class="legend-toggle h-auto gap-2 p-0 text-xs"
      :aria-expanded="!collapsed"
      @click="toggleCollapsed"
    >
      <span>MAP KEY</span>
      <Icon :icon="collapsed ? 'mdi:chevron-up' : 'mdi:chevron-down'" class="size-3" />
    </Button>
    <div
      v-if="!collapsed"
      class="legend-content mt-1 flex flex-wrap gap-x-3 gap-y-1"
      @wheel.stop
      @touchmove.stop
    >
      <span
        v-for="state in states"
        :key="state.label"
        class="legend-item flex items-center gap-1 whitespace-nowrap"
      >
        <Icon :icon="state.icon" class="size-3.5" :ariaHidden="true" />
        {{ state.label }}
      </span>
    </div>
  </div>
</template>
