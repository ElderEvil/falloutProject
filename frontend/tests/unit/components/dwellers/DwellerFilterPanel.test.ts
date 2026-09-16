import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerFilterPanel from '@/modules/dwellers/components/DwellerFilterPanel.vue'
import filterPanelSource from '@/modules/dwellers/components/DwellerFilterPanel.vue?raw'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
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

/** The collapse toggle is the only toolbar button whose label mentions active filters. */
async function expandFilters(wrapper: ReturnType<typeof mount>) {
  const toggle = wrapper.findAll('.view-toggle-btn').find((b) => b.text().includes('active'))
  expect(toggle).toBeDefined()
  await toggle!.trigger('click')
  await flushPromises()
}

describe('DwellerFilterPanel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem('dwellerViewMode')
    localStorage.removeItem('dwellerTableColumns')
  })

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
      expect(filterPanelSource).toMatch(
        /\.sort-select \{(?=[^}]*padding: 0\.5rem 0\.75rem;)(?=[^}]*font-size: 0\.8125rem;)[^}]*\}/
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

      const sortSelect = wrapper.find('.sort-select')
      expect(sortSelect.attributes('aria-label')).toBe('Sort dwellers')
      await sortSelect.setValue('level')

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
    it('collapses the filter controls until the toggle is used', async () => {
      const wrapper = mount(DwellerFilterPanel, {
        props: { collapsible: true, showIdentityFilters: true },
      })
      await flushPromises()

      expect(wrapper.text()).not.toContain('Filter by Status')
      expect(wrapper.text()).toContain('None active')

      await expandFilters(wrapper)

      expect(wrapper.text()).toContain('Filter by Status')
    })

    it('counts the active filters it hides', async () => {
      const wrapper = mount(DwellerFilterPanel, {
        props: { collapsible: true, showIdentityFilters: true },
      })
      await flushPromises()

      const store = useDwellerStore().filter
      // One change per tick, the way a user clicks the two selects.
      store.setFilterRace('ghoul')
      await flushPromises()
      store.setFilterFaction('children_of_atom')
      await flushPromises()

      expect(store.filterRace).toBe('ghoul')
      expect(store.filterFaction).toBe('children_of_atom')
      expect(wrapper.text()).toContain('2 active')
    })

    it('clears a faction the newly selected race cannot hold', async () => {
      const store = useDwellerStore().filter
      const wrapper = mount(DwellerFilterPanel, {
        props: { collapsible: true, showIdentityFilters: true },
      })
      await flushPromises()

      store.setFilterRace('ghoul')
      store.setFilterFaction('children_of_atom')
      await flushPromises()
      expect(store.filterFaction).toBe('children_of_atom')

      store.setFilterRace('super_mutant')
      await flushPromises()

      expect(store.filterFaction).toBe('all')
      wrapper.unmount()
    })
  })
