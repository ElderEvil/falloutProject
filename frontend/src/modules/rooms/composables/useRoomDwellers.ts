import { computed, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
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

  const roomToken = (): string | null => (typeof authStore.token === 'string' ? authStore.token : null)

  const handleUnassignAll = async () => {
    if (!room.value || assignedDwellers.value.length === 0) return

    if (!confirm(`Unassign all ${assignedDwellers.value.length} dwellers from this room?`)) {
      return
    }

    const token = roomToken()
    if (!token) {
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

  const handleUnassignDweller = async (dwellerId: string): Promise<void> => {
    const token = roomToken()
    if (!token) {
      actionError.value = 'No auth token available'
      return
    }

    actionError.value = null
    try {
      await dwellerManagementStore.unassignDwellerFromRoom(dwellerId, token)
    } catch (error) {
      actionError.value = error instanceof Error ? error.message : 'Failed to unassign dweller'
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

  const handleAssignDweller = async (dwellerId: string): Promise<void> => {
    if (!room.value) return
    const token = roomToken()
    if (!token) {
      actionError.value = 'No auth token available'
      return
    }

    actionError.value = null
    try {
      await dwellerManagementStore.assignDwellerToRoom(dwellerId, room.value.id, token)
    } catch {
      actionError.value = 'Failed to assign dweller to room'
    } finally {
      emitRoomUpdated()
    }
  }

  return {
    assignedDwellers,
    dwellerCapacity,
    handleUnassignAll,
    handleUnassignDweller,
    handleAssignDweller,
    openDwellerDetails,
  }
}
