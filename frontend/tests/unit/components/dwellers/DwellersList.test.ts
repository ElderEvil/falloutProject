import { describe, expect, it } from 'vitest'
import { shallowMount, mount } from '@vue/test-utils'
import DwellersList from '@/modules/dwellers/components/DwellersList.vue'

const dweller = (overrides: Record<string, unknown> = {}) => ({
  id: 'dweller-1',
  first_name: 'Sarah',
  last_name: 'Lyons',
  thumbnail_url: null,
  level: 5,
  health: 80,
  max_health: 100,
  radiation: 0,
  happiness: 75,
  room_id: null,
  status: 'working',
  age_group: 'adult',
  gender: 'female',
  rarity: 'rare',
  strength: 8,
  perception: 4,
  endurance: 4,
  charisma: 4,
  intelligence: 4,
  agility: 4,
  luck: 4,
  ...overrides,
})

const baseProps = (overrides: Record<string, unknown> = {}) => ({
  dwellers: [],
  generatingAI: {},
  isLoading: false,
  rooms: [],
  viewMode: 'list',
  ...overrides,
})

describe('DwellersList', () => {
  it('renders the list layout for list mode', () => {
    const wrapper = shallowMount(DwellersList, {
      props: baseProps({ dwellers: [dweller()] }),
    })

    expect(wrapper.find('ul').exists()).toBe(true)
    expect(wrapper.find('.dweller-grid').exists()).toBe(false)
  })

  it('renders the grid layout for grid mode', () => {
    const wrapper = shallowMount(DwellersList, {
      props: baseProps({ dwellers: [dweller()], viewMode: 'grid' }),
    })

    expect(wrapper.find('.dweller-grid').exists()).toBe(true)
  })

  it('renders the table layout for table mode', () => {
    const wrapper = mount(DwellersList, {
      props: baseProps({ dwellers: [dweller()], viewMode: 'table' }),
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.find('table').exists()).toBe(true)
    expect(wrapper.find('ul').exists()).toBe(false)
    expect(wrapper.find('.dweller-grid').exists()).toBe(false)
  })

  describe('Empty state', () => {
    it('offers a clear-filters action when no dweller matches the active filters', async () => {
      const wrapper = mount(DwellersList, {
        props: baseProps({ hasActiveFilters: true }),
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.text()).toContain('No dwellers match these filters')

      const clearButton = wrapper.get('button')
      expect(clearButton.text()).toContain('Clear filters')

      await clearButton.trigger('click')

      expect(wrapper.emitted('clear-filters')).toHaveLength(1)
    })

    it('shows the empty-vault message without a clear action when no filters are active', () => {
      const wrapper = mount(DwellersList, {
        props: baseProps(),
        global: { stubs: { Icon: true } },
      })

      expect(wrapper.text()).toContain('No dwellers yet')
      expect(wrapper.text()).not.toContain('No dwellers match these filters')
      expect(wrapper.find('button').exists()).toBe(false)
    })

    it('keeps the list skeletons instead of the empty state while loading', () => {
      const wrapper = shallowMount(DwellersList, {
        props: baseProps({ isLoading: true }),
      })

      expect(wrapper.text()).not.toContain('No dwellers yet')
      expect(wrapper.find('ul').exists()).toBe(true)
    })

    it('keeps rendering rows when the filtered list is not empty', () => {
      const wrapper = shallowMount(DwellersList, {
        props: baseProps({ dwellers: [dweller()], hasActiveFilters: true }),
      })

      expect(wrapper.text()).not.toContain('No dwellers match these filters')
      expect(wrapper.find('ul').exists()).toBe(true)
    })
  })

  it('shows the dweller combat power', () => {
    const wrapper = shallowMount(DwellersList, {
      props: {
        dwellers: [
          {
            id: 'dweller-1',
            first_name: 'Sarah',
            last_name: 'Lyons',
            thumbnail_url: null,
            level: 5,
            health: 80,
            max_health: 100,
            radiation: 0,
            happiness: 75,
            room_id: 'room-1',
            status: 'working',
            age_group: 'adult',
            gender: 'female',
            rarity: 'rare',
            strength: 8,
            perception: 4,
            endurance: 4,
            charisma: 4,
            intelligence: 4,
            agility: 4,
            luck: 4,
          },
        ],
        generatingAI: {},
        isLoading: false,
        rooms: [{ id: 'room-1', name: 'Arena', category: 'arena', ability: 'strength' }],
        viewMode: 'list',
      },
      global: { stubs: { DwellerListRow: false } },
    })

    expect(wrapper.text()).toContain('Power:')
    expect(wrapper.text()).toContain('14')
  })

  it('keeps the status column aligned when a dweller has a long name', () => {
    const wrapper = shallowMount(DwellersList, {
      props: {
        dwellers: [
          {
            id: 'dweller-2',
            first_name: 'Maximilianus',
            last_name: 'Von-Longname-Example',
            thumbnail_url: null,
            level: 5,
            health: 80,
            max_health: 100,
            radiation: 0,
            happiness: 75,
            room_id: null,
            status: 'resting',
            age_group: 'adult',
            gender: 'male',
            rarity: 'common',
            strength: 4,
            perception: 4,
            endurance: 4,
            charisma: 8,
            intelligence: 4,
            agility: 4,
            luck: 4,
          },
        ],
        generatingAI: {},
        isLoading: false,
        rooms: [],
        viewMode: 'list',
      },
      global: { stubs: { DwellerListRow: false } },
    })

    expect(wrapper.find('.dweller-identity').classes()).toContain('w-44')
    expect(wrapper.find('h3').classes()).toContain('truncate')
    expect(wrapper.find('li').classes()).toContain('bg-surface-canvas')
    expect(wrapper.find('li').classes()).toContain('border-theme-primary/20')
  })
})
