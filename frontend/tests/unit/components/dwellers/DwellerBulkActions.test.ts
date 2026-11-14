import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import DwellerBulkActions from '@/modules/dwellers/components/DwellerBulkActions.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useRoomStore } from '@/modules/rooms/stores/room'

vi.mock('@iconify/vue', () => createIconifyMock())

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

function mountToolbar() {
  return mount(DwellerBulkActions, { props: { vaultId: 'vault-1' } })
}

function counts(wrapper: ReturnType<typeof mountToolbar>): string[] {
  return wrapper.findAll('.action-count').map((element) => element.text())
}

describe('DwellerBulkActions counts', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('counts the unfiltered roster, not the narrowed view', () => {
    const { filter } = useDwellerStore()
    filter.allDwellers = [idle({ id: 'a' }), idle({ id: 'b' })]
    filter.allDwellersLoadedVaultId = 'vault-1'
    filter.dwellers = [idle({ id: 'a' })] as never

    expect(counts(mountToolbar())).toEqual(['2', '2'])
  })

  it('counts youth apprentices for the runs that place them', () => {
    const { filter } = useDwellerStore()
    const roomStore = useRoomStore()
    roomStore.rooms = [
      { id: 'training-room', category: 'training' },
      { id: 'crafting-room', category: 'crafting' },
    ] as never
    filter.allDwellers = [
      idle({ id: 'a' }),
      idle({ id: 'b' }),
      idle({ id: 'teen', age_group: 'teen' }),
    ]
    filter.allDwellersLoadedVaultId = 'vault-1'

    expect(counts(mountToolbar())).toEqual(['3', '3', '2', '2'])
  })

  it('applies the age filter the backend also receives', () => {
    const { filter } = useDwellerStore()
    const roomStore = useRoomStore()
    roomStore.rooms = [
      { id: 'training-room', category: 'training' },
      { id: 'crafting-room', category: 'crafting' },
    ] as never
    filter.allDwellers = [idle({ id: 'a' }), idle({ id: 'teen', age_group: 'teen' })]
    filter.allDwellersLoadedVaultId = 'vault-1'
    filter.filterAgeGroup = 'teen'

    expect(counts(mountToolbar())).toEqual(['1', '1', '0', '0'])
  })
})
