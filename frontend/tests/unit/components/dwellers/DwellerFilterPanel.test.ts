import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerFilterPanel from '@/modules/dwellers/components/DwellerFilterPanel.vue'
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

    it('keeps the age filter in the controls row and leaves display controls out', () => {
      const wrapper = mount(DwellerFilterPanel, { props: { showAgeFilter: true } })
      const controlsRow = wrapper.find('.filter-section-row')

      expect(controlsRow.text()).toContain('Filter by Age')
      expect(wrapper.text()).not.toContain('Sort By')
      expect(wrapper.find('.view-toggle-btn').exists()).toBe(false)
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
  const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

  it('hides the faction chips while the switch is off', async () => {
    const flags = useFeatureFlagsStore()
    flags.factionMechanics = false
    // Mark flags loaded so mounting does not refetch and re-enable the switch.
    flags.loaded = true
    const wrapper = mount(DwellerFilterPanel, { props: { showIdentityFilters: true } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Filter by Faction')
    expect(wrapper.text()).not.toContain('All Factions')
    expect(wrapper.text()).toContain('Filter by Race')
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

    // One change per tick, the way a user clicks the two chip groups.
    await chipByLabel(wrapper, 'Ghoul').trigger('click')
    await flushPromises()
    await chipByLabel(wrapper, 'Children Of Atom').trigger('click')
    await flushPromises()
    expect(store.filterFaction).toBe('children_of_atom')

    await chipByLabel(wrapper, 'Super Mutant').trigger('click')
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

describe('Gender counts', () => {
  const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

  it('shows a count per gender and a total', async () => {
    const store = useDwellerStore().filter
    store.allDwellers = [
      { id: '1', status: 'idle', gender: 'male' },
      { id: '2', status: 'idle', gender: 'male' },
      { id: '3', status: 'working', gender: 'female' },
    ] as never

    const wrapper = mount(DwellerFilterPanel, { props: { showGenderFilter: true } })
    await wrapper.vm.$nextTick()

    expect(chipByLabel(wrapper, 'Male').find('.filter-count').text()).toBe('2')
    expect(chipByLabel(wrapper, 'Female').find('.filter-count').text()).toBe('1')
    expect(chipByLabel(wrapper, 'All Genders').find('.filter-count').text()).toBe('3')

    wrapper.unmount()
  })

  it('shows no gender counts until the roster has loaded', async () => {
    const wrapper = mount(DwellerFilterPanel, { props: { showGenderFilter: true } })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.filter-count').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('Filter accents', () => {
  const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

  it('tints the active age chip with the age accent color', async () => {
    const store = useDwellerStore().filter
    store.allDwellers = [{ id: '1', status: 'idle', age_group: 'adult' }] as never

    const wrapper = mount(DwellerFilterPanel, { props: { showAgeFilter: true } })
    await chipByLabel(wrapper, 'Adult').trigger('click')
    await wrapper.vm.$nextTick()

    const chip = chipByLabel(wrapper, 'Adult')
    expect(chip.classes()).toContain('active')
    expect(chip.attributes('style') ?? '').toContain('--filter-accent: var(--badge-age-adult)')
    wrapper.unmount()
  })

  it('tints the active gender chip with the gender accent color', async () => {
    const store = useDwellerStore().filter
    store.allDwellers = [{ id: '1', status: 'idle', gender: 'male' }] as never

    const wrapper = mount(DwellerFilterPanel, { props: { showGenderFilter: true } })
    await chipByLabel(wrapper, 'Male').trigger('click')
    await wrapper.vm.$nextTick()

    const chip = chipByLabel(wrapper, 'Male')
    expect(chip.classes()).toContain('active')
    expect(chip.attributes('style') ?? '').toContain('--filter-accent: var(--badge-gender-male)')
    wrapper.unmount()
  })
})

describe('Rarity counts', () => {
  const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

  it('shows a count per rarity and a total', async () => {
    const store = useDwellerStore().filter
    store.allDwellers = [
      { id: '1', status: 'idle', rarity: 'common' },
      { id: '2', status: 'idle', rarity: 'common' },
      { id: '3', status: 'working', rarity: 'legendary' },
    ] as never

    const wrapper = mount(DwellerFilterPanel, { props: { showRarityFilter: true } })
    await wrapper.vm.$nextTick()

    expect(chipByLabel(wrapper, 'Common').find('.filter-count').text()).toBe('2')
    expect(chipByLabel(wrapper, 'Legendary').find('.filter-count').text()).toBe('1')
    expect(chipByLabel(wrapper, 'All Rarities').find('.filter-count').text()).toBe('3')

    wrapper.unmount()
  })

  it('shows no rarity counts until the roster has loaded', async () => {
    const wrapper = mount(DwellerFilterPanel, { props: { showRarityFilter: true } })
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.filter-count').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('Race counts', () => {
  const chipByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('.filter-chip').find((chip) => chip.text().includes(label))!

  it('shows a count per race and a total', async () => {
    const store = useDwellerStore().filter
    store.allDwellers = [
      { id: '1', status: 'idle', visual_attributes: { race: 'ghoul' } },
      { id: '2', status: 'idle', visual_attributes: { race: 'ghoul' } },
      { id: '3', status: 'working', visual_attributes: { race: 'human' } },
    ] as never

    const wrapper = mount(DwellerFilterPanel, { props: { showIdentityFilters: true } })
    await flushPromises()

    expect(chipByLabel(wrapper, 'Ghoul').find('.filter-count').text()).toBe('2')
    expect(chipByLabel(wrapper, 'Human').find('.filter-count').text()).toBe('1')
    expect(chipByLabel(wrapper, 'All Races').find('.filter-count').text()).toBe('3')

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

  it('never names a facet whose control is hidden', async () => {
    const store = useDwellerStore().filter
    store.setFilterStatus('dead')
    store.setFilterAgeGroup('adult')
    store.setFilterRace('ghoul')

    const wrapper = mount(DwellerFilterPanel, {
      props: {
        showActiveFilterSummary: true,
        showAgeFilter: false,
        showIdentityFilters: false,
      },
    })
    await wrapper.vm.$nextTick()

    const summary = wrapper.find('.filter-summary').text()
    expect(summary).toContain('Dead')
    expect(summary).not.toContain('Adult')
    expect(summary).not.toContain('Ghoul')
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
