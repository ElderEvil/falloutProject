import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock, createToastMock } from '../../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import UnassignedDwellers from '@/modules/dwellers/components/UnassignedDwellers.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { makeDweller } from '../../helpers/dwellerFixtures'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

// Mock components
vi.mock('@/modules/dwellers/components/stats/DwellerStatusBadge.vue', () => ({
  default: { template: '<div class="status-badge-mock"></div>', props: ['status', 'size'] },
}))

vi.mock('@/modules/dwellers/components/DwellerFilterPanel.vue', () => ({
  default: {
    template: '<div class="filter-panel-mock"><slot name="additional-filters" /></div>',
    props: ['showStatusFilter', 'showAgeFilter'],
  },
}))

// Mock auth service to prevent network calls
vi.mock('@/modules/auth/services/authService', () => ({
  authService: {
    getCurrentUser: vi
      .fn()
      .mockResolvedValue({ data: { id: 'user-1', email: 'test@example.com' } }),
    login: vi.fn(),
    register: vi.fn(),
    refreshToken: vi.fn(),
    logout: vi.fn(),
  },
}))

// Mock toast composable
const mockToast = createToastMock()

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

const mockDweller = makeDweller({
  id: 'dweller-1',
  first_name: 'John',
  last_name: 'Doe',
  room_id: null,
})

// Consistent drag payload for the room -> unassigned drop path.
const dropEvent = (currentRoomId: string | null) => ({
  dataTransfer: {
    getData: () =>
      JSON.stringify({ dwellerId: 'dweller-1', firstName: 'John', lastName: 'Doe', currentRoomId }),
  },
})

