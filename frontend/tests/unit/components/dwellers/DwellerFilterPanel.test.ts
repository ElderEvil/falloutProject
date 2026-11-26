import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { flushPromises, mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerFilterPanel from '@/modules/dwellers/components/DwellerFilterPanel.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { getDwellersByVault, getIdentityOptions } from '@/modules/dwellers/services/dwellerService'

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError: vi.fn(),
}))

vi.mock('@/core/utils/api', () => ({
  apiGet: vi.fn().mockResolvedValue({
    race_mechanics: true,
    faction_mechanics: true,
    world_events: false,
  }),
}))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getDwellersByVault: vi.fn().mockResolvedValue([]),
  getIdentityOptions: vi.fn().mockResolvedValue({
    races: ['human', 'ghoul', 'super_mutant', 'synth'],
    factions_by_race: {
      human: ['vault_dweller', 'brotherhood_of_steel'],
      ghoul: ['vault_dweller', 'children_of_atom', 'none'],
      super_mutant: ['super_mutant_tribe', 'none'],
      synth: ['the_institute', 'railroad', 'none'],
    },
    states_by_race: {},
  }),
}))

// Every case gets a fresh store: it hydrates from localStorage, so a leftover
// key would otherwise leak across tests and describes.
beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  localStorage.setItem('dwellerViewMode', 'grid')
  localStorage.removeItem('dwellerTableColumns')
})

type PanelProps = InstanceType<typeof DwellerFilterPanel>['$props']

const mountPanel = (overrides: Partial<PanelProps> = {}) =>
  mount(DwellerFilterPanel, {
    props: {
      collapsible: false,
      showAttentionFilter: false,
      showStatusFilter: true,
      showAgeFilter: false,
      showGenderFilter: false,
      showRarityFilter: false,
      showIdentityFilters: false,
      showActiveFilterSummary: false,
      ...overrides,
    },
  })

const filter = () => useDwellerStore().filter

const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
  wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

const setRoster = (dwellers: Record<string, unknown>[]) => {
  filter().allDwellers = dwellers as never
}

