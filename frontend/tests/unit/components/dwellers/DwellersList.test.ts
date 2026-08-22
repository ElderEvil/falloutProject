import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import DwellersList from '@/modules/dwellers/components/DwellersList.vue'

describe('DwellersList', () => {
  it('renders the list layout for list mode', () => {
    const wrapper = shallowMount(DwellersList, {
      props: {
        dwellers: [],
        generatingAI: {},
        isLoading: false,
        rooms: [],
        viewMode: 'list',
      },
    })

    expect(wrapper.find('ul').exists()).toBe(true)
    expect(wrapper.find('.dweller-grid').exists()).toBe(false)
  })

  it('renders the grid layout for grid mode', () => {
    const wrapper = shallowMount(DwellersList, {
      props: {
        dwellers: [],
        generatingAI: {},
        isLoading: false,
        rooms: [],
        viewMode: 'grid',
      },
    })

    expect(wrapper.find('.dweller-grid').exists()).toBe(true)
  })

  it('shows the assigned room stat from the list API response', () => {
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
            is_adult: true,
            age_group: 'adult',
            gender: 'female',
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
        rooms: [{ id: 'room-1', name: 'Power Generator', ability: 'strength' }],
        viewMode: 'list',
      },
    })

    expect(wrapper.text()).toContain('STR')
    expect(wrapper.text()).toContain('8')
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
            is_adult: true,
            age_group: 'adult',
            gender: 'male',
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
    })

    expect(wrapper.find('.dweller-identity').classes()).toContain('w-44')
    expect(wrapper.find('h3').classes()).toContain('truncate')
    expect(wrapper.find('li').classes()).toContain('bg-surface-canvas')
    expect(wrapper.find('li').classes()).toContain('border-theme-primary/20')
  })
})
