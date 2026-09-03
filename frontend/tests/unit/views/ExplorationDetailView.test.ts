import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ExplorationDetailView from '@/modules/exploration/views/ExplorationDetailView.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

// Mock ExplorationRewardsModal
vi.mock('@/modules/exploration/components/ExplorationRewardsModal.vue', () => ({
  default: {
    name: 'ExplorationRewardsModal',
    template: '<div class="rewards-modal-mock" v-if="show"></div>',
    props: ['show', 'rewards', 'dwellerName'],
    emits: ['close'],
  },
}))

// Mock useToast
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
}))

// Mock usePolling - call immediate fn once, no interval
vi.mock('@/core/composables/usePolling', () => ({
  usePolling: (fn: () => unknown) => ({
    run: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    isActive: { value: false },
    isRefreshing: { value: false },
  }),
}))

describe('ExplorationDetailView', () => {
  let router: ReturnType<typeof createRouter>
  let explorationStore: ReturnType<typeof useExplorationStore>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let authStore: ReturnType<typeof useAuthStore>
  let vaultStore: ReturnType<typeof useVaultStore>

  const mockExploration = {
    id: 'expl-1',
    vault_id: 'test-vault',
    dweller_id: 'dweller-1',
    status: 'active',
    duration: 4,
    start_time: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    end_time: null,
    events: [
      {
        type: 'combat',
        description: 'A raider attacked.',
        timestamp: '2026-01-01T00:00:00Z',
        time_elapsed_hours: 1.25,
      },
      {
        type: 'loot',
        description: 'Found a medkit.',
        timestamp: '2026-01-01T00:00:00Z',
        time_elapsed_hours: 2.0,
      },
    ],
    loot_collected: [],
    total_distance: 15,
    total_caps_found: 42,
    enemies_encountered: 3,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    dweller_strength: 5,
    dweller_perception: 4,
    dweller_endurance: 3,
    dweller_charisma: 2,
    dweller_intelligence: 6,
    dweller_agility: 4,
    dweller_luck: 3,
    stimpaks: 2,
    radaways: 1,
  }

  const mockDweller = {
    id: 'dweller-1',
    first_name: 'Amata',
    last_name: 'Almodovar',
    level: 5,
    health: 42,
    max_health: 50,
    radiation: 0,
    happiness: 75,
    image_url: 'example.com/amata.png',
    thumbnail_url: null,
    room_id: null,
    status: 'exploring',
    is_adult: true,
    age_group: 'adult',
    gender: 'female',
    birth_date: null,
    strength: 5,
    perception: 4,
    endurance: 3,
    charisma: 2,
    intelligence: 6,
    agility: 4,
    luck: 3,
    partner_id: null,
    parent_1_id: null,
    parent_2_id: null,
  }

  beforeEach(async () => {
    setActivePinia(createPinia())
    explorationStore = useExplorationStore()
    dwellerStore = useDwellerStore().filter
    authStore = useAuthStore()
    vaultStore = useVaultStore()

    // Mock store methods
    vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue([mockExploration])
    vi.spyOn(explorationStore, 'fetchExplorationDetails').mockResolvedValue(mockExploration)
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(mockDweller)
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue([])
    vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue({} as any)
    // The view opens a live SSE stream on mount; keep that off the network.
    vi.spyOn(explorationStore, 'startSseSubscription').mockImplementation(() => {})
    vi.spyOn(explorationStore, 'stopSseSubscription').mockImplementation(() => {})

    // Set up mock data
    explorationStore.activeExplorations['expl-1'] = mockExploration
    dwellerStore.dwellers = [mockDweller]
    dwellerStore.detailedDwellers['dweller-1'] = mockDweller as any
    authStore.token = 'mock-token'

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/vault/:id/exploration/:explorationId',
          component: ExplorationDetailView,
          name: 'exploration-detail',
        },
        {
          path: '/vault/:id/exploration',
          name: 'exploration',
          component: { template: '<div>Exploration List</div>' },
        },
      ],
    })

    router.push('/vault/test-vault/exploration/expl-1')
    await router.isReady()
  })

  describe('Rendering', () => {
    it('renders navbar with explorer counter', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('1 / 1')
      expect(wrapper.text()).toContain('Back to Exploration')
      expect(wrapper.find('.explorer-navigation').classes()).toContain('w-full')
      expect(wrapper.find('.exploration-detail-content').classes()).toContain('max-w-[1200px]')
    })

    it('renders the shared vault sidebar', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.findComponent({ name: 'SidePanel' }).exists()).toBe(true)
    })

    it('renders dweller name in summary card', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Amata Almodovar')
    })

    it('renders the same dweller portrait used by exploration cards', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.find('.dweller-portrait').attributes('src')).toBe('http://example.com/amata.png')
      expect(wrapper.find('.dweller-portrait').attributes('alt')).toBe('Amata Almodovar portrait')
    })

    it('uses the thumbnail when a detailed dweller has a blank image URL', async () => {
      dwellerStore.detailedDwellers['dweller-1'] = {
        ...mockDweller,
        image_url: '',
        thumbnail_url: 'example.com/amata-thumb.png',
      } as any
      dwellerStore.dwellers = [dwellerStore.detailedDwellers['dweller-1']]

      const wrapper = mount(ExplorationDetailView, { global: { plugins: [router] } })
      await flushPromises()

      expect(wrapper.find('.dweller-portrait').attributes('src')).toBe('http://example.com/amata-thumb.png')
    })

    it('renders dweller level', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('LVL 5')
    })

    it('uses the shared bar for health and the terminal meter for exploration progress', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.findAll('.u-progress-bar').length).toBeGreaterThanOrEqual(1)
      expect(wrapper.findAll('.exploration-meter')).toHaveLength(1)
      expect(wrapper.findAll('.exploration-meter__fill.rounded-full')).toHaveLength(1)
    })

    it('renders stats grid with 6 stat boxes', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Miles')
      expect(wrapper.text()).toContain('Items')
      expect(wrapper.text()).toContain('Caps')
      expect(wrapper.text()).toContain('Stimpaks')
      expect(wrapper.text()).toContain('RadAway')
      expect(wrapper.text()).toContain('Enemies')
    })

    it('renders event log with events', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Event Log')
      expect(wrapper.text()).toContain('A raider attacked.')
      expect(wrapper.text()).toContain('Found a medkit.')
      expect(wrapper.find('.event-log-section').classes()).toContain('mt-4')
    })

    it('renders the HP trend for legacy damage descriptions without structured health data', async () => {
      explorationStore.activeExplorations['expl-1'] = {
        ...mockExploration,
        events: [
          {
            type: 'danger',
            description: 'Encountered toxic waste. Health reduced by 7.',
            timestamp: '2026-01-01T00:00:00Z',
            time_elapsed_hours: 1,
          },
          {
            type: 'item_use',
            description: 'Used a stimpak. Healed 5 health.',
            timestamp: '2026-01-01T00:30:00Z',
            time_elapsed_hours: 1.5,
          },
        ],
      }

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.find('.health-trend').exists()).toBe(true)
      expect(wrapper.find('.health-trend').classes()).toContain('mt-4')
      expect(wrapper.find('.health-sparkline-frame').classes()).toContain('border')
      expect(wrapper.find('.health-sparkline-frame svg').classes()).toContain('w-[240px]')
      expect(wrapper.text()).toContain('-7')
      expect(wrapper.text()).toContain('+5')
      expect(wrapper.find('.health-trend .text-theme-primary').exists()).toBe(true)
    })

    it('renders action buttons', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Recall Dweller')
      // progress < 100% so Complete button should not be visible
      expect(wrapper.text()).not.toContain('Complete Exploration')
    })
  })

  describe('Loading State', () => {
    it('renders after a direct link loads only the detailed dweller record', async () => {
      dwellerStore.dwellers = []

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Amata Almodovar')
      expect(wrapper.text()).not.toContain('Loading exploration data...')
    })

    it('renders loading state when no exploration data', async () => {
      // Remove exploration from activeExplorations
      delete explorationStore.activeExplorations['expl-1']
      dwellerStore.dwellers = []

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Loading exploration data...')
      expect(wrapper.find('.loading-state').exists()).toBe(true)
    })
  })

  describe('Empty / no events', () => {
    it('renders empty event log message when no events', async () => {
      explorationStore.activeExplorations['expl-1'] = {
        ...mockExploration,
        events: [],
      }

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('No events yet')
    })
  })

  describe('Short-schema exploration (missing loot_collected)', () => {
    it('renders without crashing when loot_collected is undefined', async () => {
      const { loot_collected: _omit, ...shortExploration } = mockExploration
      explorationStore.activeExplorations['expl-1'] = shortExploration as typeof mockExploration

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      // Should render the summary card, not throw / blank out
      expect(wrapper.text()).toContain('Amata Almodovar')
      expect(wrapper.text()).toContain('Event Log')
      expect(wrapper.find('.loading-state').exists()).toBe(false)
    })
  })
})