describe('UnassignedDwellers', () => {
  let dwellerStore: any
  let dwellerManagementStore: any

  beforeEach(() => {
    setActivePinia(createPinia())
    const stores = useDwellerStore()
    dwellerStore = stores.filter
    dwellerManagementStore = stores.management
    useAuthStore().token = 'mock-token'
    dwellerStore.dwellers = []
    dwellerManagementStore.unassignDwellerFromRoom = vi.fn().mockResolvedValue(undefined)
    vi.clearAllMocks()
  })

  const mountPanel = (dwellers: any[] = []) => {
    dwellerStore.dwellers = dwellers
    return mount(UnassignedDwellers)
  }

  const isOpen = (wrapper: ReturnType<typeof mount>) =>
    (wrapper.get('details').element as HTMLDetailsElement).open

  const clickChip = async (wrapper: ReturnType<typeof mount>, label: string) => {
    const chip = wrapper.findAll('.filter-chip').find((c) => c.text() === label)
    expect(chip).toBeTruthy()
    await chip!.trigger('click')
  }

  describe('rendering', () => {
    it('renders the panel header and description', () => {
      const wrapper = mountPanel()

      expect(wrapper.text()).toContain('Unassigned Dwellers')
      expect(wrapper.text()).toContain('Drag dwellers here to unassign them from rooms')
    })

    it('shows the empty state when no unassigned dwellers', () => {
      const wrapper = mountPanel()

      expect(wrapper.text()).toContain('All dwellers are assigned!')
      expect(wrapper.find('.count-badge').text()).toBe('0')
    })

    it('renders a card with name, level and every SPECIAL stat', () => {
      const wrapper = mountPanel([mockDweller])

      expect(wrapper.find('.count-badge').text()).toBe('1')
      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Lv 5')
      expect(wrapper.findAll('.stat-label').map((label) => label.text())).toEqual([
        'S',
        'P',
        'E',
        'C',
        'I',
        'A',
        'L',
      ])
    })

    it('renders one card per unassigned dweller and counts them', () => {
      const wrapper = mountPanel([
        mockDweller,
        { ...mockDweller, id: 'dweller-2', first_name: 'Jane', last_name: 'Smith' },
        { ...mockDweller, id: 'dweller-3' },
      ])

      expect(wrapper.findAll('.dweller-card')).toHaveLength(3)
      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Jane Smith')
      expect(wrapper.find('.count-badge').text()).toBe('3')
    })
  })

  describe('collapsed panel', () => {
    it('keeps the panel collapsed and the count current when dwellers refresh', async () => {
      const wrapper = mountPanel([mockDweller])
      const summary = wrapper.get('summary')

      await summary.trigger('click')
      expect(isOpen(wrapper)).toBe(false)
      expect(wrapper.get('.dweller-card').isVisible()).toBe(false)
      expect(wrapper.get('.filter-panel-mock').isVisible()).toBe(false)

      dwellerStore.dwellers = [mockDweller, { ...mockDweller, id: 'dweller-2' }]
      await flushPromises()
      expect(isOpen(wrapper)).toBe(false)
      expect(summary.get('.count-badge').text()).toBe('2')

      await summary.trigger('click')
      expect(wrapper.get('.dweller-card').isVisible()).toBe(true)
      expect(wrapper.get('.filter-panel-mock').isVisible()).toBe(true)
    })

    it('unassigns room dwellers dropped on the collapsed header', async () => {
      const wrapper = mountPanel()
      expect(isOpen(wrapper)).toBe(false)

      await wrapper.get('summary').trigger('drop', dropEvent('room-1'))
      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).toHaveBeenCalledExactlyOnceWith(
        'dweller-1'
      )
      expect(mockToast.success).toHaveBeenCalledWith('John Doe unassigned from room')
      expect(isOpen(wrapper)).toBe(false)
    })

    it('starts collapsed when empty and unfolds when a dweller needs assigning', async () => {
      const wrapper = mountPanel()
      expect(isOpen(wrapper)).toBe(false)

      dwellerStore.dwellers = [mockDweller]
      await flushPromises()
      expect(isOpen(wrapper)).toBe(true)

      dwellerStore.dwellers = []
      await flushPromises()
      expect(isOpen(wrapper)).toBe(false)
    })

    it('unfolds on drag-over so the drop zone can catch the dweller', async () => {
      const wrapper = mountPanel()
      expect(isOpen(wrapper)).toBe(false)

      await wrapper.get('details').trigger('dragover', { dataTransfer: { dropEffect: '' } })
      expect(isOpen(wrapper)).toBe(true)
    })

    it('stays open on a zero-match filter so its own controls keep working', async () => {
      const wrapper = mountPanel([mockDweller])
      expect(isOpen(wrapper)).toBe(true)

      await clickChip(wrapper, 'Legendary')

      expect(isOpen(wrapper)).toBe(true)
      expect(wrapper.text()).toContain('No dwellers match the filters')
    })
  })

  describe('filtering', () => {
    it.each([
      ['an assigned dweller', { room_id: 'room-1' }],
      ['an exploring dweller', { status: 'exploring' }],
      ['a questing dweller', { status: 'questing' }],
    ])('filters out %s', (_name, patch) => {
      const wrapper = mountPanel([{ ...mockDweller, ...patch }])

      expect(wrapper.find('.dweller-card').exists()).toBe(false)
      expect(wrapper.text()).toContain('All dwellers are assigned!')
    })

    const adultDweller = {
      ...mockDweller,
      id: 'dweller-adult',
      first_name: 'Ada',
      age_group: 'adult',
      rarity: 'legendary',
    }
    const childDweller = {
      ...mockDweller,
      id: 'dweller-child',
      first_name: 'Tim',
      age_group: 'child',
      rarity: 'common',
    }

    it('renders rarity filter chips', () => {
      const wrapper = mountPanel([mockDweller])

      expect(wrapper.findAll('.filter-chip').map((c) => c.text())).toContain('Legendary')
      expect(wrapper.find('.filter-group .filter-group-label').exists()).toBe(true)
      expect(wrapper.find('.filter-group .filter-options').exists()).toBe(true)
    })

    it('filters cards by the shared age preference', () => {
      dwellerStore.setFilterAgeGroup('adult')
      const wrapper = mountPanel([adultDweller, childDweller])

      const cards = wrapper.findAll('.dweller-card')
      expect(cards.length).toBe(1)
      expect(cards[0].text()).toContain('Ada')
    })

    it('filters cards by rarity', async () => {
      const wrapper = mountPanel([adultDweller, childDweller])

      await clickChip(wrapper, 'Legendary')

      const cards = wrapper.findAll('.dweller-card')
      expect(cards.length).toBe(1)
      expect(cards[0].text()).toContain('Ada')
    })

    it('shows a filtered-out message instead of the all-assigned state', () => {
      dwellerStore.setFilterAgeGroup('child')
      const wrapper = mountPanel([adultDweller])

      expect(wrapper.text()).toContain('No dwellers match the filters')
      expect(wrapper.text()).not.toContain('All dwellers are assigned!')
    })

    it('tints the avatar ring by rarity', () => {
      const wrapper = mountPanel([adultDweller])

      expect(wrapper.find('.dweller-avatar').attributes('style')).toContain('--rarity-ring')
    })
  })

  describe('drag and drop', () => {
    it('makes dweller cards draggable and emits dragStart/dragEnd', async () => {
      const wrapper = mountPanel([mockDweller])
      const card = wrapper.find('.dweller-card')
      expect(card.attributes('draggable')).toBe('true')

      await card.trigger('dragstart', {
        dataTransfer: { effectAllowed: '', setData: vi.fn() },
      })
      expect(wrapper.emitted('dragStart')![0][0]).toMatchObject({ id: mockDweller.id })

      await card.trigger('dragend')
      expect(wrapper.emitted('dragEnd')).toHaveLength(1)
    })

    it('shows drop overlay when dragging over', async () => {
      const wrapper = mountPanel([mockDweller])

      await wrapper.find('.dweller-grid-container').trigger('dragover', {
        dataTransfer: { dropEffect: '' },
      })
      await flushPromises()

      expect(wrapper.find('.drop-overlay').exists()).toBe(true)
      expect(wrapper.text()).toContain('Drop to unassign')
    })

    it.each([false, true])(
      'keeps the drop hint active across panel children (populated=%s)',
      async (populated) => {
        const wrapper = mountPanel(populated ? [mockDweller] : [])
        const area = wrapper.get(populated ? '.dweller-grid-container' : '.empty-state')
        await area.trigger('dragover', { dataTransfer: { dropEffect: '' } })
        expect(wrapper.text()).toContain('Drop to unassign')

        await area.trigger('dragleave', { relatedTarget: wrapper.get('summary').element })
        expect(wrapper.text()).toContain('Drop to unassign')

        await wrapper.get('details').trigger('dragleave', { relatedTarget: document.body })
        expect(wrapper.text()).not.toContain('Drop to unassign')
      }
    )

    it('unassigns the dropped dweller and confirms it', async () => {
      const wrapper = mountPanel()

      await wrapper.find('.empty-state').trigger('drop', dropEvent('room-1'))
      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).toHaveBeenCalledExactlyOnceWith(
        'dweller-1'
      )
      expect(mockToast.success).toHaveBeenCalledWith('John Doe unassigned from room')
    })

    it('does not unassign a dweller that has no room', async () => {
      const wrapper = mountPanel()

      await wrapper.find('.empty-state').trigger('drop', dropEvent(null))
      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).not.toHaveBeenCalled()
    })

    it('reports an unassign failure instead of a success', async () => {
      dwellerManagementStore.unassignDwellerFromRoom = vi
        .fn()
        .mockRejectedValue(new Error('Unassign failed'))
      const wrapper = mountPanel()

      await wrapper.find('.empty-state').trigger('drop', dropEvent('room-1'))
      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).toHaveBeenCalledWith('dweller-1')
      expect(mockToast.error).toHaveBeenCalledWith('Failed to unassign dweller')
    })
  })
})
