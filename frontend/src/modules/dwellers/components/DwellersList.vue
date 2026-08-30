<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import { getCombatPower, getAbilityConfig } from '@/modules/dwellers/models/dweller'
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

interface Props {
  dwellers: DwellerShort[]
  generatingAI: Record<string, boolean>
  isLoading: boolean
  rooms: Room[]
  viewMode: 'list' | 'grid'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view-details', dwellerId: string): void
  (e: 'generate-ai', dwellerId: string): void
  (e: 'open-room', roomId: string): void
  (e: 'quick-unassign', dwellerId: string): void
  (e: 'room-click', roomId: string): void
}>()

const roomsById = computed(() => new Map(props.rooms.map((room) => [room.id, room])))

const getRoomForDweller = (roomId: string | null | undefined) =>
  roomId ? roomsById.value.get(roomId) : undefined

// Show a dweller's room-relevant stat (the ability their room needs). Arena
// rooms have no stat — show combat power instead.
const getRoomStat = (
  dweller: DwellerShort
): { icon: string; label: string; value: number; isPower: boolean } | null => {
  const room = getRoomForDweller(dweller.room_id)
  if (!room) return null
  if (room.category === 'arena') {
    return { icon: 'mdi:sword-cross', label: 'Power', value: getCombatPower(dweller), isPower: true }
  }
  const ability = getAbilityConfig(room.ability)
  if (!ability) return null
  const value = dweller[(room.ability ?? '').toLowerCase() as SpecialKey] ?? 0
  return { icon: ability.icon, label: ability.label, value, isPower: false }
}
</script>

<template>
  <ul v-if="viewMode === 'list'" class="w-full space-y-4">
    <template v-if="isLoading">
      <DwellerCardSkeleton v-for="i in 3" :key="`skeleton-${i}`" />
    </template>

    <DwellerListRow
      v-for="dweller in dwellers"
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
            <Icon icon="mdi:heart" class="h-4 w-4 text-red-400" />
            <span class="text-sm font-semibold">{{ dweller.health }} / {{ dweller.max_health }}</span>
          </div>
          <div class="flex items-center gap-1">
            <Icon icon="mdi:emoticon-happy" class="h-4 w-4 text-yellow-400" />
            <span class="text-sm font-semibold">{{ dweller.happiness }}%</span>
          </div>
        </div>

        <template v-if="getRoomStat(dweller)">
          <div class="h-10 w-px flex-shrink-0 bg-theme-primary/20"></div>
          <div class="flex items-center gap-1.5">
            <Icon
              :icon="getRoomStat(dweller)!.icon"
              :class="getRoomStat(dweller)!.isPower ? 'text-orange-400' : 'text-theme-primary/60'"
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
          v-if="getRoomForDweller(dweller.room_id)"
          class="flex cursor-pointer items-center gap-2 rounded border border-theme-primary/30 bg-surface-raised px-3 py-1.5 text-sm font-medium text-theme-primary/80 transition-all hover:bg-surface-hover"
          role="button"
          tabindex="0"
          @click.stop="emit('open-room', dweller.room_id!)"
          @keydown.enter.prevent.stop="emit('open-room', dweller.room_id!)"
          @keydown.space.prevent.stop="emit('open-room', dweller.room_id!)"
        >
          {{ getRoomForDweller(dweller.room_id)?.name }}
          <button
            class="ml-auto rounded p-0.5 transition-colors hover:bg-red-500/20"
            aria-label="Unassign from room"
            title="Unassign from room"
            @click.stop="emit('quick-unassign', dweller.id)"
          >
            <Icon icon="mdi:close" class="h-4 w-4 text-red-400" />
          </button>
        </div>
        <Icon icon="mdi:chevron-right" class="h-5 w-5 flex-shrink-0 text-terminal-green/50" />
      </template>
    </DwellerListRow>
  </ul>

  <div v-else class="w-full dweller-grid">
    <template v-if="isLoading">
      <DwellerGridItemSkeleton v-for="i in 6" :key="`grid-skeleton-${i}`" />
    </template>
    <DwellerGridItem
      v-for="dweller in dwellers"
      v-else
      :key="dweller.id"
      :dweller="dweller"
      :room-name="getRoomForDweller(dweller.room_id)?.name"
      :room-stat="getRoomStat(dweller)"
      :generating-a-i="generatingAI[dweller.id]"
      @click="emit('view-details', dweller.id)"
      @generate-ai="emit('generate-ai', dweller.id)"
      @room-click="dweller.room_id && emit('room-click', dweller.room_id)"
    />
  </div>
</template>

<style scoped>
.dweller-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; width: 100%; }
@media (max-width: 640px) { .dweller-grid { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; } }
@media (max-width: 480px) { .dweller-grid { grid-template-columns: 1fr; } }
@media (min-width: 1536px) { .dweller-grid { grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); } }
</style>
