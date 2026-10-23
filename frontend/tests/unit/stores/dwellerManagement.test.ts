import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createAxiosMock, createToastMock } from '../helpers/mocks'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { audioManager } from '@/core/audio/audioManager'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useDwellerManagementStore } from '@/modules/dwellers/stores/dwellerManagement'
import { useRoomStore } from '@/modules/rooms/stores/room'

vi.mock('@/core/plugins/axios', () => createAxiosMock())

vi.mock('@/core/audio/audioManager', () => ({
  audioManager: { play: vi.fn() },
}))

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

describe('useDwellerManagementStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renames both names and updates both cached representations', async () => {
    const filter = useDwellerFilterStore()
    const management = useDwellerManagementStore()
    filter.dwellers = [{ id: 'd1', first_name: 'John', last_name: 'Doe' }] as never
    filter.detailedDwellers.d1 = filter.dwellers[0] as never
    vi.mocked(axios.patch).mockResolvedValue({
      data: { id: 'd1', first_name: 'Jane', last_name: 'Smith' },
    })
    await management.renameDweller('d1', 'Jane', 'token', 'Smith')
    expect(axios.patch).toHaveBeenCalledWith(
      '/api/v1/dwellers/d1/rename',
      { first_name: 'Jane', last_name: 'Smith' },
      { headers: { Authorization: 'Bearer token' } }
    )
    expect(filter.dwellers[0]).toMatchObject({ first_name: 'Jane', last_name: 'Smith' })
    expect(filter.detailedDwellers.d1).toMatchObject({ first_name: 'Jane', last_name: 'Smith' })
  })

  it('keeps Gary feedback in a single rename confirmation', async () => {
    vi.mocked(axios.patch).mockResolvedValueOnce({ data: { id: 'd1', first_name: 'Gary' } })
    await useDwellerManagementStore().renameDweller('d1', 'Gary', 'token')
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith(
      expect.stringContaining('VAULT 108 PROTOCOL ACTIVATED'),
      5000
    )
    expect(mockToast.info).not.toHaveBeenCalled()
  })

  it('assigns only available dwellers to production rooms and refreshes the list', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    const refreshSpy = vi.spyOn(filterStore, 'fetchWithCurrentFilters').mockResolvedValue()
    vi.mocked(axios.post).mockResolvedValue({
      data: { assigned_count: 2, assignments: [] },
    })

    const result = await managementStore.autoAssignProductionDwellers('vault-1', 'token-1')

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/vaults/vault-1/dwellers/auto-assign-production',
      null,
      { headers: { Authorization: 'Bearer token-1' } }
    )
    expect(refreshSpy).toHaveBeenCalledWith('vault-1', 'token-1')
    expect(result).toEqual({ assigned_count: 2, assignments: [] })
  })

  it('apprentices a youth in the first production room without an apprentice', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    const roomStore = useRoomStore()

    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
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

    vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
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

  it('plays the card drop sound when a dweller is assigned to a room', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.post).mockResolvedValue({ data: { id: 'dweller-1', room_id: 'room-2' } })

    const result = await managementStore.assignDwellerToRoom('dweller-1', 'room-2', 'token-1')

    expect(result).toEqual({ id: 'dweller-1', room_id: 'room-2' })
    expect(audioManager.play).toHaveBeenCalledWith('cardDrop', 'ui')
  })

  it('plays the card drop sound when a dweller is unassigned from a room', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.put).mockResolvedValue({
      data: { id: 'dweller-1', room_id: null, status: 'idle' },
    })

    const result = await managementStore.unassignDwellerFromRoom('dweller-1', 'token-1')

    expect(result).toEqual({ id: 'dweller-1', room_id: null, status: 'idle' })
    expect(audioManager.play).toHaveBeenCalledWith('cardDrop', 'ui')
  })

  it('emits one toast with the backend detail when a rename fails', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.patch).mockRejectedValueOnce({
      response: { status: 409, data: { detail: 'Name already taken' } },
    })

    const result = await managementStore.renameDweller('d1', 'Jane', 'token-1', 'Smith')

    expect(result).toBeNull()
    expect(mockToast.error).toHaveBeenCalledTimes(1)
    expect(mockToast.error).toHaveBeenCalledWith('Failed to rename dweller d1: Name already taken')
  })

  it('emits one toast with the backend detail when bulk unassign fails', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Vault is locked down' } },
    })

    const result = await managementStore.unassignAllDwellers('vault-1', 'token-1')

    expect(result).toBeNull()
    expect(mockToast.error).toHaveBeenCalledTimes(1)
    expect(mockToast.error).toHaveBeenCalledWith(
      'Failed to unassign all dwellers for vault vault-1: Vault is locked down'
    )
  })

  it('emits one toast with the action label and backend detail when bulk auto-assign fails', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'No eligible dwellers' } },
    })

    const result = await managementStore.autoAssignProductionDwellers('vault-1', 'token-1')

    expect(result).toBeNull()
    expect(mockToast.error).toHaveBeenCalledTimes(1)
    expect(mockToast.error).toHaveBeenCalledWith(
      'Failed to auto-assign dwellers to production rooms for vault vault-1: No eligible dwellers'
    )
  })
})
