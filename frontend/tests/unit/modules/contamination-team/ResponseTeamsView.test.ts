import { describe, it, expect, vi, beforeEach, afterEach } from 'vite-plus/test'
import { reactive } from 'vue'
import { enableAutoUnmount, flushPromises } from '@vue/test-utils'
import { mountWithSetup } from '../../helpers/mountWithSetup'
import ResponseTeamsView from '@/modules/contamination-team/views/ResponseTeamsView.vue'
import { useRoomStore } from '@/modules/rooms/stores/room'

const routeState = reactive({ params: { id: 'vault-1' }, path: '/vault/vault-1/response-teams' })
const mockReplace = vi.fn()
enableAutoUnmount(afterEach)

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const mockToast = { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRoute: () => routeState,
    useRouter: () => ({ replace: mockReplace }),
  }
})

vi.mock('@/modules/rooms/stores/room', () => ({ useRoomStore: vi.fn() }))

type RoomStub = { id: string; category: string }

let returnedRooms: RoomStub[] = []
const storeState = {
  rooms: [] as RoomStub[],
  roomsLoadedVaultId: null as string | null,
  fetchRooms: vi.fn(),
}

describe('ResponseTeamsView (compatibility redirect)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeState.params.id = 'vault-1'
    returnedRooms = []
    storeState.rooms = []
    storeState.roomsLoadedVaultId = null
    storeState.fetchRooms.mockImplementation(async (id: string) => {
      storeState.rooms = [...returnedRooms]
      storeState.roomsLoadedVaultId = id
      return 'loaded'
    })
    vi.mocked(useRoomStore).mockReturnValue(storeState as never)
  })

  it('opens the vault station room when the vault has one', async () => {
    returnedRooms = [{ id: 'station-1', category: 'response' }]

    mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(storeState.fetchRooms).toHaveBeenCalledWith('vault-1', 'test-token')
    expect(mockReplace).toHaveBeenCalledWith({
      path: '/vault/vault-1',
      query: { roomId: 'station-1' },
    })
    expect(mockToast.info).not.toHaveBeenCalled()
  })

  it('redirects into the vault and explains the requirement when no station exists', async () => {
    returnedRooms = [{ id: 'r1', category: 'production' }]

    mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(mockToast.info).toHaveBeenCalledTimes(1)
    expect(mockReplace).toHaveBeenCalledWith({ path: '/vault/vault-1', query: {} })
  })

  it('renders no second management surface', async () => {
    returnedRooms = [{ id: 'station-1', category: 'response' }]

    const wrapper = mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Response Teams')
    expect(wrapper.find('a.nav-item').exists()).toBe(false)
  })

  it('reports a failed room load instead of claiming the vault has no station', async () => {
    storeState.fetchRooms.mockImplementation(async () => {
      storeState.rooms = []
      storeState.roomsLoadedVaultId = null
      return 'failed'
    })

    mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(mockToast.error).not.toHaveBeenCalled()
    expect(mockToast.info).not.toHaveBeenCalled()
    expect(mockReplace).toHaveBeenCalledWith({ path: '/vault/vault-1' })
  })

  it('retries a superseded load instead of reporting an error', async () => {
    returnedRooms = [{ id: 'station-1', category: 'response' }]
    let calls = 0
    storeState.fetchRooms.mockImplementation(async (id: string) => {
      calls += 1
      if (calls === 1) return 'superseded'
      storeState.rooms = [...returnedRooms]
      storeState.roomsLoadedVaultId = id
      return 'loaded'
    })

    mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(storeState.fetchRooms).toHaveBeenCalledTimes(2)
    expect(mockToast.error).not.toHaveBeenCalled()
    expect(mockReplace).toHaveBeenCalledWith({
      path: '/vault/vault-1',
      query: { roomId: 'station-1' },
    })
  })

  it('keeps retrying a superseded load without surfacing an error', async () => {
    returnedRooms = [{ id: 'r1', category: 'production' }]
    storeState.fetchRooms.mockImplementation(async (id: string) => {
      storeState.rooms = [...returnedRooms]
      storeState.roomsLoadedVaultId = id
      return 'superseded'
    })

    mountWithSetup(ResponseTeamsView)
    await flushPromises()

    expect(mockToast.error).not.toHaveBeenCalled()
    expect(mockReplace).toHaveBeenCalledWith({ path: '/vault/vault-1', query: {} })
  })
})
