<script setup lang="ts">
import { computed } from 'vue'
import { useArenaStore } from '../stores/arena'
import DwellerList from './DwellerList.vue'
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

const props = defineProps<Props>()

const emit = defineEmits<{
  upgrade: []
  destroy: []
  unassignAll: []
  assignDweller: [dwellerId: string]
  unassignDweller: [dwellerId: string]
  viewDweller: [dwellerId: string]
}>()

const arenaStore = useArenaStore()
const isFighting = computed(() => {
  const state = arenaStore.getRoom(props.room.id)
  return !!state?.fight_started && !state.match_done
})

const assignmentMode = defineModel<'worker' | 'apprentice' | null>('assignmentMode', {
  default: null,
})
</script>

<template>
  <div class="arena-room-detail flex flex-col gap-3">
    <RoomPreviewSection
      :room-name="room.name"
      :image-url="room.image_url ?? null"
      :room-image-url="roomImageUrl"
      :room-units="room.size ?? room.size_min ?? 3"
      :dweller-capacity="dwellerCapacity"
      :assigned-dwellers="assignedDwellers"
      :assign-enabled="!isFighting"
      @activate="emit('viewDweller', $event)"
      @unassign="emit('unassignDweller', $event)"
      @assign-worker="assignmentMode = 'worker'"
    />
    <p v-if="isFighting" class="text-xs text-muted-foreground">
      Room management is locked until the match finishes.
    </p>
    <DwellerList
      v-if="assignmentMode && !isFighting && assignedDwellers.length < dwellerCapacity"
      v-model:assignment-mode="assignmentMode"
      :ability="null"
      title="Assign to Arena"
      empty-text="No unassigned adults available. Unassign an adult from another room first."
      @assign-dweller="emit('assignDweller', $event)"
    />
    <ArenaModal :vault-id="vaultId" :room-id="room.id" />
    <RoomActions
      :disabled="isFighting"
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
