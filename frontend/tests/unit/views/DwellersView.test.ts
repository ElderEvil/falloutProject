import { describe, it, expect, beforeEach, afterEach, vi } from 'vite-plus/test'
import { ref } from 'vue'
import { mount, flushPromises, enableAutoUnmount } from '@vue/test-utils'
import { setActivePinia, createPinia, disposePinia, getActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DwellersView from '@/modules/dwellers/views/DwellersView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import axios from '@/core/plugins/axios'
import type { Room } from '@/modules/rooms/models/room'

vi.mock('@/core/plugins/axios')

enableAutoUnmount((unmount) => {
  afterEach(async () => {
    unmount()
    await flushPromises()
    const pinia = getActivePinia()
    if (pinia) disposePinia(pinia)
    vi.restoreAllMocks()
  })
})

// The auth store refreshes the cached user on boot; resolve it from the seeded
// session so this view test never falls back to a real network call.
vi.mock('@/modules/auth/services/authService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/modules/auth/services/authService')>()
  return {
    ...actual,
    authService: {
      ...actual.authService,
      getCurrentUser: vi.fn(async () => ({
        data: JSON.parse(localStorage.getItem('user') ?? '{}'),
      })),
    },
  }
})

const dweller = (overrides: Record<string, unknown> = {}) => ({
  id: 'dweller-1',
  first_name: 'Test',
  last_name: 'Dweller',
  level: 1,
  health: 100,
  max_health: 100,
  radiation: 0,
  happiness: 80,
  status: 'working',
  age_group: 'adult',
  gender: 'male',
  rarity: 'common',
  room_id: null,
  vault_id: 'vault-1',
  ...overrides,
})

const productionRoom = {
  id: 'garden-1',
  name: 'Garden',
  category: 'production',
  ability: 'agility',
}

