<script setup lang="ts">
import { computed, watch, ref, toRef } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'
import { getRoomDetailParts, hasPart, producesResources, craftingItemType, isElevator, type RoomPart } from '../models/roomParts'
import { useRoomProduction } from '../composables/useRoomProduction'
import { useRoomUpgrade } from '../composables/useRoomUpgrade'
import { useRoomDwellers } from '../composables/useRoomDwellers'
import { useRadioRoom } from '../composables/useRadioRoom'
import UModal from '@/core/components/ui/UModal.vue'
import RoomDetailHeader from './RoomDetailHeader.vue'
import RoomPreviewSection from './RoomPreviewSection.vue'
import ProductionStats from './ProductionStats.vue'
import DwellerList from './DwellerList.vue'
import RadioControls from './RadioControls.vue'
import RoomActions from './RoomActions.vue'
import RoomTrainingSection from './RoomTrainingSection.vue'
import ArenaRoomDetail from './ArenaRoomDetail.vue'
import RoomIncidentDetail from './RoomIncidentDetail.vue'
import IncidentAftermath from './IncidentAftermath.vue'
import CraftingPanel from '@/modules/crafting/components/CraftingPanel.vue'
import OverseerBriefing from '@/modules/vault/components/shell/OverseerBriefing.vue'
import type { OverseerBriefingData } from '@/modules/vault/models/overseerBriefing'
import { useSound } from '@/core/composables/useSound'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

interface Props {
  room: Room | null
  modelValue: boolean
  vaultId: string
  overseerBriefing?: OverseerBriefingData
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  close: []
  roomUpdated: []
  reviewIncidents: []
}>()

const actionError = ref<string | null>(null)
const assignmentMode = ref<'worker' | 'apprentice' | null>(null)

const roomRef = toRef(props, 'room')
const modelValueRef = toRef(props, 'modelValue')

const incidentStore = useIncidentStore()
const liveIncident = computed(
  () => incidentStore.activeIncidents.find((inc) => inc.room_id === props.room?.id) ?? null
)
const liveAftermath = computed(() =>
  props.room ? (incidentStore.aftermathForRoom(props.room.id) ?? null) : null
)

// Which sections this room renders — decided by the part registry, nowhere else.
const parts = computed<RoomPart[]>(() =>
  getRoomDetailParts(props.room, liveIncident.value, liveAftermath.value)
)
const has = (part: RoomPart) => hasPart(parts.value, part)
const craftingType = computed(() => craftingItemType(props.room))
const roomUnits = computed(() => props.room?.size ?? props.room?.size_min ?? 3)
// Elevators keep one static slot for future transit display — no assignment.
const isElevatorRoom = computed(() => isElevator(props.room))

// Composables
const {
  assignedDwellers,
  dwellerCapacity,
  handleUnassignAll,
  handleUnassignDweller,
  handleAssignDweller,
  openDwellerDetails,
} = useRoomDwellers(roomRef, actionError, () => emit('roomUpdated'))

const { filter: dwellerStore } = useDwellerStore()
const vaultDwellers = computed(() => dwellerStore.dwellers)

const sceneCapacity = computed(() => isElevatorRoom.value ? 1 : dwellerCapacity.value)

const { resourceIcon, roomImageUrl, productionInfo } = useRoomProduction(
  roomRef,
  assignedDwellers,
  dwellerCapacity
)

const {
  isUpgrading,
  isDestroying,
  upgradeInfo,
  isVaultDoor,
  handleUpgrade,
  handleDestroy,
} = useRoomUpgrade(
  roomRef,
  actionError,
  () => emit('roomUpdated'),
  () => emit('close')
)

const {
  isRecruiting,
  localRadioMode,
  manualRecruitCost,
  radioStats,
  handleSwitchRadioMode,
  handleRecruitDweller,
} = useRadioRoom(roomRef, modelValueRef, assignedDwellers)

const { playSound } = useSound()

// Clear error when modal closes
watch(
  () => props.modelValue,
  (newValue, oldValue) => {
    if (!newValue) {
      actionError.value = null
      assignmentMode.value = null
    }
    if (newValue && newValue !== oldValue) playSound('modalOpen')
  }
)
</script>

