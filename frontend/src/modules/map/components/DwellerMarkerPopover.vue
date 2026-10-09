<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerStatusBadge from '@/modules/dwellers/components/stats/DwellerStatusBadge.vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import type { ExplorerTrack } from '../models/map'

interface Props {
  track: ExplorerTrack
  x: number
  y: number
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  'view-details': []
}>()

// Fixed-size card; the anchor is the marker's screen point, offset so the card
// clears the glyph and clamped to keep it on-screen.
const POPOVER_WIDTH = 256
const ESTIMATED_HEIGHT = 250
const EDGE_MARGIN = 8
const ANCHOR_OFFSET = 14

const name = computed(() => props.track.dwellerName || 'Unknown Dweller')
const isReturning = computed(() => props.track.status === 'returning')
const taskLabel = computed(() => (isReturning.value ? 'Heading home' : 'Exploring the wasteland'))
// STATUS_CONFIG_MAP has no `returning` entry: keep the badge on the valid
// `exploring` status and carry "Heading home" on the task line instead.
const badgeStatus = computed<'exploring'>(() => 'exploring')
// Optional on the interface (frozen mockup fixture); real tracks build with nulls.
const health = computed(() => props.track.health ?? null)
const radiation = computed(() => props.track.radiation ?? null)

const position = computed(() => ({
  left: `${Math.max(
    EDGE_MARGIN,
    Math.min(props.x + ANCHOR_OFFSET, window.innerWidth - POPOVER_WIDTH - EDGE_MARGIN)
  )}px`,
  top: `${Math.max(
    EDGE_MARGIN,
    Math.min(props.y + ANCHOR_OFFSET, window.innerHeight - ESTIMATED_HEIGHT - EDGE_MARGIN)
  )}px`,
}))

const cardRef = ref<HTMLElement | null>(null)

function onPointerDown(event: PointerEvent) {
  const card = cardRef.value
  if (card && event.target instanceof Node && card.contains(event.target)) return
  emit('close')
}

onMounted(() => {
  cardRef.value?.focus()
  document.addEventListener('pointerdown', onPointerDown)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onPointerDown)
})
</script>

<template>
  <Teleport to="body">
    <div
      ref="cardRef"
      role="dialog"
      aria-label="Explorer details"
      tabindex="-1"
      class="fixed z-50 w-64 border border-theme-primary bg-surface p-3 font-mono text-theme-primary shadow-glow-md outline-none"
      :style="position"
      @keydown.esc="emit('close')"
    >
      <div class="flex items-start gap-3">
        <DwellerPortrait
          :thumbnail-url="track.dwellerThumbnailUrl ?? null"
          prefer-thumbnail
          :alt="`${name} portrait`"
          fallback-icon="mdi:account"
          image-class="h-12 w-12 shrink-0 rounded-full border border-theme-primary object-cover object-top"
          fallback-class="block h-12 w-12 shrink-0"
        />
        <div class="min-w-0">
          <p class="truncate text-sm font-bold">{{ name }}</p>
          <DwellerStatusBadge :status="badgeStatus" :show-label="true" size="small" class="mt-1" />
        </div>
      </div>

      <div class="mt-3 space-y-3">
        <div>
          <div
            class="flex items-baseline justify-between text-[10px] tracking-wider uppercase text-theme-primary/60"
          >
            <span>HP</span>
            <span v-if="health !== null">{{ health }} / 100</span>
            <span v-else class="text-theme-primary/40">—</span>
          </div>
          <!-- @vue-ignore -->
          <Progress
            v-if="health !== null"
            :model-value="health"
            size="xs"
            tone="success"
            label="Hit points"
            :value-text="`${health} / 100`"
            class="mt-1"
          />
        </div>
        <div>
          <div
            class="flex items-baseline justify-between text-[10px] tracking-wider uppercase text-theme-primary/60"
          >
            <span>Radiation</span>
            <span v-if="radiation !== null">{{ radiation }} / 100</span>
            <span v-else class="text-theme-primary/40">—</span>
          </div>
          <!-- @vue-ignore -->
          <Progress
            v-if="radiation !== null"
            :model-value="radiation"
            size="xs"
            tone="warning"
            label="Radiation"
            :value-text="`${radiation} / 100`"
            class="mt-1"
          />
        </div>
      </div>

      <p class="mt-3 text-xs text-theme-primary/70">
        Current task:
        <span class="text-theme-primary">{{ taskLabel }}</span>
      </p>

      <Button size="sm" class="mt-3 w-full" @click="emit('view-details')">View details</Button>
    </div>
  </Teleport>
</template>
