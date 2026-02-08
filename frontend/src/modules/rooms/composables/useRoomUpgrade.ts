import { computed, ref, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import type { Room } from '../models/room'
import { useRoomStore } from '../stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'

export function useRoomUpgrade(
  room: Ref<Room | null>,
  actionError: Ref<string | null>,
  emitRoomUpdated: () => void,
  emitClose: () => void,
) {
  const route = useRoute()
  const roomStore = useRoomStore()
  const authStore = useAuthStore()
  const toast = useToast()

  const isUpgrading = ref(false)
  const isDestroying = ref(false)
  const isRushing = ref(false)
  const justUpgraded = ref(false)

  const upgradeInfo = computed(() => {
    if (!room.value) return null

    const r = room.value
    const maxTier = r.t2_upgrade_cost && r.t3_upgrade_cost ? 3 : r.t2_upgrade_cost ? 2 : 1
    const canUpgrade = r.tier < maxTier
    const nextTier = Math.min(r.tier + 1, maxTier)

    let upgradeCost = 0
    if (r.tier === 1 && r.t2_upgrade_cost) {
      upgradeCost = r.t2_upgrade_cost
    } else if (r.tier === 2 && r.t3_upgrade_cost) {
      upgradeCost = r.t3_upgrade_cost
    }

    return {
      canUpgrade,
      upgradeCost,
      nextTier,
      maxTier,
    }
  })

  const isVaultDoor = computed(() => {
    return room.value?.name?.toLowerCase() === 'vault door'
  })

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

    const roomName = room.value.name
    const currentTier = room.value.tier
    const nextTier = currentTier + 1
    const upgradeCost = upgradeInfo.value?.upgradeCost || 0

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
      console.error('Failed to upgrade room:', error)
      actionError.value = error instanceof Error ? error.message : 'Failed to upgrade room'
      toast.error(error instanceof Error ? error.message : 'Failed to upgrade room', 5000)
    } finally {
      isUpgrading.value = false
    }
  }

  const handleDestroy = async () => {
    if (!room.value) return

    if (
      !confirm(
        `Are you sure you want to destroy ${room.value.name}? You will receive a partial refund.`,
      )
    ) {
      return
    }

    isDestroying.value = true
    actionError.value = null
    const roomName = room.value.name

    const vaultId = route.params.id
    if (!vaultId || typeof vaultId !== 'string') {
      actionError.value = 'No vault ID available'
      isDestroying.value = false
      return
    }

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      actionError.value = 'No auth token available'
      isDestroying.value = false
      return
    }

    try {
      await roomStore.destroyRoom(room.value.id, token, vaultId)
      toast.success(`${roomName} destroyed. Caps refunded (50%).`)
      emitRoomUpdated()
      emitClose()
    } catch (error) {
      console.error('Failed to destroy room:', error)
      actionError.value = error instanceof Error ? error.message : 'Failed to destroy room'
      toast.error(error instanceof Error ? error.message : 'Failed to destroy room', 5000)
    } finally {
      isDestroying.value = false
    }
  }

  const handleRushProduction = async () => {
    if (!room.value) return

    actionError.value = 'Rush Production feature coming soon!'
    setTimeout(() => {
      actionError.value = null
    }, 3000)
  }

  return {
    isUpgrading,
    isDestroying,
    isRushing,
    justUpgraded,
    upgradeInfo,
    isVaultDoor,
    handleUpgrade,
    handleDestroy,
    handleRushProduction,
  }
}