describe('DwellersView', () => {
  let router: ReturnType<typeof createRouter>
  let authStore: ReturnType<typeof useAuthStore>
  let dwellerFilter: ReturnType<typeof useDwellerStore>['filter']
  let vaultStore: ReturnType<typeof useVaultStore>
  let roomStore: ReturnType<typeof useRoomStore>
  let incidentStore: ReturnType<typeof useIncidentStore>
  let pinia: ReturnType<typeof createPinia>

  /** Every endpoint the view reads on mount, answered by URL. */
  const mockEndpoints = (dwellers: unknown[] = [], rooms: unknown[] = []) =>
    vi.mocked(axios.get).mockImplementation((url: string) => {
      if (url.includes('/dwellers/identity-options')) {
        return Promise.resolve({ data: { races: [], factions_by_race: {}, states_by_race: {} } })
      }
      if (url.includes('/dwellers/vault/')) return Promise.resolve({ data: dwellers })
      if (url.includes('/incidents')) {
        return Promise.resolve({
          data: { vault_id: 'vault-1', incident_count: 0, incidents: [] },
        })
      }
      if (url.includes('/rooms/vault/')) return Promise.resolve({ data: rooms })
      return Promise.resolve({ data: [] })
    })

  const mockEmptyRoster = () => mockEndpoints([])

  const mountView = async (isFlickering = false, stubs: Record<string, unknown> = {}) => {
    await router.isReady()
    return mount(DwellersView, {
      global: {
        plugins: [router, pinia],
        provide: { isFlickering: ref(isFlickering) },
        stubs,
      },
    })
  }

  /** Mount at a given query string, waiting for the guarded reads to settle. */
  const mountAt = async (query = '', isFlickering = false) => {
    if (query) await router.push(`/vault/vault-1/dwellers${query}`)
    const wrapper = await mountView(isFlickering)
    await flushPromises()
    return wrapper
  }

  const requestUrls = () => vi.mocked(axios.get).mock.calls.map(([url]) => String(url))
  const requested = (fragment: string) => requestUrls().some((url) => url.includes(fragment))

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)

    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 'test-user-id', username: 'testuser', email: 'test@example.com' })
    )

    useAuthStore()
    authStore = useAuthStore()
    dwellerFilter = useDwellerStore().filter
    vaultStore = useVaultStore()
    roomStore = useRoomStore()
    incidentStore = useIncidentStore()

    vaultStore.loadedVaults['vault-1'] = {
      id: 'vault-1',
      number: 101,
      bottle_caps: 1000,
    } as never

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id/dwellers', name: 'dwellers', component: DwellersView },
        {
          path: '/vault/:id/dwellers/:dwellerId',
          name: 'dwellerDetail',
          component: { template: '<div>Dweller Detail</div>' },
        },
        { path: '/vault/:id', component: { template: '<div>Vault View</div>' } },
        {
          path: '/vault/:id/happiness',
          name: 'happiness',
          component: { template: '<div>Happiness</div>' },
        },
        { path: '/dweller/:id/chat', component: { template: '<div>Chat</div>' } },
      ],
    })

    await router.push('/vault/vault-1/dwellers')

    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.clearAllMocks()
  })

  it('hides the identity and age filters while the dead-dweller panel is shown', async () => {
    dwellerFilter.setFilterStatus('dead')
    const wrapper = await mountAt()

    expect(wrapper.find('.identity-controls').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Filter by Age')
  })

  it('restores a room deep link after loading and clears it when the room closes', async () => {
    mockEmptyRoster()
    await router.push('/vault/vault-1/dwellers?roomId=room-1&dweller=dweller-1')
    const wrapper = await mountView(false, {
      RoomDetailModal: {
        name: 'RoomDetailModal',
        props: ['room'],
        emits: ['close'],
        template: `<button @click="$emit('close')">Close room</button>`,
      },
    })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'RoomDetailModal' }).exists()).toBe(false)

    const room = { id: 'room-1', name: 'Power Generator', category: 'production' } as Room
    roomStore.rooms = [room]
    await flushPromises()
    expect(wrapper.findComponent({ name: 'RoomDetailModal' }).exists()).toBe(false)

    await router.replace({ query: { roomId: 'room-1' } })
    await flushPromises()
    const modal = wrapper.findComponent({ name: 'RoomDetailModal' })
    expect(modal.props('room').id).toBe('room-1')

    await modal.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.roomId).toBeUndefined()

    roomStore.rooms = [{ ...room }]
    await flushPromises()
    expect(wrapper.findComponent({ name: 'RoomDetailModal' }).exists()).toBe(false)
    wrapper.unmount()
  })

  describe('Initialization', () => {
    it('fetches the roster and the rooms on mount', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt()

      expect(wrapper.text()).toContain('Dwellers')
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/dwellers/vault/vault-1')
      )
      // Should fetch both dwellers and rooms
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/rooms/vault/vault-1'),
        expect.any(Object)
      )
    })

    it('adopts the vault before starting the guarded data reads', async () => {
      const startedRequests: string[] = []
      const resolvers: Array<() => void> = []
      const deferredRequest = (name: string) => {
        startedRequests.push(name)
        return new Promise<void>((resolve) => resolvers.push(resolve))
      }

      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockImplementation(() => deferredRequest('vault'))
      vi.spyOn(dwellerFilter, 'fetchWithCurrentFilters').mockImplementation(() =>
        deferredRequest('filtered dwellers')
      )
      vi.spyOn(dwellerFilter, 'fetchAllDwellers').mockImplementation(() =>
        deferredRequest('all dwellers')
      )
      vi.spyOn(incidentStore, 'fetchIncidents').mockImplementation(() =>
        deferredRequest('incidents')
      )
      vi.spyOn(roomStore, 'fetchRooms').mockImplementation(() =>
        deferredRequest('rooms').then(() => 'loaded' as const)
      )

      await mountView()
      await flushPromises()

      try {
        expect(startedRequests).toEqual(['vault'])
        resolvers.splice(0).forEach((resolve) => resolve())
        await flushPromises()
        expect(startedRequests).toEqual(
          expect.arrayContaining([
            'vault',
            'filtered dwellers',
            'all dwellers',
            'incidents',
            'rooms',
          ])
        )
      } finally {
        while (resolvers.length > 0) {
          resolvers.splice(0).forEach((resolve) => resolve())
          await flushPromises()
        }
      }
    })

    it('skips the guarded reads when the session changes while adopting the vault', async () => {
      const reads: string[] = []
      let resolveVault!: () => void
      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockImplementation(
        () =>
          new Promise<void>((resolve) => {
            resolveVault = resolve
          })
      )
      vi.spyOn(dwellerFilter, 'fetchWithCurrentFilters').mockImplementation(async () => {
        reads.push('filtered dwellers')
      })
      vi.spyOn(dwellerFilter, 'fetchAllDwellers').mockImplementation(async () => {
        reads.push('all dwellers')
      })
      vi.spyOn(incidentStore, 'fetchIncidents').mockImplementation(async () => {
        reads.push('incidents')
        return []
      })
      vi.spyOn(roomStore, 'fetchRooms').mockImplementation(async () => {
        reads.push('rooms')
        return 'loaded'
      })

      await mountView()
      await flushPromises()

      authStore.sessionGeneration++
      resolveVault()
      await flushPromises()

      expect(reads).toEqual([])
    })

    it('shows an error when the vault cannot be loaded', async () => {
      delete vaultStore.loadedVaults['vault-1']
      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockRejectedValue(new Error('Vault unavailable'))
      vi.spyOn(dwellerFilter, 'fetchDwellersByVault').mockResolvedValue()
      vi.spyOn(dwellerFilter, 'fetchAllDwellers').mockResolvedValue()
      vi.spyOn(incidentStore, 'fetchIncidents').mockResolvedValue()
      vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')

      const wrapper = await mountAt()

      expect(wrapper.text()).toContain('Vault unavailable')
    })
  })

  describe('Dweller navigation', () => {
    it('navigates to the full-page detail route when clicking a dweller', async () => {
      mockEndpoints([dweller({ first_name: 'John', last_name: 'Doe', level: 5 })])

      const wrapper = await mountAt()
      await wrapper.findAll('li')[0]!.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('dwellerDetail')
      expect(router.currentRoute.value.params.dwellerId).toBe('dweller-1')
    })
  })

  describe('Filter panel integration', () => {
    it.each([
      ['Socializing', 'resting', 'status=resting'],
      ['Fighting', 'fighting', 'status=fighting'],
    ])('applies the %s query filter', async (_, filter, fragment) => {
      mockEmptyRoster()
      await mountAt(`?filter=${filter}`)

      expect(axios.get).toHaveBeenCalledWith(expect.stringContaining(fragment))
    })

    it('refetches with identity filters when they change', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt()

      dwellerFilter.setFilterRace('ghoul')
      await flushPromises()

      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('race=ghoul'),
        expect.any(Object)
      )
      wrapper.unmount()
    })
  })

  describe('URL sync', () => {
    it.each([
      ['race', 'ghoul'],
      ['gender', 'female'],
      ['rarity', 'legendary'],
    ])('applies a %s query param on load', async (param, value) => {
      mockEmptyRoster()
      const wrapper = await mountAt(`?${param}=${value}`)

      expect(requested(`${param}=${value}`)).toBe(true)
      wrapper.unmount()
    })

    it('applies the facet state from a deep link', async () => {
      mockEmptyRoster()
      await mountAt('?gender=female&rarity=legendary')

      expect(dwellerFilter.filterGender).toBe('female')
      expect(dwellerFilter.filterRarity).toBe('legendary')
    })

    it('follows a query-only navigation while the view stays mounted', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt()

      await router.push('/vault/vault-1/dwellers?filter=exploring&race=ghoul')
      await flushPromises()

      expect(dwellerFilter.filterStatus).toBe('exploring')
      expect(dwellerFilter.filterRace).toBe('ghoul')
      wrapper.unmount()
    })

    it('resets a filter the query no longer carries', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt('?filter=exploring')
      expect(dwellerFilter.filterStatus).toBe('exploring')

      await router.push('/vault/vault-1/dwellers')
      await flushPromises()

      expect(dwellerFilter.filterStatus).toBe('all')
      wrapper.unmount()
    })

    it('drops the live-only filters and their URL keys when the dead panel takes over', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt()

      dwellerFilter.setFilterRace('ghoul')
      dwellerFilter.setFilterAgeGroup('adult')
      await flushPromises()
      expect(router.currentRoute.value.query.race).toBe('ghoul')

      dwellerFilter.setFilterStatus('dead')
      await flushPromises()

      expect(dwellerFilter.filterRace).toBe('all')
      expect(dwellerFilter.filterAgeGroup).toBe('all')
      expect(router.currentRoute.value.query.race).toBeUndefined()
      expect(router.currentRoute.value.query.ageGroup).toBeUndefined()
      expect(router.currentRoute.value.query.filter).toBe('dead')
      wrapper.unmount()
    })

    it('writes filter and sort changes back to the query', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt()

      dwellerFilter.setFilterStatus('idle')
      dwellerFilter.setFilterRace('ghoul')
      dwellerFilter.setSortBy('level')
      dwellerFilter.setSortDirection('desc')
      await flushPromises()

      expect(router.currentRoute.value.query).toMatchObject({
        filter: 'idle',
        race: 'ghoul',
        sortBy: 'level',
        order: 'desc',
      })
      wrapper.unmount()
    })

    it('drops a default filter back out of the query', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt('?filter=idle')

      dwellerFilter.setFilterStatus('all')
      await flushPromises()

      expect(router.currentRoute.value.query.filter).toBeUndefined()
      wrapper.unmount()
    })

    it('preserves unrelated query params', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt('?foo=bar')

      dwellerFilter.setFilterStatus('working')
      await flushPromises()

      expect(router.currentRoute.value.query.foo).toBe('bar')
      expect(router.currentRoute.value.query.filter).toBe('working')
      wrapper.unmount()
    })

    it.each([
      ['gender', 'male', (filter: typeof dwellerFilter) => filter.setFilterGender('male')],
      ['rarity', 'rare', (filter: typeof dwellerFilter) => filter.setFilterRarity('rare')],
    ])(
      'writes %s changes back to the query and refetches the roster',
      async (param, value, set) => {
        mockEmptyRoster()
        const wrapper = await mountAt()
        vi.mocked(axios.get).mockClear()

        set(dwellerFilter)
        await flushPromises()

        expect(router.currentRoute.value.query[param]).toBe(value)
        expect(axios.get).toHaveBeenCalledWith(
          expect.stringContaining(`${param}=${value}`),
          expect.any(Object)
        )
        wrapper.unmount()
      }
    )

    it('ignores facet query params while the dead panel is active', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt('?filter=dead&rarity=legendary&race=ghoul')

      expect(dwellerFilter.filterStatus).toBe('dead')
      expect(dwellerFilter.filterRarity).toBe('all')
      expect(dwellerFilter.filterRace).toBe('all')
      wrapper.unmount()
    })
  })

  describe('Empty roster recovery', () => {
    it('clears every active filter and its query keys from the empty-state action', async () => {
      mockEmptyRoster()
      const wrapper = await mountAt('?filter=idle&ageGroup=adult&gender=male')

      expect(dwellerFilter.filterStatus).toBe('idle')
      expect(wrapper.text()).toContain('No dwellers match these filters')

      const clearButton = wrapper
        .findAll('button')
        .find((button) => button.text().includes('Clear filters'))
      expect(clearButton).toBeDefined()

      await clearButton!.trigger('click')
      await flushPromises()

      expect(dwellerFilter.filterStatus).toBe('all')
      expect(dwellerFilter.filterAgeGroup).toBe('all')
      expect(dwellerFilter.filterGender).toBe('all')
      expect(router.currentRoute.value.query.filter).toBeUndefined()
      expect(router.currentRoute.value.query.ageGroup).toBeUndefined()
      expect(router.currentRoute.value.query.gender).toBeUndefined()
      wrapper.unmount()
    })
  })

  describe('Urgent action summary', () => {
    it('shows concrete idle and care counts instead of the vague attention text', async () => {
      mockEndpoints([
        dweller({ id: 'd1', status: 'idle' }),
        dweller({ id: 'd2', first_name: 'Hurt', health: 20 }),
        dweller({ id: 'd3', first_name: 'Rad', radiation: 30 }),
      ])
      const wrapper = await mountAt()

      const summary = wrapper.find('.happiness-overview summary')
      expect(summary.text()).toContain('1 idle')
      expect(summary.text()).toContain('2 need care')
      expect(summary.text()).not.toContain('Attention needed')
    })

    it('deep-links the idle count to the roster idle filter', async () => {
      mockEndpoints([dweller({ status: 'idle' })])
      const wrapper = await mountAt()

      await wrapper.find('a[aria-label="Filter the roster to 1 idle dwellers"]').trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.query.filter).toBe('idle')
      expect(dwellerFilter.filterStatus).toBe('idle')
    })

    it.each(['summary', 'dashboard'])(
      'clears care attention when opening idle through %s',
      async (entry) => {
        mockEndpoints([dweller({ status: 'idle', health: 20, happiness: 10 })])
        const wrapper = await mountAt()
        await wrapper
          .find('a[aria-label="Filter the roster to 1 injured or irradiated dwellers"]')
          .trigger('click')
        await flushPromises()
        expect(dwellerFilter.filterFocus).toBe('needs_care')

        if (entry === 'summary') {
          await wrapper
            .find('a[aria-label="Filter the roster to 1 idle dwellers"]')
            .trigger('click')
        } else {
          const action = wrapper
            .findAll('button')
            .find((button) => button.text().includes('Assign Idle'))
          expect(action).toBeTruthy()
          await action!.trigger('click')
        }
        await flushPromises()
        expect(dwellerFilter.filterStatus).toBe('idle')
        expect(dwellerFilter.filterFocus).toBe('all')
        expect(router.currentRoute.value.query.filter).toBe('idle')
        expect(router.currentRoute.value.query.focus).toBeUndefined()
        wrapper.unmount()
      }
    )

    it('filters injured and irradiated dwellers without using medicine', async () => {
      mockEndpoints([dweller({ health: 20 })])
      const wrapper = await mountAt()

      await wrapper
        .find('a[aria-label="Filter the roster to 1 injured or irradiated dwellers"]')
        .trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('dwellers')
      expect(router.currentRoute.value.query.focus).toBe('needs_care')
      expect(dwellerFilter.filterFocus).toBe('needs_care')
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('clears unrelated filters when opening low happiness and sends the attention query', async () => {
      mockEndpoints([dweller({ happiness: 10 })])
      await router.push({
        path: '/vault/vault-1/dwellers',
        query: {
          filter: 'working',
          ageGroup: 'adult',
          gender: 'male',
          rarity: 'rare',
          race: 'human',
          sortBy: 'level',
          order: 'desc',
        },
      })
      const wrapper = await mountAt()

      const action = wrapper
        .findAll('button')
        .find((button) => button.text().includes('View Low Happiness'))
      expect(action).toBeTruthy()
      await action!.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.query).toEqual({
        focus: 'low_happiness',
        sortBy: 'happiness',
      })
      expect(dwellerFilter.filterStatus).toBe('all')
      expect(dwellerFilter.filterFocus).toBe('low_happiness')
      expect(wrapper.find('.filter-panel summary').text()).toContain('Low Happiness')
      expect(requested('focus=low_happiness')).toBe(true)
      expect(axios.post).not.toHaveBeenCalled()
    })

    it('deep-links a critical resource to its production room', async () => {
      vaultStore.loadedVaults['vault-1'].resource_warnings = [
        { type: 'critical_food', message: 'Food critically low!' },
      ] as never
      mockEndpoints([], [productionRoom])
      const wrapper = await mountAt()

      const chip = wrapper.find(
        'a[aria-label="Food critically low! — open the Food production room"]'
      )
      expect(chip.exists()).toBe(true)
      await chip.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/vault/vault-1')
      expect(router.currentRoute.value.query.roomId).toBe('garden-1')
    })

    it('shows a re-armed vault error with a retry that reloads the overview', async () => {
      delete vaultStore.loadedVaults['vault-1']
      mockEndpoints([])
      const ensured = vi
        .spyOn(vaultStore, 'ensureVaultLoaded')
        .mockRejectedValueOnce(new Error('Vault unavailable'))
        .mockImplementationOnce(async (id: string) => {
          vaultStore.loadedVaults[id] = {
            id,
            number: 101,
            bottle_caps: 0,
            power: 100,
            power_max: 100,
            food: 100,
            food_max: 100,
            water: 100,
            water_max: 100,
            dweller_count: 0,
          } as never
        })

      const wrapper = await mountAt()

      expect(wrapper.text()).toContain('Vault overview unavailable')
      expect(wrapper.text()).toContain('Vault unavailable')
      expect(wrapper.text()).toContain('could not be loaded')

      await wrapper.find('button[aria-label="Retry loading the vault overview"]').trigger('click')
      await flushPromises()

      expect(ensured).toHaveBeenCalledTimes(2)
      expect(wrapper.text()).not.toContain('Vault overview unavailable')
      expect(wrapper.text()).toContain('Happiness Overview')
    })
  })

  describe('Flicker gating', () => {
    it.each([
      [true, true],
      [false, false],
      [undefined, false],
    ])(
      'applies the flicker treatment only when the provided flag is %s',
      async (flag, expected) => {
        mockEmptyRoster()

        await router.isReady()
        const wrapper =
          flag === undefined
            ? mount(DwellersView, { global: { plugins: [router, pinia] } })
            : await mountView(flag)
        await flushPromises()

        expect(wrapper.find('.main-content.flicker').exists()).toBe(expected)
        wrapper.unmount()
      }
    )
  })
})
