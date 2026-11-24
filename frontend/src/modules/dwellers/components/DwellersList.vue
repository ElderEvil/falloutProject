<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, toRef, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import {
  getCombatPower,
  getAbilityConfig,
  getHealthDisplay,
} from '@/modules/dwellers/models/dweller'
import {
  DEFAULT_TABLE_COLUMNS,
  type DwellerTableColumnId,
} from '@/modules/dwellers/models/dwellerTable'
import type { DwellerViewMode } from '@/modules/dwellers/stores/dwellerFilter'
import type { Room } from '@/modules/rooms/models/room'
import DwellerPortrait from './DwellerPortrait.vue'
import DwellerStatusBadge from './stats/DwellerStatusBadge.vue'
import DwellerAgeBadge from './DwellerAgeBadge.vue'
import DwellerGenderBadge from './DwellerGenderBadge.vue'
import DwellerRarityBadge from './DwellerRarityBadge.vue'
import DwellerGridItem from './grid/DwellerGridItem.vue'
import DwellerCardSkeleton from './cards/DwellerCardSkeleton.vue'
import DwellerGridItemSkeleton from './grid/DwellerGridItemSkeleton.vue'
import DwellerListRow from './DwellerListRow.vue'
import DwellersTable from './table/DwellersTable.vue'
import TerminalEmptyState from '@/core/components/common/TerminalEmptyState.vue'
import { Button } from '@/core/components/ui/button'
import { useRoomLookup } from '../composables/useRoomLookup'

interface Props {
  dwellers: DwellerShort[]
  isLoading: boolean
  rooms: Room[]
  viewMode: DwellerViewMode
  columns?: DwellerTableColumnId[]
  /** True when at least one roster facet is narrowing the list. */
  hasActiveFilters?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  columns: () => DEFAULT_TABLE_COLUMNS,
  hasActiveFilters: false,
})

const emit = defineEmits<{
  (e: 'view-details', dwellerId: string): void
  (e: 'open-room', roomId: string): void
  (e: 'quick-unassign', dwellerId: string): void
  (e: 'room-click', roomId: string): void
  (e: 'clear-filters'): void
}>()

const PAGE_SIZE = 20
const visibleCount = ref(PAGE_SIZE)
const visibleDwellers = computed(() => props.dwellers.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < props.dwellers.length)

// Reset only when the roster itself is replaced (a new filter/sort/query rebuilds
// the array) or grows/shrinks. A single dweller's field update arrives in place —
// same array instance, same length — so it leaves the reader's scroll depth alone.
// A deep watch would reset on every stat tick, which is exactly the bug this avoids.
watch([() => props.dwellers, () => props.dwellers.length], () => {
  visibleCount.value = PAGE_SIZE
})

const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

/** Nearest ancestor that scrolls vertically — the roster is nested in page shells, not window. */
const scrollingAncestor = (el: HTMLElement): HTMLElement | null => {
  for (let node = el.parentElement; node; node = node.parentElement) {
    const overflowY = getComputedStyle(node).overflowY
    if (overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') return node
  }
  return null
}

const loadMore = () => {
  if (!hasMore.value) return
  visibleCount.value = Math.min(visibleCount.value + PAGE_SIZE, props.dwellers.length)
}

const observeSentinel = (el: HTMLElement | null) => {
  observer?.disconnect()
  observer = null
  if (!el || typeof IntersectionObserver === 'undefined') return
  observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting) || !hasMore.value) return
      loadMore()
      // The observer fires on intersection *changes* only: re-attach after the
      // appended rows move the sentinel so a tall viewport keeps filling.
      void nextTick(() => {
        if (!observer || !sentinel.value) return
        observer.unobserve(sentinel.value)
        observer.observe(sentinel.value)
      })
    },
    { root: scrollingAncestor(el), rootMargin: '200px' }
  )
  observer.observe(el)
}

watch(sentinel, observeSentinel, { flush: 'post' })
onBeforeUnmount(() => observer?.disconnect())

/** The empty state outranks the view-mode branches: without rows there is nothing to lay out. */
const showEmptyState = computed(() => !props.isLoading && props.dwellers.length === 0)

const emptyState = computed(() => {
  if (props.hasActiveFilters) {
    return {
      icon: 'mdi:filter-remove-outline',
      title: 'No dwellers match these filters',
      description: 'Adjust or clear the filters to bring the roster back.',
    }
  }
  return {
    icon: 'mdi:account-plus-outline',
    title: 'No dwellers yet',
    description: 'Dwellers will show up here as soon as they arrive in the vault.',
  }
})

const { roomFor } = useRoomLookup(toRef(props, 'rooms'))

// Show a dweller's room-relevant stat (the ability their room needs). Arena
// rooms have no stat — show combat power instead.
const getRoomStat = (
  dweller: DwellerShort
): { icon: string; label: string; value: number; isPower: boolean } | null => {
  const room = roomFor(dweller.room_id)
  if (!room) return null
  if (room.category === 'arena') {
    return {
      icon: 'mdi:sword-cross',
      label: 'Power',
      value: getCombatPower(dweller),
      isPower: true,
    }
  }
  const ability = getAbilityConfig(room.ability)
  if (!ability) return null
  const value = dweller[(room.ability ?? '').toLowerCase() as SpecialKey] ?? 0
  return { icon: ability.icon, label: ability.label, value, isPower: false }
}
</script>

