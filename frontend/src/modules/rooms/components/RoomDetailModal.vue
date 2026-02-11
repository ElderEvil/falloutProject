<script setup lang="ts">
import { computed, watch, ref, toRef } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'
import { useRoomProduction } from '../composables/useRoomProduction'
import { useRoomUpgrade } from '../composables/useRoomUpgrade'
import { useRoomDwellers } from '../composables/useRoomDwellers'
import { useRadioRoom } from '../composables/useRadioRoom'
import UModal from '@/core/components/ui/UModal.vue'
import RoomDetailHeader from './RoomDetailHeader.vue'
import RoomPreviewSection from './RoomPreviewSection.vue'
import RoomInfoGrid from './RoomInfoGrid.vue'
import ProductionStats from './ProductionStats.vue'
import DwellerList from './DwellerList.vue'
import RadioControls from './RadioControls.vue'
import RoomActions from './RoomActions.vue'

interface Props {
  room: Room | null
  modelValue: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  close: []
  roomUpdated: []
}>()

const actionError = ref<string | null>(null)

const roomRef = toRef(props, 'room')
const modelValueRef = toRef(props, 'modelValue')

// Composables
const {
  assignedDwellers,
  dwellerCapacity,
  getAbilityLabel,
  handleUnassignAll,
  openDwellerDetails,
} = useRoomDwellers(roomRef, actionError, () => emit('roomUpdated'))

const {
  resourceIcon,
  roomImageUrl,
  productionInfo,
} = useRoomProduction(roomRef, assignedDwellers, dwellerCapacity)

const {
  isUpgrading,
  isDestroying,
  isRushing,
  justUpgraded,
  upgradeInfo,
  isVaultDoor,
  handleUpgrade,
  handleDestroy,
  handleRushProduction,
} = useRoomUpgrade(roomRef, actionError, () => emit('roomUpdated'), () => emit('close'))

const {
  isRecruiting,
  isRadioRoom,
  localRadioMode,
  manualRecruitCost,
  handleSwitchRadioMode,
  handleRecruitDweller,
} = useRadioRoom(roomRef, modelValueRef, assignedDwellers)

// Clear error when modal closes
watch(
  () => props.modelValue,
  (newValue) => {
    if (!newValue) {
      actionError.value = null
    }
  },
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
        :room-name="room.name"
        :category="room.category"
        :tier="room.tier"
        :ability="room.ability"
        :resource-icon="resourceIcon"
        :just-upgraded="justUpgraded"
      />
    </template>

    <div v-if="room" class="modal-content">
      <!-- Error display -->
      <div v-if="actionError" class="error-banner">
        <Icon icon="mdi:alert-circle" class="h-5 w-5" />
        {{ actionError }}
      </div>

      <RoomPreviewSection
        :room-name="room.name"
        :image-url="room.image_url"
        :room-image-url="roomImageUrl"
        :dweller-capacity="dwellerCapacity"
        :assigned-dwellers="assignedDwellers"
      />

      <RoomInfoGrid
        :room="room"
        :assigned-dweller-count="assignedDwellers.length"
        :dweller-capacity="dwellerCapacity"
        :ability-label="room.ability ? getAbilityLabel(room.ability) : null"
      />

      <ProductionStats v-if="productionInfo" :production-info="productionInfo" />

      <DwellerList
        :assigned-dwellers="assignedDwellers"
        :ability="room.ability"
        @dweller-click="openDwellerDetails"
      />

      <RoomActions
        :room="room"
        :upgrade-info="upgradeInfo"
        :is-upgrading="isUpgrading"
        :is-destroying="isDestroying"
        :is-rushing="isRushing"
        :is-vault-door="isVaultDoor"
        :has-production-info="!!productionInfo"
        :is-radio-room="isRadioRoom"
        :assigned-dweller-count="assignedDwellers.length"
        @upgrade="handleUpgrade"
        @destroy="handleDestroy"
        @rush-production="handleRushProduction"
        @unassign-all="handleUnassignAll"
      >
        <template v-if="isRadioRoom" #radio-controls>
          <RadioControls
            :local-radio-mode="localRadioMode"
            :is-recruiting="isRecruiting"
            :manual-recruit-cost="manualRecruitCost"
            :assigned-dwellers="assignedDwellers"
            @switch-mode="handleSwitchRadioMode"
            @recruit="handleRecruitDweller"
          />
        </template>
      </RoomActions>
    </div>
  </UModal>
</template>

<style scoped>
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1rem 0;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(255, 0, 0, 0.1);
  border: 1px solid #ff0000;
  border-radius: 4px;
  color: #ff0000;
  font-size: 0.875rem;
}
</style>