<template>
  <UModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    @close="emit('close')"
    size="lg"
  >
    <template #header>
      <RoomDetailHeader
        v-if="room"
        :room="room"
        :resource-icon="resourceIcon"
      />
    </template>

    <div v-if="room" class="modal-content">
      <!-- Error display -->
      <div v-if="actionError && !has('arena') && !has('incident') && !has('aftermath')" class="error-banner">
        <Icon icon="mdi:alert-circle" class="h-5 w-5" />
        {{ actionError }}
      </div>

      <RoomIncidentDetail
        v-if="has('incident') && liveIncident"
        :incident="liveIncident"
        :vault-id="props.vaultId"
        :dwellers="vaultDwellers"
        :room-image-url="roomImageUrl ?? null"
      />

      <IncidentAftermath
        v-else-if="has('aftermath') && liveAftermath"
        :aftermath="liveAftermath"
      />

      <ArenaRoomDetail
        v-else-if="has('arena')"
        :room="room"
        :vault-id="props.vaultId"
        :assigned-dwellers="assignedDwellers"
        :dweller-capacity="dwellerCapacity"
        :room-image-url="roomImageUrl ?? null"
        :upgrade-info="upgradeInfo"
        :is-upgrading="isUpgrading"
        :is-destroying="isDestroying"
        :is-vault-door="isVaultDoor"
        @upgrade="handleUpgrade"
        @destroy="handleDestroy"
        @unassign-all="handleUnassignAll"
      />

      <template v-else>
        <RoomPreviewSection
          :room-name="room.name"
          :image-url="room.image_url ?? null"
          :room-image-url="roomImageUrl ?? null"
          :room-units="roomUnits"
          :dweller-capacity="sceneCapacity"
          :assigned-dwellers="assignedDwellers"
          :show-apprentice-slot="producesResources(room) && !isElevatorRoom"
          :assign-enabled="!isElevatorRoom"
          @activate="openDwellerDetails"
          @unassign="handleUnassignDweller"
          @assign-worker="assignmentMode = 'worker'"
          @assign-apprentice="assignmentMode = 'apprentice'"
        />

        <DwellerList
          v-if="has('dwellerList')"
          v-model:assignment-mode="assignmentMode"
          :ability="room.ability"
          @assign-dweller="handleAssignDweller"
        />

        <OverseerBriefing
          v-if="has('overseerBriefing') && overseerBriefing"
          v-bind="overseerBriefing"
          @review-incidents="emit('reviewIncidents')"
        />

        <ProductionStats
          v-if="has('radioStats') && radioStats"
          :radio-stats="radioStats"
          :radio-mode="localRadioMode"
        />

        <ProductionStats v-else-if="has('productionStats') && productionInfo" :production-info="productionInfo" />

        <RoomTrainingSection
          v-if="has('training')"
          :room="room"
          :assigned-dwellers="assignedDwellers"
        />

        <CraftingPanel
          v-if="has('crafting') && craftingType"
          :vault-id="vaultId"
          :item-type="craftingType"
          @crafted="emit('roomUpdated')"
        />

        <RadioControls
          v-if="has('radioControls')"
          :local-radio-mode="localRadioMode"
          :is-recruiting="isRecruiting"
          :manual-recruit-cost="manualRecruitCost"
          :assigned-dwellers="assignedDwellers"
          @switch-mode="handleSwitchRadioMode"
          @recruit="handleRecruitDweller"
        />

        <RoomActions
          v-if="has('actions')"
          :room="room"
          :upgrade-info="upgradeInfo"
          :is-upgrading="isUpgrading"
          :is-destroying="isDestroying"
          :is-vault-door="isVaultDoor"
          :assigned-dweller-count="assignedDwellers.length"
          @upgrade="handleUpgrade"
          @destroy="handleDestroy"
          @unassign-all="handleUnassignAll"
        />
      </template>
    </div>
  </UModal>
</template>

<style scoped>
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.25rem 0;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(255, 0, 0, 0.1);
  border: 1px solid var(--color-danger);
  border-radius: 4px;
  color: var(--color-danger);
  font-size: 0.875rem;
}
</style>
