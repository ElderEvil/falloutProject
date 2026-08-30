<script setup lang="ts">
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import RoomPreviewSection from './RoomPreviewSection.vue'
import ArenaModal from './ArenaModal.vue'

interface Props {
  room: Room
  vaultId: string
  assignedDwellers: DwellerShort[]
  dwellerCapacity: number
  roomImageUrl: string | null
  isDestroying: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  destroy: []
}>()
</script>

<template>
  <div class="arena-room-detail">
    <RoomPreviewSection
      :room-name="room.name"
      :image-url="room.image_url ?? null"
      :room-image-url="roomImageUrl"
      :dweller-capacity="dwellerCapacity"
      :assigned-dwellers="assignedDwellers"
    />
    <ArenaModal
      :vault-id="vaultId"
      :room-id="room.id"
      :is-destroying="isDestroying"
      @destroy="emit('destroy')"
    />
  </div>
</template>

<style scoped>
.arena-room-detail {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
