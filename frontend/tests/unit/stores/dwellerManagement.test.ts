import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useDwellerManagementStore } from '@/modules/dwellers/stores/dwellerManagement'
import { useRoomStore } from '@/modules/rooms/stores/room'

vi.mock('@/core/plugins/axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}))

describe('useDwellerManagementStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('assigns only available dwellers to production rooms and refreshes the list', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    const refreshSpy = vi.spyOn(filterStore, 'fetchDwellersByVault').mockResolvedValue()
    vi.mocked(axios.post).mockResolvedValue({
      data: { assigned_count: 2, assignments: [] },
    })

    const result = await managementStore.autoAssignProductionDwellers('vault-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/vaults/vault-1/dwellers/auto-assign-production',
      null,
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(refreshSpy).toHaveBeenCalledWith('vault-1', 'token-1', {
      status: filterStore.filterStatus,
      ageGroup: filterStore.filterAgeGroup,
      race: filterStore.filterRace,
      faction: filterStore.filterFaction,
      sortBy: filterStore.sortBy,
      order: filterStore.sortDirection,
    })
    expect(result).toEqual({ assigned_count: 2, assignments: [] })
  })

  it('apprentices a youth in the first production room without an apprentice', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    const roomStore = useRoomStore()

    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue()
    roomStore.rooms = [
      { id: 'room-1', name: 'Power Generator', category: 'production', ability: 'strength' },
      { id: 'room-2', name: 'Diner', category: 'production', ability: 'agility' },
      { id: 'room-3', name: 'Weight Room', category: 'training', ability: null },
    ] as never
    vi.spyOn(filterStore, 'fetchAllDwellers').mockResolvedValue()
    filterStore.dwellers = [
      { id: 'youth-9', room_id: 'room-1', apprentice_stat: 'strength' },
    ] as never
    vi.mocked(axios.post).mockResolvedValue({ data: { id: 'youth-1', room_id: 'room-2' } })

    const result = await managementStore.assignApprenticeToRoom('youth-1', 'vault-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith('/api/v1/dwellers/youth-1/move_to/room-2', null, {
      headers: { Authorization: 'Bearer token-1' },
    })
    expect(result).toEqual({ id: 'youth-1', room_id: 'room-2' })
  })

  it('does not assign an apprentice when every production room is taken', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    const roomStore = useRoomStore()

    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue()
    roomStore.rooms = [
      { id: 'room-1', name: 'Power Generator', category: 'production', ability: 'strength' },
    ] as never
    vi.spyOn(filterStore, 'fetchAllDwellers').mockResolvedValue()
    filterStore.dwellers = [
      { id: 'youth-9', room_id: 'room-1', apprentice_stat: 'strength' },
    ] as never

    const result = await managementStore.assignApprenticeToRoom('youth-1', 'vault-1', 'token-1')

    expect(result).toBeNull()
    expect(axios.post).not.toHaveBeenCalled()
  })
})
