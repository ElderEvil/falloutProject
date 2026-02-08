import { computed, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { Room } from '../models/room'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'

type SpecialKey =
  | 'strength'
  | 'perception'
  | 'endurance'
  | 'charisma'
  | 'intelligence'
  | 'agility'
  | 'luck'

export function useRoomDwellers(
  room: Ref<Room | null>,
  actionError: Ref<string | null>,
  emitRoomUpdated: () => void,
) {
  const route = useRoute()
  const router = useRouter()
  const dwellerStore = useDwellerStore()
  const authStore = useAuthStore()

  const assignedDwellers = computed<DwellerShort[]>(() => {
    if (!room.value) return []
    return dwellerStore.dwellers.filter((d) => d.room_id === room.value!.id)
  })

  const dwellerCapacity = computed(() => {
    if (!room.value) return 0
    const r = room.value
    const roomSize = r.size || r.size_min || 3
    const cellsOccupied = Math.ceil(roomSize / 3)
    return cellsOccupied * 2
  })

  const getAbilityLabel = (ability: string) => {
    const labels: Record<string, string> = {
      STRENGTH: 'S - Strength',
      PERCEPTION: 'P - Perception',
      ENDURANCE: 'E - Endurance',
      CHARISMA: 'C - Charisma',
      INTELLIGENCE: 'I - Intelligence',
      AGILITY: 'A - Agility',
      LUCK: 'L - Luck',
    }
    return labels[ability.toUpperCase()] || ability
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

    actionError.value = null

    try {
      for (const dweller of assignedDwellers.value) {
        await dwellerStore.unassignDwellerFromRoom(dweller.id, authStore.token as string)
      }
      emitRoomUpdated()
    } catch (error) {
      console.error('Failed to unassign dwellers:', error)
      actionError.value = error instanceof Error ? error.message : 'Failed to unassign dwellers'
    }
  }

  const openDwellerDetails = (dwellerId: string) => {
    const vaultId = route.params.id as string
    if (vaultId) {
      router.push({
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
