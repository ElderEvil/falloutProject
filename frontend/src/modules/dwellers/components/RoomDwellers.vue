<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerStore } from '../stores/dweller'
import type { DwellerShort } from '../models/dweller'
import {
  getAbilityConfig,
  getDwellerDisplayName,
  isApprentice,
  orderRoomDwellers,
} from '../models/dweller'
import DwellerPortrait from './DwellerPortrait.vue'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/core/components/ui/tooltip'

interface Props {
  roomId: string
}

const props = defineProps<Props>()
const { filter: dwellerStore } = useDwellerStore()

const emit = defineEmits<{
  dragStart: [dweller: DwellerShort]
  dragEnd: []
}>()

// Get dwellers assigned to this room
const roomDwellers = computed(() =>
  orderRoomDwellers(dwellerStore.dwellers.filter((dweller) => dweller.room_id === props.roomId))
)

const apprenticeLabel = (dweller: DwellerShort): string =>
  getAbilityConfig(dweller.apprentice_stat)?.label ?? dweller.apprentice_stat ?? ''

const handleDragStart = (event: DragEvent, dweller: DwellerShort) => {
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData(
      'application/json',
      JSON.stringify({
        dwellerId: dweller.id,
        firstName: dweller.first_name,
        lastName: dweller.last_name,
        currentRoomId: props.roomId,
      })
    )
  }
  emit('dragStart', dweller)
}

const handleDragEnd = () => {
  emit('dragEnd')
}
</script>

<template>
  <div v-if="roomDwellers.length > 0" class="room-dwellers">
    <Tooltip v-for="dweller in roomDwellers" :key="dweller.id">
      <TooltipTrigger as-child>
        <div
          class="dweller-avatar"
          :class="{ 'dweller-avatar--apprentice': isApprentice(dweller) }"
          draggable="true"
          tabindex="0"
          @dragstart="handleDragStart($event, dweller)"
          @dragend="handleDragEnd"
          :aria-label="`${getDwellerDisplayName(dweller)} (Lv${dweller.level})${
            isApprentice(dweller) ? `, apprentice in ${apprenticeLabel(dweller)}` : ''
          }`"
        >
          <DwellerPortrait
            :thumbnail-url="dweller.thumbnail_url"
            :alt="getDwellerDisplayName(dweller)"
            image-class="avatar-image"
            fallback-class="h-10 w-10 icon-primary"
          />
          <div class="dweller-level">{{ dweller.level }}</div>
          <span v-if="isApprentice(dweller)" class="apprentice-badge" aria-hidden="true">
            <Icon icon="mdi:school-outline" />
          </span>
        </div>
      </TooltipTrigger>
      <TooltipContent>
        {{ getDwellerDisplayName(dweller) }} (Lv{{ dweller.level }})
        <template v-if="isApprentice(dweller)">
          · Apprentice {{ apprenticeLabel(dweller) }}
        </template>
      </TooltipContent>
    </Tooltip>
  </div>
</template>

<style scoped>
.room-dwellers {
  display: flex;
  gap: 0.25rem;
  flex-wrap: nowrap;
  justify-content: space-evenly;
  align-items: center;
  margin-top: 0.5rem;
  padding: 0.5rem;
  width: 100%;
  overflow-x: auto;
}

.dweller-avatar {
  position: relative;
  flex: 0 1 40px;
  min-width: 28px;
  max-width: 40px;
  aspect-ratio: 1;
  cursor: grab;
  transition: transform 0.2s;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  overflow: hidden;
}

.dweller-avatar--apprentice {
  border-color: var(--color-warning);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--color-warning) 70%, transparent),
    0 0 8px color-mix(in srgb, var(--color-warning) 35%, transparent);
}

.apprentice-badge {
  position: absolute;
  top: 0;
  left: 0;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 1px;
  border-bottom-right-radius: 3px;
  background: var(--color-warning);
  color: var(--color-surface-sunken);
  line-height: 0;
}

.apprentice-badge :deep(svg) {
  width: 0.6rem;
  height: 0.6rem;
}

.dweller-avatar:hover {
  transform: scale(1.1);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.dweller-avatar:active {
  cursor: grabbing;
  opacity: 0.7;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dweller-level {
  position: absolute;
  bottom: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.8);
  color: var(--color-theme-primary);
  font-size: 0.625rem;
  font-weight: bold;
  padding: 0 2px;
  line-height: 1;
  border-top-left-radius: 2px;
}

.icon-primary {
  color: var(--color-theme-primary);
}
</style>