<template>
  <TerminalEmptyState
    v-if="showEmptyState"
    :icon="emptyState.icon"
    :title="emptyState.title"
    :description="emptyState.description"
  >
    <template v-if="hasActiveFilters" #actions>
      <Button
        variant="outline"
        size="sm"
        class="border-2 border-theme-primary bg-transparent hover:shadow-glow-md"
        @click="emit('clear-filters')"
      >
        <Icon icon="mdi:filter-remove-outline" class="mr-2 h-4 w-4" />
        Clear filters
      </Button>
    </template>
  </TerminalEmptyState>

  <ul v-else-if="viewMode === 'list'" class="w-full space-y-4">
    <template v-if="isLoading">
      <DwellerCardSkeleton v-for="i in 3" :key="`skeleton-${i}`" />
    </template>

    <DwellerListRow
      v-for="dweller in visibleDwellers"
      v-else
      :key="dweller.id"
      :dweller="dweller"
      @activate="emit('view-details', dweller.id)"
    >
      <template #middle>
        <div class="h-10 w-px flex-shrink-0 bg-theme-primary/20"></div>
        <div class="flex-shrink-0">
          <DwellerStatusBadge :status="dweller.status" :show-label="true" size="small" />
        </div>
        <div class="h-10 w-px flex-shrink-0 bg-theme-primary/20"></div>

        <div class="flex items-center gap-4">
          <div class="flex items-center gap-1.5">
            <Icon icon="mdi:heart" class="h-4 w-4 text-danger" />
            <span class="text-sm font-semibold">{{
              getHealthDisplay(dweller.health, dweller.max_health, dweller.radiation)
            }}</span>
          </div>
          <div class="flex items-center gap-1">
            <Icon icon="mdi:emoticon-happy" class="h-4 w-4 text-warning" />
            <span class="text-sm font-semibold">{{ dweller.happiness }}%</span>
          </div>
        </div>

        <template v-if="getRoomStat(dweller)">
          <div class="h-10 w-px flex-shrink-0 bg-theme-primary/20"></div>
          <div class="flex items-center gap-1.5">
            <Icon
              :icon="getRoomStat(dweller)!.icon"
              :class="getRoomStat(dweller)!.isPower ? 'text-warning' : 'text-theme-primary/60'"
              class="h-4 w-4"
            />
            <span class="text-sm font-semibold">
              {{ getRoomStat(dweller)!.label }}: {{ getRoomStat(dweller)!.value }}
            </span>
          </div>
        </template>
      </template>

      <template #actions>
        <div
          v-if="roomFor(dweller.room_id)"
          class="flex cursor-pointer items-center gap-2 rounded border border-theme-primary/30 bg-surface-raised px-3 py-1.5 text-sm font-medium text-theme-primary/80 transition-all hover:bg-surface-hover"
          role="button"
          tabindex="0"
          @click.stop="emit('open-room', dweller.room_id!)"
          @keydown.enter.prevent.stop="emit('open-room', dweller.room_id!)"
          @keydown.space.prevent.stop="emit('open-room', dweller.room_id!)"
        >
          {{ roomFor(dweller.room_id)?.name }}
          <button
            class="ml-auto rounded p-0.5 transition-colors hover:bg-danger/20"
            aria-label="Unassign from room"
            title="Unassign from room"
            @click.stop="emit('quick-unassign', dweller.id)"
          >
            <Icon icon="mdi:close" class="h-4 w-4 text-danger" />
          </button>
        </div>
        <Icon icon="mdi:chevron-right" class="h-5 w-5 flex-shrink-0 text-terminal-green/50" />
      </template>
    </DwellerListRow>
  </ul>

  <div v-else-if="viewMode === 'grid'" class="w-full dweller-grid">
    <template v-if="isLoading">
      <DwellerGridItemSkeleton v-for="i in 6" :key="`grid-skeleton-${i}`" />
    </template>
    <DwellerGridItem
      v-for="dweller in visibleDwellers"
      v-else
      :key="dweller.id"
      :dweller="dweller"
      :room-name="roomFor(dweller.room_id)?.name"
      :room-stat="getRoomStat(dweller)"
      @click="emit('view-details', dweller.id)"
      @room-click="dweller.room_id && emit('room-click', dweller.room_id)"
    />
  </div>

  <DwellersTable
    v-else
    :dwellers="visibleDwellers"
    :rooms="rooms"
    :columns="columns"
    :is-loading="isLoading"
    @view-details="emit('view-details', $event)"
    @open-room="emit('open-room', $event)"
  />
  <!-- Progress + keyboard "load more" affordance; the sentinel below auto-advances for
       pointer scrolling. The count is deliberately not a live region: it changes on every
       append and would announce continuously. -->
  <div
    v-if="!isLoading && dwellers.length > 0"
    class="mt-4 flex flex-col items-center gap-3 text-sm text-theme-primary/70"
  >
    <p class="dweller-progress">Showing {{ visibleDwellers.length }} of {{ dwellers.length }}</p>
    <template v-if="hasMore">
      <Button variant="outline" size="sm" @click="loadMore">
        Show {{ Math.min(PAGE_SIZE, dwellers.length - visibleCount) }} more
      </Button>
      <div ref="sentinel" class="dweller-sentinel h-px w-full" aria-hidden="true" />
    </template>
  </div>
</template>

<style scoped>
.dweller-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  width: 100%;
}
@media (max-width: 640px) {
  .dweller-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
  }
}
@media (max-width: 480px) {
  .dweller-grid {
    grid-template-columns: 1fr;
  }
}
@media (min-width: 1536px) {
  .dweller-grid {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}
</style>
