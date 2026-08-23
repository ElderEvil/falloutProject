import { computed, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { getTrainingRoomCapacity } from '../utils/room'
import type { Room } from '../models/room'

export function useRoomDwellers(
  room: Ref<Room | null>,
  actionError: Ref<string | null>,
  emitRoomUpdated: () => void
) {
  const route = useRoute()
  const router = useRouter()
  const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
  const authStore = useAuthStore()

  const assignedDwellers = computed<DwellerShort[]>(() => {
    if (!room.value) return []
    return dwellerStore.dwellers.filter((d) => d.room_id === room.value!.id)
  })

const dwellerCapacity = computed(() => {
  if (!room.value) return 0
  return getTrainingRoomCapacity(room.value)
})

  const getAbilityLabel = (ability: string) => {
    const cfg = getAbilityConfig(ability)
    return cfg ? `${cfg.letter} - ${cfg.label}` : ability
  }

  const getDwellerStatValue = (dweller: DwellerShort, ability: string) => {
    const key = ability.toLowerCase() as SpecialKey
    const value = dweller[key]
    return typeof value === 'number' ? value : 0
  }

  const handleUnassignAll = async () => {
    if (!room.value || assignedDwellers.value.length === 0) return

    if (!confirm(`Unassign all ${assignedDwellers.value.length} dwellers from this room?`)) {
      return
    }

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      actionError.value = 'No auth token available'
      return
    }

    actionError.value = null
    const dwellersToUnassign = [...assignedDwellers.value]

    try {
      const results = await Promise.allSettled(
        dwellersToUnassign.map((dweller) =>
          dwellerManagementStore.unassignDwellerFromRoom(dweller.id, token)
        )
      )

      const rejected = results.filter((result) => result.status === 'rejected')
      if (rejected.length > 0) {
        actionError.value = 'Failed to unassign some dwellers'
      }
    } catch (error) {
      actionError.value = error instanceof Error ? error.message : 'Failed to unassign dwellers'
    } finally {
      emitRoomUpdated()
    }
  }

  const openDwellerDetails = (dwellerId: string) => {
    const vaultId = route.params.id as string
    if (vaultId) {
      void router.push({
        name: 'dwellerDetail',
        params: { id: vaultId, dwellerId },
      })
    }
  }

  return {
    assignedDwellers,
    dwellerCapacity,
    getAbilityLabel,
    getDwellerStatValue,
    handleUnassignAll,
    openDwellerDetails,
  }
}
