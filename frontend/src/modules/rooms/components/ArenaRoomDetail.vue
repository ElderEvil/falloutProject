<script setup lang="ts">
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import RoomPreviewSection from './RoomPreviewSection.vue'
import ArenaModal from './ArenaModal.vue'
import RoomActions from './RoomActions.vue'

interface UpgradeInfo {
  canUpgrade: boolean
  upgradeCost: number
  nextTier: number
  maxTier: number
}

interface Props {
  room: Room
  vaultId: string
  assignedDwellers: DwellerShort[]
  dwellerCapacity: number
  roomImageUrl: string | null
  upgradeInfo: UpgradeInfo | null
  isUpgrading: boolean
  isDestroying: boolean
  isVaultDoor: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  upgrade: []
  destroy: []
  unassignAll: []
}>()
</script>

<template>
  <div class="arena-room-detail">
    <RoomPreviewSection
      :room-name="room.name"
      :image-url="room.image_url ?? null"
      :room-image-url="roomImageUrl"
      :room-units="room.size ?? room.size_min ?? 3"
      :dweller-capacity="dwellerCapacity"
      :assigned-dwellers="assignedDwellers"
    />
    <ArenaModal
      :vault-id="vaultId"
      :room-id="room.id"
    />
    <RoomActions
      :room="room"
      :upgrade-info="upgradeInfo"
      :is-upgrading="isUpgrading"
      :is-destroying="isDestroying"
      :is-vault-door="isVaultDoor"
      :assigned-dweller-count="assignedDwellers.length"
      @upgrade="emit('upgrade')"
      @destroy="emit('destroy')"
      @unassign-all="emit('unassignAll')"
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
