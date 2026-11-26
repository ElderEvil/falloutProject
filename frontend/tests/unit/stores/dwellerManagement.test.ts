import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createAxiosMock, createToastMock } from '../helpers/mocks'
import { createPinia, setActivePinia } from 'pinia'
import axios from '@/core/plugins/axios'
import { audioManager } from '@/core/audio/audioManager'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useDwellerManagementStore } from '@/modules/dwellers/stores/dwellerManagement'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'

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

  it('renames both names and updates every cached roster representation', async () => {
    const filter = useDwellerFilterStore()
    const management = useDwellerManagementStore()
    filter.dwellers = [{ id: 'd1', first_name: 'John', last_name: 'Doe' }] as never
    filter.allDwellers = [{ id: 'd1', first_name: 'John', last_name: 'Doe' }] as never
    filter.detailedDwellers.d1 = filter.dwellers[0] as never
    vi.mocked(axios.patch).mockResolvedValue({
      data: { id: 'd1', first_name: 'Jane', last_name: 'Smith' },
    })
    await management.renameDweller('d1', 'Jane', 'Smith')
    expect(axios.patch).toHaveBeenCalledWith('/api/v1/dwellers/d1/rename', {
      first_name: 'Jane',
      last_name: 'Smith',
    })
    expect(filter.dwellers[0]).toMatchObject({ first_name: 'Jane', last_name: 'Smith' })
    expect(filter.allDwellers[0]).toMatchObject({ first_name: 'Jane', last_name: 'Smith' })
    expect(filter.detailedDwellers.d1).toMatchObject({ first_name: 'Jane', last_name: 'Smith' })
  })

  it('keeps Gary feedback in a single rename confirmation', async () => {
    vi.mocked(axios.patch).mockResolvedValueOnce({ data: { id: 'd1', first_name: 'Gary' } })
    await useDwellerManagementStore().renameDweller('d1', 'Gary')
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith(
      expect.stringContaining('VAULT 108 PROTOCOL ACTIVATED'),
      5000
    )
    expect(mockToast.info).not.toHaveBeenCalled()
  })

  it('assigns only available dwellers to production rooms and refreshes both lists', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    useVaultStore().activeVaultId = 'vault-1'
    const refreshSpy = vi.spyOn(filterStore, 'fetchWithCurrentFilters').mockResolvedValue()
    const rosterSpy = vi.spyOn(filterStore, 'fetchAllDwellers').mockResolvedValue()
    vi.mocked(axios.post).mockResolvedValue({
      data: { assigned_count: 2, assignments: [] },
    })

    const result = await managementStore.autoAssignProductionDwellers('vault-1')
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/vaults/vault-1/dwellers/auto-assign-production',
      null
    )
    expect(refreshSpy).toHaveBeenCalledWith('vault-1')
    expect(rosterSpy).toHaveBeenCalledWith('vault-1', false, true)
    expect(result).toEqual({ assigned_count: 2, assignments: [] })
  })

  it('refreshes the full roster after unassigning every dweller', async () => {
    const filterStore = useDwellerFilterStore()
    const managementStore = useDwellerManagementStore()
    useVaultStore().activeVaultId = 'vault-1'
    const pageSpy = vi.spyOn(filterStore, 'fetchDwellersByVault').mockResolvedValue()
    const rosterSpy = vi.spyOn(filterStore, 'fetchAllDwellers').mockResolvedValue()
    vi.mocked(axios.post).mockResolvedValue({ data: { unassigned_count: 3 } })

    const result = await managementStore.unassignAllDwellers('vault-1')
    expect(result).toEqual({ unassigned_count: 3 })
    expect(pageSpy).toHaveBeenCalledWith('vault-1')
    expect(rosterSpy).toHaveBeenCalledWith('vault-1', false, true)
  })

  it('ignores a bulk unassign response that lands after the active vault switches', async () => {
    const vaultStore = useVaultStore()
    vaultStore.activeVaultId = 'vault-a'
    const filter = useDwellerFilterStore()
    const management = useDwellerManagementStore()
    filter.dwellers = [{ id: 'b1', room_id: 'room-b', status: 'working' }] as never
    filter.allDwellers = [{ id: 'b1', room_id: 'room-b', status: 'working' }] as never
    filter.allDwellersLoadedVaultId = 'vault-b'
    const pageSpy = vi.spyOn(filter, 'fetchDwellersByVault').mockResolvedValue()
    const rosterSpy = vi.spyOn(filter, 'fetchAllDwellers').mockResolvedValue()
    const pending = deferred<{ data: unknown }>()
    vi.mocked(axios.post).mockReturnValueOnce(pending.promise as never)

    const call = management.unassignAllDwellers('vault-a')
    vaultStore.activeVaultId = 'vault-b'
    pending.resolve({ data: { unassigned_count: 4 } })
    await call
    expect(pageSpy).not.toHaveBeenCalled()
    expect(rosterSpy).not.toHaveBeenCalled()
    expect(filter.allDwellers).toEqual([{ id: 'b1', room_id: 'room-b', status: 'working' }])
    expect(filter.allDwellersLoadedVaultId).toBe('vault-b')
  })

  it('rolls a failed move back to unassigned after a bulk unassign refreshes the roster', async () => {
    const filter = useDwellerFilterStore()
    const management = useDwellerManagementStore()
    useVaultStore().activeVaultId = 'vault-1'
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'working' }] as never
    filter.allDwellers = [{ id: 'd1', room_id: 'room-1', status: 'working' }] as never

    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { id: 'd1', room_id: 'room-2', status: 'working' },
    })
    await management.assignDwellerToRoom('d1', 'room-2')
    vi.spyOn(filter, 'fetchDwellersByVault').mockImplementation(async () => {
      filter.dwellers = [{ id: 'd1', room_id: null, status: 'idle' }] as never
    })
    vi.spyOn(filter, 'fetchAllDwellers').mockImplementation(async () => {
      filter.allDwellers = [{ id: 'd1', room_id: null, status: 'idle' }] as never
    })
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { unassigned_count: 1 } })
    await management.unassignAllDwellers('vault-1')
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Room is full' } },
    })
    await expect(management.assignDwellerToRoom('d1', 'room-3')).rejects.toBeTruthy()
    expect(filter.dwellers[0]).toMatchObject({ room_id: null })
    expect(filter.allDwellers[0]).toMatchObject({ room_id: null })
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
    const result = await managementStore.assignApprenticeToRoom('youth-1', 'vault-1')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/dwellers/youth-1/move_to/room-2')
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
    const result = await managementStore.assignApprenticeToRoom('youth-1', 'vault-1')
    expect(result).toBeNull()
    expect(axios.post).not.toHaveBeenCalled()
  })

  it('plays the card drop sound when a dweller is assigned to a room', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.post).mockResolvedValue({ data: { id: 'dweller-1', room_id: 'room-2' } })
    const result = await managementStore.assignDwellerToRoom('dweller-1', 'room-2')
    expect(result).toEqual({ id: 'dweller-1', room_id: 'room-2' })
    expect(audioManager.play).toHaveBeenCalledWith('cardDrop', 'ui')
  })

  it('applies the room assignment before the server responds', async () => {
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    filter.allDwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    const pending = deferred<{ data: unknown }>()
    vi.mocked(axios.post).mockReturnValueOnce(pending.promise as never)

    const call = useDwellerManagementStore().assignDwellerToRoom('d1', 'room-2')
    expect(filter.dwellers[0]?.room_id).toBe('room-2')
    expect(filter.allDwellers[0]?.room_id).toBe('room-2')
    pending.resolve({ data: { id: 'd1', room_id: 'room-2', status: 'working' } })
    await call
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-2', status: 'working' })
    expect(filter.allDwellers[0]).toMatchObject({ room_id: 'room-2', status: 'working' })
  })

  it('rolls the room assignment back when the server rejects it', async () => {
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'working' }] as never
    filter.allDwellers = [{ id: 'd1', room_id: 'room-1', status: 'working' }] as never
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Room is full' } },
    })

    await expect(
      useDwellerManagementStore().assignDwellerToRoom('d1', 'room-2')
    ).rejects.toBeTruthy()
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-1', status: 'working' })
    expect(filter.allDwellers[0]).toMatchObject({ room_id: 'room-1', status: 'working' })
  })

  it('keeps a newer assignment when an older request fails', async () => {
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    const pending = deferred<{ data: unknown }>()
    vi.mocked(axios.post)
      .mockReturnValueOnce(pending.promise as never)
      .mockResolvedValueOnce({ data: { id: 'd1', room_id: 'room-3', status: 'working' } })

    const management = useDwellerManagementStore()
    const first = management.assignDwellerToRoom('d1', 'room-2')
    const second = management.assignDwellerToRoom('d1', 'room-3')
    await second
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-3' })
    pending.reject({ response: { status: 400, data: { detail: 'Room is full' } } })
    await expect(first).rejects.toBeTruthy()
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-3', status: 'working' })
  })

  it('restores the confirmed room when overlapping assignments both fail', async () => {
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    const first = deferred<{ data: unknown }>()
    const second = deferred<{ data: unknown }>()
    vi.mocked(axios.post)
      .mockReturnValueOnce(first.promise as never)
      .mockReturnValueOnce(second.promise as never)

    const management = useDwellerManagementStore()
    const firstCall = management.assignDwellerToRoom('d1', 'room-2')
    const secondCall = management.assignDwellerToRoom('d1', 'room-3')
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-3' })
    first.reject({ response: { status: 400, data: { detail: 'Room 2 is full' } } })
    second.reject({ response: { status: 400, data: { detail: 'Room 3 is full' } } })
    await expect(firstCall).rejects.toBeTruthy()
    await expect(secondCall).rejects.toBeTruthy()
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-1', status: 'idle' })
  })

  it('patches the detail room optimistically', async () => {
    const filter = useDwellerFilterStore()
    const roomStore = useRoomStore()
    roomStore.rooms = [{ id: 'room-2', name: 'Diner' }] as never
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    filter.detailedDwellers.d1 = { id: 'd1', room: { id: 'room-1' } } as never
    const pending = deferred<{ data: unknown }>()
    vi.mocked(axios.post).mockReturnValueOnce(pending.promise as never)

    const call = useDwellerManagementStore().assignDwellerToRoom('d1', 'room-2')
    expect(filter.detailedDwellers.d1?.room?.id).toBe('room-2')
    pending.resolve({ data: { id: 'd1', room_id: 'room-2', status: 'working' } })
    await call
  })

  it('does not restore cached detail after the session changes', async () => {
    const auth = useAuthStore()
    auth.token = 'token-1'
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    filter.detailedDwellers.d1 = { id: 'd1', room_id: 'room-1' } as never
    const pending = deferred<{ data: unknown }>()
    vi.mocked(axios.post).mockReturnValueOnce(pending.promise as never)

    const call = useDwellerManagementStore().assignDwellerToRoom('d1', 'room-2')
    auth.token = 'token-2'
    pending.reject({ response: { status: 400, data: { detail: 'Room is full' } } })
    await expect(call).rejects.toBeTruthy()
    expect(filter.detailedDwellers.d1).toBeUndefined()
  })

  it('ignores a previous session success when a later assignment fails', async () => {
    const auth = useAuthStore()
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    const stale = deferred<{ data: unknown }>()
    vi.mocked(axios.post).mockReturnValueOnce(stale.promise as never)

    const management = useDwellerManagementStore()
    const staleCall = management.assignDwellerToRoom('d1', 'room-old')
    auth.sessionGeneration += 1
    stale.resolve({ data: { id: 'd1', room_id: 'room-old', status: 'working' } })
    await staleCall
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'idle' }] as never
    vi.mocked(axios.post).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'Room is full' } },
    })
    await expect(management.assignDwellerToRoom('d1', 'room-new')).rejects.toBeTruthy()
    expect(filter.dwellers[0]).toMatchObject({ room_id: 'room-1', status: 'idle' })
  })

  it('clears the room before the unassign response arrives', async () => {
    const filter = useDwellerFilterStore()
    filter.dwellers = [{ id: 'd1', room_id: 'room-1', status: 'working' }] as never
    filter.allDwellers = [{ id: 'd1', room_id: 'room-1', status: 'working' }] as never
    const pending = deferred<{ data: unknown }>()
    vi.mocked(axios.put).mockReturnValueOnce(pending.promise as never)

    const call = useDwellerManagementStore().unassignDwellerFromRoom('d1')
    expect(filter.dwellers[0]).toMatchObject({ room_id: null, status: 'idle' })
    expect(filter.allDwellers[0]).toMatchObject({ room_id: null, status: 'idle' })
    pending.resolve({ data: { id: 'd1', room_id: null, status: 'idle' } })
    await call
    expect(filter.dwellers[0]).toMatchObject({ room_id: null, status: 'idle' })
    expect(filter.allDwellers[0]).toMatchObject({ room_id: null, status: 'idle' })
  })

  it('plays the card drop sound when a dweller is unassigned from a room', async () => {
    const managementStore = useDwellerManagementStore()
    vi.mocked(axios.put).mockResolvedValue({
      data: { id: 'dweller-1', room_id: null, status: 'idle' },
    })

    const result = await managementStore.unassignDwellerFromRoom('dweller-1')
    expect(result).toEqual({ id: 'dweller-1', room_id: null, status: 'idle' })
    expect(audioManager.play).toHaveBeenCalledWith('cardDrop', 'ui')
  })

  it('removes a soft-deleted dweller from the vault roster too', async () => {
    const filter = useDwellerFilterStore()
    const gone = { id: 'd1', room_id: null, status: 'idle' }
    filter.dwellers = [gone] as never
    filter.allDwellers = [gone] as never
    vi.mocked(axios.post).mockResolvedValueOnce({ data: { id: 'd1' } })

    await useDwellerManagementStore().softDeleteDweller('d1')
    expect(filter.dwellers).toEqual([])
    expect(filter.allDwellers).toEqual([])
  })

  it.each([
    [
      'rename',
      'patch',
      (store: ReturnType<typeof useDwellerManagementStore>) =>
        store.renameDweller('d1', 'Jane', 'Smith'),
      'Name already taken',
      'Failed to rename dweller d1: Name already taken',
    ],
    [
      'bulk unassign',
      'post',
      (store: ReturnType<typeof useDwellerManagementStore>) => store.unassignAllDwellers('vault-1'),
      'Vault is locked down',
      'Failed to unassign all dwellers for vault vault-1: Vault is locked down',
    ],
    [
      'bulk auto-assign',
      'post',
      (store: ReturnType<typeof useDwellerManagementStore>) =>
        store.autoAssignProductionDwellers('vault-1'),
      'No eligible dwellers',
      'Failed to auto-assign dwellers to production rooms for vault vault-1: No eligible dwellers',
    ],
  ] as [string, 'patch' | 'post', (store: never) => Promise<unknown>, string, string][])(
    'emits one toast with the backend detail when %s fails',
    async (_, method, invoke, detail, message) => {
      vi.mocked(axios[method]).mockRejectedValueOnce({
        response: { status: 400, data: { detail } },
      })

      const result = await invoke(useDwellerManagementStore() as never)

      expect(result).toBeNull()
      expect(mockToast.error).toHaveBeenCalledTimes(1)
      expect(mockToast.error).toHaveBeenCalledWith(message)
    }
  )
})

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}
