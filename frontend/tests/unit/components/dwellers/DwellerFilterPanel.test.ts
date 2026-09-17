import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerFilterPanel from '@/modules/dwellers/components/DwellerFilterPanel.vue'
import filterPanelSource from '@/modules/dwellers/components/DwellerFilterPanel.vue?raw'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import { getIdentityOptions } from '@/modules/dwellers/services/dwellerService'

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn().mockResolvedValue({ race_mechanics: true, faction_mechanics: true }),
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

describe('DwellerFilterPanel', () => {
  describe('Status Filters', () => {
    it('should render all status filter options', () => {
      const wrapper = mount(DwellerFilterPanel)

      // Check for all status options
      expect(wrapper.text()).toContain('All')
      expect(wrapper.text()).toContain('Idle')
      expect(wrapper.text()).toContain('Socializing')
      expect(wrapper.text()).toContain('Working')
      expect(wrapper.text()).toContain('Training')
      expect(wrapper.text()).toContain('Exploring')
      expect(wrapper.text()).toContain('Questing')
      expect(wrapper.text()).toContain('Dead')
    })

    it('should update store when status filter is clicked', async () => {
      const wrapper = mount(DwellerFilterPanel)
      const store = useDwellerStore().filter

      // Find and click the "Working" filter button
      const buttons = wrapper.findAll('.filter-chip')
      const workingButton = buttons.find((btn) => btn.text().includes('Working'))

      expect(workingButton).toBeDefined()
      await workingButton!.trigger('click')

      expect(store.filterStatus).toBe('working')
    })

    it('should highlight active filter with active class', async () => {
      const wrapper = mount(DwellerFilterPanel)
      const store = useDwellerStore().filter

      store.setFilterStatus('working')
      await wrapper.vm.$nextTick()

      // Check that the working filter has active class
      const buttons = wrapper.findAll('.filter-chip')
      const workingButton = buttons.find((btn) => btn.text().includes('Working'))

      expect(workingButton!.classes()).toContain('active')
    })
  })

  describe('Sort Options', () => {
    it('should render sort by section', () => {
      const wrapper = mount(DwellerFilterPanel)

      expect(wrapper.text()).toContain('Sort By')
      // Both toolbar dropdowns share one trigger rule, so their lists cannot drift apart.
      expect(filterPanelSource).toMatch(
        /\.identity-controls :deep\(\.select-trigger\),\s*\.sort-controls :deep\(\.select-trigger\) \{(?=[^}]*padding: 0\.5rem 0\.75rem;)(?=[^}]*font-size: 0\.8125rem;)[^}]*\}/
      )
      expect(filterPanelSource).toMatch(
        /\.sort-direction-button \{(?=[^}]*padding: 0\.5rem 0\.75rem;)[^}]*\}/
      )
      expect(filterPanelSource).toMatch(
        /\.view-toggle-btn \{(?=[^}]*padding: 0\.5rem 0\.75rem;)(?=[^}]*font-size: 0\.8125rem;)[^}]*\}/
      )
    })

    it('should update store when sort option is changed', async () => {
      const wrapper = mount(DwellerFilterPanel)
      const store = useDwellerStore().filter

      const sortTrigger = wrapper.find('.sort-controls .select-trigger')
      expect(sortTrigger.attributes('aria-label')).toBe('Sort dwellers')

      await sortTrigger.trigger('click')
      const levelOption = wrapper.findAll('.sort-controls .select-option').find((o) => o.text().includes('Level'))
      expect(levelOption).toBeDefined()
      await levelOption!.trigger('click')

      expect(store.sortBy).toBe('level')
    })

    it('should have sort direction toggle button', () => {
      const wrapper = mount(DwellerFilterPanel)

      const sortDirectionBtn = wrapper.find('.sort-direction-button')
      expect(sortDirectionBtn.exists()).toBe(true)
    })
  })

  describe('View modes', () => {
    it('switches to the table view', async () => {
      const wrapper = mount(DwellerFilterPanel, { props: { showViewToggle: true } })
      const store = useDwellerStore().filter

      const tableButton = wrapper
        .findAll('.view-toggle-btn')
        .find((btn) => btn.text().includes('Table'))
      expect(tableButton).toBeDefined()

      await tableButton!.trigger('click')

      expect(store.viewMode).toBe('table')
    })

    it('shows the column picker only in table mode and toggles a column', async () => {
      const wrapper = mount(DwellerFilterPanel, { props: { showViewToggle: true } })
      const store = useDwellerStore().filter

      expect(wrapper.text()).not.toContain('Columns')

      store.setViewMode('table')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Columns')
      const rarityButton = wrapper
        .findAll('.view-toggle-btn')
        .find((btn) => btn.text().includes('Rarity'))
      expect(rarityButton).toBeDefined()

      await rarityButton!.trigger('click')

      expect(store.tableColumns).toContain('rarity')
    })

    it('applies a column preset', async () => {
      const wrapper = mount(DwellerFilterPanel, { props: { showViewToggle: true } })
      const store = useDwellerStore().filter

      store.setViewMode('table')
      await wrapper.vm.$nextTick()

      const vitalsButton = wrapper
        .findAll('.view-toggle-btn')
        .find((btn) => btn.text().includes('Vitals'))
      expect(vitalsButton).toBeDefined()

      await vitalsButton!.trigger('click')

      expect(store.tableColumns).toContain('health')
      expect(store.tableColumns).not.toContain('room')
    })
  })

  describe('Component Structure', () => {
    it('should render filter panel container', () => {
      const wrapper = mount(DwellerFilterPanel)

      const filterPanel = wrapper.find('.filter-panel')
      expect(filterPanel.exists()).toBe(true)
    })

    it('should have button group for status filters', () => {
      const wrapper = mount(DwellerFilterPanel)

      const buttonGroup = wrapper.find('.filter-options')
      expect(buttonGroup.exists()).toBe(true)
    })

    it('should place age filtering and sorting in the same row', () => {
      const wrapper = mount(DwellerFilterPanel, { props: { showAgeFilter: true } })
      const controlsRow = wrapper.find('.filter-section-row')

      expect(controlsRow.text()).toContain('Filter by Age')
      expect(controlsRow.text()).toContain('Sort By')
    })

    it('should render additional filters inside the controls panel', () => {
      const wrapper = mount(DwellerFilterPanel, {
        slots: { 'additional-filters': '<span data-test="additional-filter">Rarity</span>' },
      })

      expect(wrapper.find('.filter-section-row [data-test="additional-filter"]').exists()).toBe(
        true
      )
    })
  })
})

  describe('Identity filters', () => {
    it('hides the faction select while the switch is off', async () => {
      const flags = useFeatureFlagsStore()
      flags.factionMechanics = false
      // Mark flags loaded so mounting does not refetch and re-enable the switch.
      flags.loaded = true
      const wrapper = mount(DwellerFilterPanel, { props: { showIdentityFilters: true } })
      await flushPromises()

      expect(wrapper.text()).not.toContain('All Factions')
      expect(wrapper.text()).toContain('All Races')
      wrapper.unmount()
    })

    it('drops a persisted race the loaded options no longer offer', async () => {
      const store = useDwellerStore().filter
      store.setFilterRace('reptilian')

      const wrapper = mount(DwellerFilterPanel, { props: { showIdentityFilters: true } })
      await flushPromises()

      expect(store.filterRace).toBe('all')
      wrapper.unmount()
    })

    it('keeps a persisted race filter when the identity options fail to load', async () => {
      vi.mocked(getIdentityOptions).mockRejectedValueOnce(new Error('offline'))
      const store = useDwellerStore().filter
      store.setFilterRace('ghoul')

      const wrapper = mount(DwellerFilterPanel, { props: { showIdentityFilters: true } })
      await flushPromises()

      expect(store.filterRace).toBe('ghoul')
      wrapper.unmount()
    })

    it('clears a faction the newly selected race cannot hold', async () => {
      const store = useDwellerStore().filter
      const wrapper = mount(DwellerFilterPanel, {
        props: { showIdentityFilters: true },
      })
      await flushPromises()

      // One change per tick, the way a user clicks the two selects.
      store.setFilterRace('ghoul')
      await flushPromises()
      store.setFilterFaction('children_of_atom')
      await flushPromises()
      expect(store.filterFaction).toBe('children_of_atom')

      store.setFilterRace('super_mutant')
      await flushPromises()

      expect(store.filterFaction).toBe('all')
      wrapper.unmount()
    })
  })

  describe('Status counts', () => {
    const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
      wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

    it('shows a count per status and omits the dead count', async () => {
      const store = useDwellerStore().filter
      store.allDwellers = [
        { id: '1', status: 'idle' },
        { id: '2', status: 'idle' },
        { id: '3', status: 'working' },
        { id: '4', status: 'dead' },
      ] as never

      const wrapper = mount(DwellerFilterPanel)
      await wrapper.vm.$nextTick()

      expect(chipByLabel(wrapper, 'Idle').find('.filter-count').text()).toBe('2')
      expect(chipByLabel(wrapper, 'Working').find('.filter-count').text()).toBe('1')
      expect(chipByLabel(wrapper, 'All').find('.filter-count').text()).toBe('4')
      expect(chipByLabel(wrapper, 'Dead').find('.filter-count').exists()).toBe(false)

      wrapper.unmount()
    })

    it('marks zero-count statuses as empty', async () => {
      const store = useDwellerStore().filter
      store.allDwellers = [{ id: '1', status: 'idle' }] as never

      const wrapper = mount(DwellerFilterPanel)
      await wrapper.vm.$nextTick()

      expect(chipByLabel(wrapper, 'Working').classes()).toContain('empty')
      expect(chipByLabel(wrapper, 'Idle').classes()).not.toContain('empty')
      expect(chipByLabel(wrapper, 'Dead').classes()).not.toContain('empty')

      wrapper.unmount()
    })

    it('contextualizes counts by the age filter only while it is on screen', async () => {
      const store = useDwellerStore().filter
      store.allDwellers = [
        { id: '1', status: 'idle', age_group: 'adult' },
        { id: '2', status: 'working', age_group: 'child' },
      ] as never
      store.setFilterAgeGroup('adult')

      const ageHidden = mount(DwellerFilterPanel)
      await ageHidden.vm.$nextTick()
      expect(chipByLabel(ageHidden, 'Working').find('.filter-count').text()).toBe('1')

      const ageShown = mount(DwellerFilterPanel, { props: { showAgeFilter: true } })
      await ageShown.vm.$nextTick()
      expect(chipByLabel(ageShown, 'Working').find('.filter-count').text()).toBe('0')

      ageHidden.unmount()
      ageShown.unmount()
    })

    it('shows no counts until the roster has loaded', async () => {
      const wrapper = mount(DwellerFilterPanel)
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.filter-count').exists()).toBe(false)
      wrapper.unmount()
    })
  })

  describe('Active filter summary', () => {
    it('stays hidden while no filters are active', () => {
      const wrapper = mount(DwellerFilterPanel, { props: { showActiveFilterSummary: true } })

      expect(wrapper.find('.filter-summary').exists()).toBe(false)
      wrapper.unmount()
    })

    it('lists active filters and clears only the filtering state', async () => {
      const store = useDwellerStore().filter
      store.setFilterStatus('idle')
      store.setFilterAgeGroup('adult')
      store.setSortBy('level')
      store.setViewMode('grid')

      const wrapper = mount(DwellerFilterPanel, {
        props: { showActiveFilterSummary: true, showAgeFilter: true },
      })
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

      wrapper.unmount()
    })

    it('names an active identity filter', async () => {
      const store = useDwellerStore().filter
      store.setFilterRace('ghoul')

      const wrapper = mount(DwellerFilterPanel, {
        props: { showActiveFilterSummary: true, showIdentityFilters: true },
      })
      await flushPromises()

      expect(wrapper.find('.filter-summary').text()).toContain('Ghoul')
      wrapper.unmount()
    })
  })
