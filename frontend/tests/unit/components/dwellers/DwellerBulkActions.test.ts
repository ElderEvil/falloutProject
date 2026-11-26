import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createAxiosMock, createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
import axios from '@/core/plugins/axios'
import DwellerBulkActions from '@/modules/dwellers/components/DwellerBulkActions.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useRoomStore } from '@/modules/rooms/stores/room'

vi.mock('@iconify/vue', () => createIconifyMock())
vi.mock('@/core/plugins/axios', () => createAxiosMock())

vi.mock('@/core/components/ui/tooltip', () => {
  const passthrough = { template: '<div><slot /></div>' }
  return {
    Tooltip: passthrough,
    TooltipContent: passthrough,
    TooltipProvider: passthrough,
    TooltipTrigger: passthrough,
  }
})

const idle = (overrides: Record<string, unknown> = {}) =>
  ({ id: 'dweller', status: 'idle', room_id: null, age_group: 'adult', ...overrides }) as never

const mountToolbar = () => mount(DwellerBulkActions, { props: { vaultId: 'vault-1' } })

const counts = (wrapper: ReturnType<typeof mountToolbar>): string[] =>
  wrapper.findAll('.action-count').map((element) => element.text())

describe('DwellerBulkActions counts', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const seedRooms = () => {
    useRoomStore().rooms = [
      { id: 'training-room', category: 'training' },
      { id: 'crafting-room', category: 'crafting' },
    ] as never
  }

  it.each([
    [
      'the unfiltered roster rather than the narrowed view',
      () => {
        const { filter } = useDwellerStore()
        filter.allDwellers = [idle({ id: 'a' }), idle({ id: 'b' })]
        filter.dwellers = [idle({ id: 'a' })] as never
      },
      ['2', '2'],
    ],
    [
      'youth apprentices for the runs that place them',
      () => {
        seedRooms()
        useDwellerStore().filter.allDwellers = [
          idle({ id: 'a' }),
          idle({ id: 'b' }),
          idle({ id: 'teen', age_group: 'teen' }),
        ]
      },
      ['3', '3', '2', '2'],
    ],
    [
      'the age filter the backend also receives',
      () => {
        seedRooms()
        const { filter } = useDwellerStore()
        filter.allDwellers = [idle({ id: 'a' }), idle({ id: 'teen', age_group: 'teen' })]
        filter.filterAgeGroup = 'teen'
      },
      ['1', '1', '0', '0'],
    ],
  ] as const)('counts %s', (_name, seed, expected) => {
    seed()
    const { filter } = useDwellerStore()
    filter.allDwellersLoadedVaultId = 'vault-1'

    expect(counts(mountToolbar())).toEqual([...expected])
  })

  it('drops the count immediately after a single assignment from the full roster', async () => {
    const { filter, management } = useDwellerStore()
    filter.dwellers = [idle({ id: 'a' }), idle({ id: 'b' })] as never
    filter.allDwellers = [idle({ id: 'a' }), idle({ id: 'b' })]
    filter.allDwellersLoadedVaultId = 'vault-1'
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { id: 'a', room_id: 'room-1', status: 'working' },
    })

    const wrapper = mountToolbar()
    expect(counts(wrapper)).toEqual(['2', '2'])

    await management.assignDwellerToRoom('a', 'room-1')
    await nextTick()

    expect(counts(wrapper)).toEqual(['1', '1'])
  })
})