describe('DwellerFilterPanel', () => {
  describe('status filters', () => {
    it('renders every status option', () => {
      const wrapper = mountPanel()

      expect(wrapper.findAll('.filter-chip').map((chip) => chip.text())).toEqual([
        'All Statuses',
        'Idle',
        'Socializing',
        'Working',
        'Training',
        'Exploring',
        'Questing',
        'Fighting',
        'Dead',
      ])
    })

    it('updates the store and highlights the clicked status', async () => {
      const wrapper = mountPanel()

      const working = chipByLabel(wrapper, 'Working')
      await working.trigger('click')

      expect(filter().filterStatus).toBe('working')
      expect(working.classes()).toContain('active')
      expect(chipByLabel(wrapper, 'All').classes()).not.toContain('active')
    })
  })

  describe('component structure', () => {
    it('owns the filter panel and keeps display controls out of it', () => {
      const wrapper = mount(DwellerFilterPanel, {
        props: { showStatusFilter: true, showAgeFilter: true },
        slots: { 'additional-filters': '<span data-test="additional-filter">Rarity</span>' },
      })

      expect(wrapper.find('.filter-panel').exists()).toBe(true)
      expect(wrapper.find('.filter-options').exists()).toBe(true)
      expect(wrapper.find('.filter-section-row').text()).toContain('Filter by Age')
      expect(wrapper.find('.filter-section-row [data-test="additional-filter"]').exists()).toBe(
        true
      )
      expect(wrapper.text()).not.toContain('Sort By')
      expect(wrapper.find('.view-toggle-btn').exists()).toBe(false)
    })
  })

  describe('identity filters', () => {
    it('hides the faction chips while the switch is off', async () => {
      const flags = useFeatureFlagsStore()
      flags.factionMechanics = false
      // Mark flags loaded so mounting does not refetch and re-enable the switch.
      flags.loaded = true
      const wrapper = mountPanel({ showIdentityFilters: true })
      await flushPromises()

      expect(wrapper.text()).not.toContain('Filter by Faction')
      expect(wrapper.text()).not.toContain('All Factions')
      expect(wrapper.text()).toContain('Filter by Race')
      expect(wrapper.text()).toContain('All Races')
    })

    it('drops a persisted race the loaded options no longer offer', async () => {
      filter().setFilterRace('reptilian')
      mountPanel({ showIdentityFilters: true })
      await flushPromises()

      expect(filter().filterRace).toBe('all')
    })

    it('keeps a persisted race filter when the identity options fail to load', async () => {
      vi.mocked(getIdentityOptions).mockRejectedValueOnce(new Error('offline'))
      filter().setFilterRace('ghoul')
      mountPanel({ showIdentityFilters: true })
      await flushPromises()

      expect(filter().filterRace).toBe('ghoul')
    })

    it('clears a faction the newly selected race cannot hold', async () => {
      const wrapper = mountPanel({ showIdentityFilters: true })
      await flushPromises()

      // One change per tick, the way a user clicks the two chip groups.
      await chipByLabel(wrapper, 'Ghoul').trigger('click')
      await flushPromises()
      await chipByLabel(wrapper, 'Children Of Atom').trigger('click')
      await flushPromises()
      expect(filter().filterFaction).toBe('children_of_atom')

      await chipByLabel(wrapper, 'Super Mutant').trigger('click')
      await flushPromises()

      expect(filter().filterFaction).toBe('all')
    })
  })

  describe('facet counts', () => {
    const byStatus = [
      { id: '1', status: 'idle' },
      { id: '2', status: 'idle' },
      { id: '3', status: 'working' },
      { id: '4', status: 'dead' },
    ]
    const byGender = [
      { id: '1', status: 'idle', gender: 'male' },
      { id: '2', status: 'idle', gender: 'male' },
      { id: '3', status: 'working', gender: 'female' },
    ]
    const byRarity = [
      { id: '1', status: 'idle', rarity: 'common' },
      { id: '2', status: 'idle', rarity: 'common' },
      { id: '3', status: 'working', rarity: 'legendary' },
    ]
    const byRace = [
      { id: '1', status: 'idle', visual_attributes: { race: 'ghoul' } },
      { id: '2', status: 'idle', visual_attributes: { race: 'ghoul' } },
      { id: '3', status: 'working', visual_attributes: { race: 'human' } },
    ]

    it.each([
      [
        'status',
        byStatus,
        {},
        [
          ['Idle', '2'],
          ['Working', '1'],
          ['All', '4'],
        ],
      ],
      [
        'gender',
        byGender,
        { showGenderFilter: true },
        [
          ['Male', '2'],
          ['Female', '1'],
          ['All Genders', '3'],
        ],
      ],
      [
        'rarity',
        byRarity,
        { showRarityFilter: true },
        [
          ['Common', '2'],
          ['Legendary', '1'],
          ['All Rarities', '3'],
        ],
      ],
      [
        'race',
        byRace,
        { showIdentityFilters: true },
        [
          ['Ghoul', '2'],
          ['Human', '1'],
          ['All Races', '3'],
        ],
      ],
    ] as const)('shows a count per %s and a total', async (_facet, dwellers, props, rows) => {
      setRoster(dwellers as unknown as Record<string, unknown>[])
      const wrapper = mountPanel(props as Partial<PanelProps>)
      await flushPromises()

      for (const [label, count] of rows) {
        expect(chipByLabel(wrapper, label).find('.filter-count').text()).toBe(count)
      }
    })

    it('shows a status count but omits the dead count', async () => {
      setRoster([
        { id: '1', status: 'idle' },
        { id: '4', status: 'dead' },
      ])
      const wrapper = mountPanel()
      await wrapper.vm.$nextTick()

      expect(chipByLabel(wrapper, 'Dead').find('.filter-count').exists()).toBe(false)
      expect(chipByLabel(wrapper, 'Idle').find('.filter-count').text()).toBe('1')
    })

    it('marks zero-count statuses as empty', async () => {
      setRoster([{ id: '1', status: 'idle' }])
      const wrapper = mountPanel()
      await wrapper.vm.$nextTick()

      expect(chipByLabel(wrapper, 'Working').classes()).toContain('empty')
      expect(chipByLabel(wrapper, 'Idle').classes()).not.toContain('empty')
      expect(chipByLabel(wrapper, 'Dead').classes()).not.toContain('empty')
    })

    it('contextualizes counts by the age filter only while it is on screen', async () => {
      setRoster([
        { id: '1', status: 'idle', age_group: 'adult' },
        { id: '2', status: 'working', age_group: 'child' },
      ])
      filter().setFilterAgeGroup('adult')

      const ageHidden = mountPanel()
      await ageHidden.vm.$nextTick()
      expect(chipByLabel(ageHidden, 'Working').find('.filter-count').text()).toBe('1')

      const ageShown = mountPanel({ showAgeFilter: true })
      await ageShown.vm.$nextTick()
      expect(chipByLabel(ageShown, 'Working').find('.filter-count').text()).toBe('0')
    })

    it.each([{}, { showGenderFilter: true }, { showRarityFilter: true }])(
      'shows no counts until the roster has loaded (props %o)',
      async (props) => {
        const wrapper = mountPanel(props as Partial<PanelProps>)
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.filter-count').exists()).toBe(false)
      }
    )
  })

  describe('filter accents', () => {
    it.each([
      ['age', 'Adult', { showAgeFilter: true }, 'filterAgeGroup', 'adult', '--badge-age-adult'],
      ['gender', 'Male', { showGenderFilter: true }, 'filterGender', 'male', '--badge-gender-male'],
    ] as const)(
      'tints the active %s chip with its accent color',
      async (_facet, label, props, storeKey, value, accent) => {
        setRoster([{ id: '1', status: 'idle', age_group: 'adult', gender: 'male' }])
        const wrapper = mountPanel(props as Partial<PanelProps>)

        await chipByLabel(wrapper, label).trigger('click')
        await wrapper.vm.$nextTick()

        const chip = chipByLabel(wrapper, label)
        expect(chip.classes()).toContain('active')
        expect(chip.attributes('style')).toContain(`--filter-accent: var(${accent})`)
        expect((filter() as unknown as Record<string, string>)[storeKey]).toBe(value)
      }
    )
  })

  describe('active filter summary', () => {
    it('stays hidden while no filters are active', () => {
      const wrapper = mountPanel({ showActiveFilterSummary: true })

      expect(wrapper.find('.filter-summary').exists()).toBe(false)
    })

    it('lists active filters and clears only the filtering state', async () => {
      const store = filter()
      store.setFilterStatus('idle')
      store.setFilterAgeGroup('adult')
      store.setSortBy('level')
      store.setViewMode('grid')

      const wrapper = mountPanel({ showActiveFilterSummary: true, showAgeFilter: true })
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.filter-summary').text()).toContain('Idle')
      expect(wrapper.find('.filter-summary').text()).toContain('Adult')

      await wrapper.find('.filter-clear').trigger('click')

      expect(store.filterStatus).toBe('all')
      expect(store.filterAgeGroup).toBe('all')
      expect(store.filterRace).toBe('all')
      expect(store.filterFaction).toBe('all')
      expect(store.sortBy).toBe('level')
      expect(store.viewMode).toBe('grid')
    })

    it('never names a facet whose control is hidden', async () => {
      const store = filter()
      store.setFilterStatus('dead')
      store.setFilterAgeGroup('adult')
      store.setFilterRace('ghoul')

      const wrapper = mountPanel({
        showActiveFilterSummary: true,
        showAgeFilter: false,
        showIdentityFilters: false,
      })
      await wrapper.vm.$nextTick()

      const summary = wrapper.find('.filter-summary').text()
      expect(summary).toContain('Dead')
      expect(summary).not.toContain('Adult')
      expect(summary).not.toContain('Ghoul')
    })

    it('names an active identity filter', async () => {
      filter().setFilterRace('ghoul')

      const wrapper = mountPanel({ showActiveFilterSummary: true, showIdentityFilters: true })
      await flushPromises()

      expect(wrapper.find('.filter-summary').text()).toContain('Ghoul')
    })
  })

  describe('collapsible roster filters', () => {
    it('starts collapsed and preserves active selections across toggles', async () => {
      const store = filter()
      store.setFilterFocus('needs_care')
      store.setFilterAgeGroup('adult')
      const wrapper = mountPanel({
        collapsible: true,
        showAttentionFilter: true,
        showAgeFilter: true,
      })
      const details = wrapper.element as HTMLDetailsElement
      expect(details.tagName).toBe('DETAILS')
      expect(details.open).toBe(false)
      expect(wrapper.find('summary').text()).toContain('Needs Care')
      expect(wrapper.find('summary').text()).toContain('Adult')

      details.open = true
      await wrapper.trigger('toggle')
      details.open = false
      await wrapper.trigger('toggle')

      expect(store.filterFocus).toBe('needs_care')
      expect(store.filterAgeGroup).toBe('adult')
    })

    it('clears attention and facets from the collapsed summary while keeping sort and view', async () => {
      const store = filter()
      store.setFilterFocus('low_happiness')
      store.setFilterStatus('working')
      store.setFilterAgeGroup('adult')
      store.setSortBy('happiness')
      store.setViewMode('table')
      const wrapper = mountPanel({
        collapsible: true,
        showAttentionFilter: true,
        showAgeFilter: true,
      })

      await wrapper.find('summary button').trigger('click')

      expect(store.filterFocus).toBe('all')
      expect(store.filterStatus).toBe('all')
      expect(store.filterAgeGroup).toBe('all')
      expect(store.sortBy).toBe('happiness')
      expect(store.viewMode).toBe('table')
      expect((wrapper.element as HTMLDetailsElement).open).toBe(false)
    })
  })

  it.each([
    ['retired_focus', 'all', undefined],
    ['needs_care', 'needs_care', 'needs_care'],
    ['low_happiness', 'low_happiness', 'low_happiness'],
    ['all', 'all', undefined],
  ])(
    'hydrates persisted focus %s safely before the first roster request',
    async (stored, hydrated, sent) => {
      localStorage.setItem('dwellerFilterFocus', stored!)
      const store = filter()
      expect(store.filterFocus).toBe(hydrated)
      await store.fetchWithCurrentFilters('vault-1')
      expect(getDwellersByVault).toHaveBeenLastCalledWith(
        'vault-1',
        expect.objectContaining({ focus: sent })
      )
    }
  )
})
