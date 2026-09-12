<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getHealthDisplay } from '@/modules/dwellers/models/dweller'
import {
  orderedVisibleColumns,
  type DwellerTableColumnId,
} from '@/modules/dwellers/models/dwellerTable'
import type { Room } from '@/modules/rooms/models/room'
import USkeleton from '@/core/components/ui/USkeleton.vue'
import DwellerPortrait from '../DwellerPortrait.vue'
import DwellerStatusBadge from '../stats/DwellerStatusBadge.vue'
import DwellerAgeBadge from '../DwellerAgeBadge.vue'
import DwellerGenderBadge from '../DwellerGenderBadge.vue'
import DwellerRarityBadge from '../DwellerRarityBadge.vue'

interface Props {
  dwellers: DwellerShort[]
  rooms: Room[]
  columns: DwellerTableColumnId[]
  isLoading: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view-details', dwellerId: string): void
  (e: 'open-room', roomId: string): void
}>()

const visibleColumns = computed(() => orderedVisibleColumns(props.columns))
const roomsById = computed(() => new Map(props.rooms.map((room) => [room.id, room])))

const roomName = (roomId: string | null | undefined) =>
  roomId ? roomsById.value.get(roomId)?.name : undefined

const cellClass = (align?: 'left' | 'right') =>
  align === 'right'
    ? 'whitespace-nowrap px-3 py-2 text-right'
    : 'whitespace-nowrap px-3 py-2 text-left'

function activate(dwellerId: string) {
  emit('view-details', dwellerId)
}
</script>

<template>
  <div class="dweller-table-wrap">
    <table class="dweller-table">
      <thead>
        <tr>
          <th
            v-for="column in visibleColumns"
            :key="column.id"
            scope="col"
            :class="cellClass(column.align)"
          >
            <span class="inline-flex items-center gap-1.5">
              <Icon :icon="column.icon" class="h-4 w-4 opacity-70" />
              {{ column.label }}
            </span>
          </th>
        </tr>
      </thead>

      <tbody v-if="isLoading">
        <tr v-for="row in 5" :key="`skeleton-${row}`">
          <td v-for="column in visibleColumns" :key="column.id" class="px-3 py-2">
            <USkeleton height="1rem" />
          </td>
        </tr>
      </tbody>

      <tbody v-else-if="dwellers.length === 0">
        <tr>
          <td :colspan="visibleColumns.length" class="px-3 py-6 text-center opacity-60">
            No dwellers to show
          </td>
        </tr>
      </tbody>

      <tbody v-else>
        <tr
          v-for="dweller in dwellers"
          :key="dweller.id"
          class="dweller-table-row cursor-pointer"
          role="button"
          tabindex="0"
          @click="activate(dweller.id)"
          @keydown.enter.prevent="activate(dweller.id)"
          @keydown.space.prevent="activate(dweller.id)"
        >
          <td v-for="column in visibleColumns" :key="column.id" :class="cellClass(column.align)">
            <DwellerPortrait
              v-if="column.id === 'portrait'"
              :thumbnail-url="dweller.thumbnail_url"
              alt=""
              url-mode="static"
              fallback-icon="mdi:account-circle"
              image-class="h-9 w-9 rounded object-cover"
              fallback-class="h-9 w-9 text-theme-primary/60"
            />
            <span
              v-else-if="column.id === 'name'"
              class="block max-w-[18rem] truncate font-semibold text-terminal-green"
            >
              {{ dweller.first_name }} {{ dweller.last_name }}
            </span>
            <span v-else-if="column.id === 'level'">{{ dweller.level }}</span>
            <DwellerRarityBadge
              v-else-if="column.id === 'rarity'"
              :rarity="dweller.rarity"
              size="sm"
            />
            <DwellerGenderBadge
              v-else-if="column.id === 'gender'"
              :gender="dweller.gender"
              size="sm"
            />
            <DwellerAgeBadge v-else-if="column.id === 'age'" :age-group="dweller.age_group" size="sm" />
            <DwellerStatusBadge
              v-else-if="column.id === 'status'"
              :status="dweller.status"
              size="small"
              show-label
            />
            <span v-else-if="column.id === 'health'">{{
              getHealthDisplay(dweller.health, dweller.max_health, dweller.radiation)
            }}</span>
            <span v-else-if="column.id === 'happiness'">{{ dweller.happiness }}%</span>
            <button
              v-else-if="column.id === 'room' && roomName(dweller.room_id)"
              type="button"
              class="rounded px-1.5 py-0.5 text-left transition-colors hover:bg-surface-hover"
              @click.stop="emit('open-room', dweller.room_id!)"
            >
              {{ roomName(dweller.room_id) }}
            </button>
            <span v-else-if="column.id === 'room'" class="opacity-50">Unassigned</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.dweller-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  border-radius: 6px;
}

.dweller-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.dweller-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--color-surface-sunken);
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.dweller-table-row {
  border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 12%, transparent);
  transition: background 150ms ease;
}

.dweller-table-row:hover {
  background: var(--color-surface-hover);
}

.dweller-table-row:last-child {
  border-bottom: none;
}
</style>
