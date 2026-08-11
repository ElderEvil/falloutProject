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
})
