import { computed, onScopeDispose, ref, type Ref } from 'vue'
import { useConfirmDialog } from '@vueuse/core'
import { useRoute } from 'vue-router'
import type { Room } from '../models/room'
import { isVaultDoor } from '../models/roomParts'
import { useRoomStore } from '../stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { useRoomDestroy } from './useRoomDestroy'
import { notifyErrorOnce, getErrorMessage } from '@/core/utils/errorHandler'
import { getRoomSegmentCount } from '../utils/room'

export function useRoomUpgrade(
  room: Ref<Room | null>,
  actionError: Ref<string | null>,
  emitRoomUpdated: () => void,
  emitClose: () => void
) {
  const route = useRoute()
  const roomStore = useRoomStore()
  const authStore = useAuthStore()
  const toast = useToast()

  const {
    isDestroying,
    destroyRoom,
    destroyTitle,
    showDestroyConfirmation,
    confirmDestroy,
    cancelDestroy,
  } = useRoomDestroy()

  const isUpgrading = ref(false)
  const justUpgraded = ref(false)
  const isRemodeling = ref(false)
  const remodelTitle = ref('')
  const {
    isRevealed: showRemodelConfirmation,
    reveal: revealRemodel,
    confirm: confirmRemodel,
    cancel: cancelRemodel,
  } = useConfirmDialog()
  onScopeDispose(cancelRemodel)

  const upgradeInfo = computed(() => {
    if (!room.value) return null

    const r = room.value
    const maxTier = r.t2_upgrade_cost && r.t3_upgrade_cost ? 3 : r.t2_upgrade_cost ? 2 : 1
    const canUpgrade = r.tier < maxTier
    const nextTier = Math.min(r.tier + 1, maxTier)

    let upgradeCost = 0
    if (r.tier === 1 && r.t2_upgrade_cost) {
      upgradeCost = r.t2_upgrade_cost * getRoomSegmentCount(r)
    } else if (r.tier === 2 && r.t3_upgrade_cost) {
      upgradeCost = r.t3_upgrade_cost * getRoomSegmentCount(r)
    }

    return {
      canUpgrade,
      upgradeCost,
      nextTier,
      maxTier,
    }
  })

  const isVaultDoorRoom = computed(() => isVaultDoor(room.value))

  const handleUpgrade = async () => {
    if (!room.value) return

    const vaultId = route.params.id
    if (!vaultId || typeof vaultId !== 'string') {
      actionError.value = 'No vault ID available'
      return
    }

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      actionError.value = 'No auth token available'
      return
    }

    const info = upgradeInfo.value
    if (!info?.canUpgrade) {
      actionError.value = 'Room is already at max tier'
      toast.error('Room is already at max tier', 5000)
      return
    }

    const roomName = room.value.name
    const nextTier = info.nextTier
    const upgradeCost = info.upgradeCost

    isUpgrading.value = true
    actionError.value = null

    try {
      await roomStore.upgradeRoom(room.value.id, token, vaultId)

      toast.success(`${roomName} upgraded to Tier ${nextTier}! (Cost: ${upgradeCost} caps)`, 5000)

      justUpgraded.value = true
      setTimeout(() => {
        justUpgraded.value = false
      }, 1000)

      emitRoomUpdated()
      setTimeout(() => {
        emitClose()
      }, 800)
    } catch (error) {
      actionError.value = error instanceof Error ? error.message : 'Failed to upgrade room'
      notifyErrorOnce(
        error,
        error instanceof Error ? error.message : 'Failed to upgrade room',
        5000
      )
    } finally {
      isUpgrading.value = false
    }
  }

  const handleDestroy = async () => {
    if (!room.value) return
    await destroyRoom(room.value.id, {
      roomName: room.value.name,
      actionError,
      onSuccess: () => {
        emitRoomUpdated()
        emitClose()
      },
    })
  }

  const handleRemodel = async (otherRoomId?: string) => {
    if (!room.value || !authStore.token || isRemodeling.value || showRemodelConfirmation.value)
      return
    const roomId = room.value.id
    const token = authStore.token
    const verb = otherRoomId ? 'Merge' : 'Split'
    remodelTitle.value = `${verb} ${room.value.name}?`
    const { isCanceled } = await revealRemodel()
    if (isCanceled || room.value?.id !== roomId || authStore.token !== token) return
    isRemodeling.value = true
    actionError.value = null
    try {
      await roomStore.remodelRoom(roomId, token, otherRoomId)
      toast.success(otherRoomId ? 'Rooms merged.' : 'Room split into base segments.')
      emitRoomUpdated()
      emitClose()
    } catch (error) {
      actionError.value = getErrorMessage(error)
      notifyErrorOnce(error, actionError.value)
    } finally {
      isRemodeling.value = false
    }
  }

  return {
    isUpgrading,
    isRemodeling,
    remodelTitle,
    showRemodelConfirmation,
    confirmRemodel,
    cancelRemodel,
    handleRemodel,
    isDestroying,
    destroyTitle,
    showDestroyConfirmation,
    confirmDestroy,
    cancelDestroy,
    justUpgraded,
    upgradeInfo,
    isVaultDoor: isVaultDoorRoom,
    handleUpgrade,
    handleDestroy,
  }
}
