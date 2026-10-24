import { describe, expect, it } from 'vite-plus/test'
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
  isLoading: false,
  rooms: [],
  viewMode: 'list',
  ...overrides,
})

describe('DwellersList', () => {
  const roster = Array.from({ length: 45 }, (_, index) => dweller({ id: `dweller-${index}` }))

  it.each(['list', 'grid', 'table'])(
    'paginates the %s layout without changing roster order',
    async (viewMode) => {
      const wrapper = shallowMount(DwellersList, {
        props: baseProps({ dwellers: roster, viewMode }),
        global: { stubs: { Button: false } },
      })
      const visibleIds = () =>
        viewMode === 'table'
          ? wrapper
              .findComponent({ name: 'DwellersTable' })
              .props('dwellers')
              .map((d: { id: string }) => d.id)
          : wrapper
              .findAllComponents({
                name: viewMode === 'list' ? 'DwellerListRow' : 'DwellerGridItem',
              })
              .map((row) => row.props('dweller').id)

      expect(visibleIds()).toEqual(roster.slice(0, 20).map((d) => d.id))
      expect(wrapper.text()).toContain('1–20 of 45')
      expect(wrapper.get('[aria-label="Dweller pages"]').element.nextElementSibling).toBeNull()
      expect(
        wrapper.get('[aria-label="Previous dweller page"]').attributes('disabled')
      ).toBeDefined()

      await wrapper.get('[aria-label="Next dweller page"]').trigger('click')
      expect(visibleIds()).toEqual(roster.slice(20, 40).map((d) => d.id))
      expect(wrapper.text()).toContain('21–40 of 45')
      await wrapper.get('[aria-label="Next dweller page"]').trigger('click')
      expect(visibleIds()).toEqual(roster.slice(40).map((d) => d.id))
      expect(wrapper.get('[aria-label="Next dweller page"]').attributes('disabled')).toBeDefined()
      await wrapper.get('[aria-label="Previous dweller page"]').trigger('click')
      expect(visibleIds()).toEqual(roster.slice(20, 40).map((d) => d.id))
    }
  )

  it('resets to the first page when filtered or sorted results are replaced', async () => {
    const wrapper = shallowMount(DwellersList, {
      props: baseProps({ dwellers: roster }),
      global: { stubs: { Button: false } },
    })
    await wrapper.get('[aria-label="Next dweller page"]').trigger('click')
    const filtered = [roster[42]!]
    await wrapper.setProps({ dwellers: filtered })
    expect(wrapper.findComponent({ name: 'DwellerListRow' }).props('dweller')).toEqual(filtered[0])
    expect(wrapper.find('[aria-label="Dweller pages"]').exists()).toBe(false)
  })

  it('preserves the page when changing layout and opens the dweller on that page', async () => {
    const wrapper = shallowMount(DwellersList, {
      props: baseProps({ dwellers: roster }),
      global: { stubs: { Button: false } },
    })
    await wrapper.get('[aria-label="Next dweller page"]').trigger('click')
    await wrapper.setProps({ viewMode: 'grid' })
    wrapper.findComponent({ name: 'DwellerGridItem' }).vm.$emit('click')
    expect(wrapper.emitted('view-details')).toEqual([['dweller-20']])
  })

  it('hides pagination for a single page and while loading', async () => {
    const wrapper = shallowMount(DwellersList, {
      props: baseProps({ dwellers: roster.slice(0, 20) }),
    })
    expect(wrapper.find('[aria-label="Dweller pages"]').exists()).toBe(false)
    await wrapper.setProps({ dwellers: roster, isLoading: true })
    expect(wrapper.find('[aria-label="Dweller pages"]').exists()).toBe(false)
  })

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

  it('keeps level below the name and does not add a short divider to the standard row', () => {
    const wrapper = mount(DwellersList, {
      props: baseProps({ dwellers: [dweller()] }),
      global: { stubs: { DwellerListRow: false } },
    })

    const identity = wrapper.get('.dweller-identity')
    expect(identity.text()).toContain('Sarah Lyons')
    expect(identity.text()).toContain('Level 5')
    expect(identity.find('.dweller-meta-divider').exists()).toBe(false)
  })
})
