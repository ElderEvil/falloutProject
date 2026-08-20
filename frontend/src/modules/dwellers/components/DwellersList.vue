<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { getStaticImageUrl } from '@/core/utils/image'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import type { Room } from '@/modules/rooms/models/room'
import DwellerStatusBadge from './stats/DwellerStatusBadge.vue'
import DwellerGridItem from './grid/DwellerGridItem.vue'
import DwellerCardSkeleton from './cards/DwellerCardSkeleton.vue'
import DwellerGridItemSkeleton from './grid/DwellerGridItemSkeleton.vue'

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

const getImageUrl = (imagePath: string | null | undefined) => getStaticImageUrl(imagePath) ?? ''

const getRelevantStatForRoom = (
  dweller: DwellerShort,
  room: Room | null | undefined
) => {
  if (!room?.ability) return null

  const abilityMap: Record<string, { value: number; label: string; icon: string; color: string }> = {
    strength: { value: dweller.strength, label: 'STR', icon: 'mdi:arm-flex', color: 'text-red-400' },
    perception: { value: dweller.perception, label: 'PER', icon: 'mdi:eye', color: 'text-blue-400' },
    endurance: { value: dweller.endurance, label: 'END', icon: 'mdi:shield', color: 'text-orange-400' },
    charisma: { value: dweller.charisma, label: 'CHA', icon: 'mdi:account-voice', color: 'text-pink-400' },
    intelligence: { value: dweller.intelligence, label: 'INT', icon: 'mdi:brain', color: 'text-purple-400' },
    agility: { value: dweller.agility, label: 'AGI', icon: 'mdi:run-fast', color: 'text-cyan-400' },
    luck: { value: dweller.luck, label: 'LCK', icon: 'mdi:clover', color: 'text-green-400' },
  }

  return abilityMap[room.ability.toLowerCase()] ?? null
}

const getStatColorClass = (value: number) => {
  if (value >= 7) return 'text-green-400'
  if (value >= 4) return 'text-yellow-400'
  return 'text-red-400'
}
</script>

<template>
  <ul v-if="viewMode === 'list'" class="w-full space-y-4">
    <template v-if="isLoading">
      <DwellerCardSkeleton v-for="i in 3" :key="`skeleton-${i}`" />
    </template>

    <li
      v-for="dweller in dwellers"
      v-else
      :key="dweller.id"
      class="flex cursor-pointer items-center gap-3 rounded border border-gray-700 bg-surface-warm-dark p-3 transition-all hover:bg-surface-warm-hover"
      role="button"
      tabindex="0"
      @click="emit('view-details', dweller.id)"
      @keydown.enter.prevent="emit('view-details', dweller.id)"
      @keydown.space.prevent="emit('view-details', dweller.id)"
    >
      <div class="flex-shrink-0">
        <img
          v-if="dweller.thumbnail_url"
          :src="getImageUrl(dweller.thumbnail_url)"
          alt="Dweller Thumbnail"
          class="h-16 w-16 rounded object-cover"
        />
        <Icon
          v-else
          icon="mdi:account-circle"
          class="h-16 w-16"
          :style="{ color: 'var(--color-theme-primary)', opacity: 0.6 }"
        />
      </div>

      <div class="dweller-identity flex w-44 min-w-0 flex-col">
        <h3 class="truncate text-base font-bold text-terminal-green">
          {{ dweller.first_name }} {{ dweller.last_name }}
        </h3>
        <p class="text-sm text-gray-400">Level {{ dweller.level }}</p>
      </div>

      <div class="h-10 w-px flex-shrink-0 bg-gray-600/50"></div>
      <div class="flex-shrink-0">
        <DwellerStatusBadge :status="dweller.status" :show-label="true" size="small" />
      </div>
      <div class="h-10 w-px flex-shrink-0 bg-gray-600/50"></div>

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

      <template v-if="getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))">
        <div class="h-10 w-px flex-shrink-0 bg-gray-600/50"></div>
        <div class="flex items-center gap-1.5">
          <span class="text-sm text-gray-400">Job Stat:</span>
          <div class="flex items-center gap-1.5">
            <Icon
              :icon="getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.icon"
              :class="getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.color"
              class="h-4 w-4"
            />
            <span class="text-sm">{{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.label }}</span>
            <span
              :class="getStatColorClass(getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.value)"
              class="text-sm font-bold"
            >
              {{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.value }}
            </span>
          </div>
        </div>
      </template>

      <div class="ml-auto flex items-center gap-2">
        <div
          v-if="getRoomForDweller(dweller.room_id)"
          class="flex items-center gap-2 rounded border border-gray-600 bg-gray-700/80 px-3 py-1.5 text-sm font-medium text-gray-200 transition-all hover:bg-gray-700 cursor-pointer"
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
      </div>
    </li>
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
      :room-ability="getRoomForDweller(dweller.room_id)?.ability"
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
