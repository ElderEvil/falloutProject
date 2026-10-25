<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getRoomImageUrl } from '@/core/utils/image'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import ArenaPreview from './ArenaPreview.vue'
import { useArenaRoom } from '../composables/useArenaRoom'
import { useArenaMatchDraft } from '../composables/useArenaMatchDraft'
import ArenaSupportPanel from './ArenaSupportPanel.vue'
import { Button } from '@/core/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import TerminalConfirmation from '@/core/components/common/TerminalConfirmation.vue'
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
  changed: []
  upgrade: []
  destroy: []
  unassignAll: []
  assignDweller: [dwellerId: string]
  unassignDweller: [dwellerId: string]
  viewDweller: [dwellerId: string]
}>()

const controller = useArenaRoom(props.vaultId, props.room.id)
const match = useArenaMatchDraft(props.vaultId, props.room.id, controller)
const roomState = controller.roomState
const managementLocked = computed(() => !roomState.value || match.isFighting)
// The parent already owns refreshing room/dweller data after a room mutation.
watch(
  () => match.isFighting,
  () => emit('changed')
)

const stopConfirmOpen = ref(false)
const confirmStop = async () => {
  stopConfirmOpen.value = false
  await match.stopFight()
}
</script>

<template>
  <div class="arena-room-detail flex flex-col gap-3">
    <ComponentLoader v-if="!roomState && controller.isLoading.value" label="Loading Arena…" />
    <Alert v-else-if="!roomState && controller.loadFailed.value" variant="destructive">
      <AlertTitle>Arena unavailable</AlertTitle>
      <AlertDescription>Your match could not be loaded. Try connecting again.</AlertDescription>
      <Button variant="outline" size="sm" class="mt-2 w-fit" @click="controller.retry()">
        Retry
      </Button>
    </Alert>
    <ArenaPreview
      v-else
      :match="match"
      :scene-image-url="roomImageUrl ?? getRoomImageUrl(room.image_url)"
      :pending-skills="controller.pendingSkills.value"
      :attacking-team="controller.attackingTeam.value"
      :attacking-fighter-id="controller.attackingFighterId.value"
      :damage-numbers="controller.damageNumbers.value"
      :skill-burst="controller.skillBurst.value"
      :active-action="controller.activeAction?.value"
      :combat-phase="controller.combatPhase?.value"
      @skill="controller.queueSkill"
      @stop="stopConfirmOpen = true"
    />
    <TerminalConfirmation
      :open="stopConfirmOpen"
      title="Stop Arena Fight"
      message="Stop this match? Fighters keep their current health and no rewards are awarded."
      confirm-label="Stop Fight"
      @confirm="confirmStop"
      @cancel="stopConfirmOpen = false"
    />
    <p v-if="!roomState" class="text-xs text-muted-foreground">
      Room management is unavailable until match state loads.
    </p>
    <p v-else-if="match.isFighting" class="text-xs text-muted-foreground">
      Room management is locked until the match finishes.
    </p>
    <ArenaSupportPanel :match="match" />
    <RoomActions
      :disabled="managementLocked"
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
