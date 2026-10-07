import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createIconifyMock, createToastMock } from '../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ExplorationDetailView from '@/modules/exploration/views/ExplorationDetailView.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import HealthRadiationBar from '@/core/components/common/HealthRadiationBar.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useExpeditionSiteStore } from '@/modules/exploration/stores/expeditionSite'
import ExpeditionSiteModal from '@/modules/exploration/components/ExpeditionSiteModal.vue'
import type { AvailableSiteView, SiteRoomView } from '@/modules/exploration/api/expeditionSite'

// Mock Iconify
vi.mock('@iconify/vue', () => createIconifyMock())

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
const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
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

const soundMock = vi.hoisted(() => ({
  playMusic: vi.fn(),
  playSound: vi.fn(),
  stopMusic: vi.fn(),
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => soundMock,
}))

describe('ExplorationDetailView', () => {
  let router: ReturnType<typeof createRouter>
  let explorationStore: ReturnType<typeof useExplorationStore>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let authStore: ReturnType<typeof useAuthStore>
  let vaultStore: ReturnType<typeof useVaultStore>
  let siteStore: ReturnType<typeof useExpeditionSiteStore>

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
    siteStore = useExpeditionSiteStore()

    // Mock store methods
    vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue([mockExploration])
    vi.spyOn(explorationStore, 'fetchExplorationDetails').mockResolvedValue(mockExploration)
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(mockDweller)
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue([])
    vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue({} as any)
    // The view opens a live SSE stream on mount; keep that off the network.
    vi.spyOn(explorationStore, 'startSseSubscription').mockImplementation(() => {})
    vi.spyOn(explorationStore, 'stopSseSubscription').mockImplementation(() => {})
    // Both actions are stubbed so the store's scope-reset never clears this
    // snapshot; a non-empty default keeps the CTA enabled unless a test empties it.
    const availableSite = {
      id: 'site-1',
      name: 'Test Site',
      flavor: 'A test site.',
      min_dweller_level: 1,
      room_total: 3,
    }
    siteStore.availableSites = [availableSite]
    vi.spyOn(siteStore, 'fetchCurrentRoom').mockResolvedValue(null)
    vi.spyOn(siteStore, 'fetchAvailableSites').mockResolvedValue([availableSite])

    // Set up mock data
    authStore.token = 'mock-token'
    explorationStore.activeExplorations['expl-1'] = mockExploration
    dwellerStore.dwellers = [mockDweller]
    dwellerStore.detailedDwellers['dweller-1'] = mockDweller as any

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
    it('plays exploration music on mount and restores the vault loop on unmount', async () => {
      soundMock.playMusic.mockClear()
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(soundMock.playMusic).toHaveBeenCalledWith('exploration')

      wrapper.unmount()
      expect(soundMock.playMusic).toHaveBeenCalledWith('vaultAmbient')
    })

    it('renders navbar with explorer counter', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('1 / 1')
      expect(wrapper.text()).toContain('Back to Exploration')
      expect(wrapper.find('.explorer-navigation').exists()).toBe(true)
      expect(wrapper.find('.exploration-detail-content').exists()).toBe(true)
    })

    it('constrains the header and detail content to the shared 1200px rail', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const rail = wrapper.findComponent(PageContentRail)
      expect(rail.props('width')).toBe('content')
      expect(rail.classes()).toContain('max-w-[1200px]')
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

      expect(wrapper.find('.dweller-portrait').attributes('src')).toBe(
        'http://example.com/amata.png'
      )
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

      expect(wrapper.find('.dweller-portrait').attributes('src')).toBe(
        'http://example.com/amata-thumb.png'
      )
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

      expect(wrapper.findAllComponents(HealthRadiationBar).length).toBeGreaterThanOrEqual(1)

      const meter = wrapper.find('[role="progressbar"][aria-label="Exploration progress"]')
      expect(meter.exists()).toBe(true)
      expect(meter.attributes('aria-valuenow')).toBeDefined()
      expect(wrapper.find('[data-slot="progress-segments"]').exists()).toBe(true)
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

    it('disables the Expedition site CTA when no sites are available', async () => {
      siteStore.availableSites = []
      vi.spyOn(siteStore, 'fetchAvailableSites').mockResolvedValue([])

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const siteButton = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Expedition site'))
      expect((siteButton?.element as HTMLButtonElement).disabled).toBe(true)
    })

    it('keeps the Expedition site CTA enabled when sites are available', async () => {
      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      const siteButton = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Expedition site'))
      expect(siteButton?.attributes('disabled')).toBeUndefined()
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

    it('shows the AT RISK badge from roster vitals before the detailed record loads', async () => {
      // No detailed record yet (the beforeEach one is removed); the roster
      // dweller carries the low-health vitals the badge must surface.
      delete dwellerStore.detailedDwellers['dweller-1']
      dwellerStore.dwellers = [{ ...mockDweller, health: 10 }]

      const wrapper = mount(ExplorationDetailView, {
        global: {
          plugins: [router],
        },
      })

      await flushPromises()

      expect(wrapper.find('[aria-label="Dweller at risk"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('AT RISK')
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

  describe('Site reconnect on explorer switch', () => {
    it('re-scopes the site store and reconnects when the exploration changes', async () => {
      const siteStore = useExpeditionSiteStore()
      const resetSpy = vi.spyOn(siteStore, 'reset')
      const fetchCurrentRoomSpy = vi.spyOn(siteStore, 'fetchCurrentRoom').mockResolvedValue(null)
      vi.spyOn(explorationStore, 'fetchExplorationDetails').mockImplementation(
        async (id: string) => ({
          ...mockExploration,
          id,
        })
      )
      explorationStore.activeExplorations['expl-2'] = { ...mockExploration, id: 'expl-2' }

      const wrapper = mount(ExplorationDetailView, { global: { plugins: [router] } })
      await flushPromises()
      resetSpy.mockClear()
      fetchCurrentRoomSpy.mockClear()

      await router.push('/vault/test-vault/exploration/expl-2')
      await flushPromises()

      expect(resetSpy).toHaveBeenCalled()
      expect(fetchCurrentRoomSpy).toHaveBeenCalledWith('expl-2')
      wrapper.unmount()
    })

    it('does not reopen the modal when the previous explorer reconnect finishes late', async () => {
      const siteStore = useExpeditionSiteStore()
      let finishOld!: (room: SiteRoomView | null) => void
      vi.spyOn(siteStore, 'fetchCurrentRoom')
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              finishOld = resolve
            })
        )
        .mockResolvedValueOnce(null)
      explorationStore.activeExplorations['expl-2'] = { ...mockExploration, id: 'expl-2' }

      const wrapper = mount(ExplorationDetailView, { global: { plugins: [router] } })
      await flushPromises()
      await router.push('/vault/test-vault/exploration/expl-2')
      await flushPromises()
      finishOld({ exploration_id: 'expl-1' } as SiteRoomView)
      await flushPromises()

      expect(wrapper.findComponent(ExpeditionSiteModal).props('show')).toBe(false)
      wrapper.unmount()
    })

    it('does not let a stale site-options response disable the new explorer CTA', async () => {
      const siteStore = useExpeditionSiteStore()
      let resolveFirstSites!: (sites: AvailableSiteView[]) => void
      // First call (expl-1) stays pending; the second (expl-2) rejects.
      vi.spyOn(siteStore, 'fetchAvailableSites')
        .mockImplementationOnce(
          () =>
            new Promise<AvailableSiteView[]>((resolve) => {
              resolveFirstSites = resolve
            })
        )
        .mockRejectedValueOnce(new Error('network failure'))
      vi.spyOn(explorationStore, 'fetchExplorationDetails').mockImplementation(
        async (id: string) => ({
          ...mockExploration,
          id,
        })
      )
      explorationStore.activeExplorations['expl-2'] = { ...mockExploration, id: 'expl-2' }

      const wrapper = mount(ExplorationDetailView, { global: { plugins: [router] } })
      await flushPromises()
      await router.push('/vault/test-vault/exploration/expl-2')
      await flushPromises()

      // The stale expl-1 response lands after the switch; it must not mark the
      // current explorer's options as loaded (which would disable the CTA).
      resolveFirstSites([])
      await flushPromises()

      const siteButton = wrapper
        .findAll('button')
        .find((b) => b.text().includes('Expedition site'))
      expect(siteButton?.attributes('disabled')).toBeUndefined()
      expect((wrapper.vm as any).siteOptionsLoaded).toBe(false)
      wrapper.unmount()
    })
  })
})
