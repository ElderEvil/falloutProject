import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProfileStats from '@/components/profile/ProfileStats.vue'

describe('ProfileStats', () => {
  const mockStatistics = {
    totalDwellersCreated: 10,
    totalCapsEarned: 5000,
    totalExplorations: 25,
    totalRoomsBuilt: 8
  }

  describe('Component Rendering', () => {
    it('should render component with title', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: mockStatistics
        }
      })

      expect(wrapper.text()).toContain('Vault Statistics')
    })

    it('should render all statistics when data is provided', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: mockStatistics
        }
      })

      expect(wrapper.text()).toContain('Total Dwellers Created')
      expect(wrapper.text()).toContain('Total Caps Earned')
      expect(wrapper.text()).toContain('Total Explorations')
      expect(wrapper.text()).toContain('Total Rooms Built')
    })

    it('should display correct values for each statistic', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: mockStatistics
        }
      })

      const statValues = wrapper.findAll('.font-bold.text-xl')
      expect(statValues[0].text()).toBe('10')
      expect(statValues[1].text()).toBe('5000')
      expect(statValues[2].text()).toBe('25')
      expect(statValues[3].text()).toBe('8')
    })

    it('should show placeholder message when statistics is null', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: null
        }
      })

      expect(wrapper.text()).toContain('No statistics available')
    })
  })

  describe('Statistics Display', () => {
    it('should display zero values correctly', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: {
            totalDwellersCreated: 0,
            totalCapsEarned: 0,
            totalExplorations: 0,
            totalRoomsBuilt: 0
          }
        }
      })

      const statValues = wrapper.findAll('.font-bold.text-xl')
      expect(statValues.length).toBe(4)
      statValues.forEach((value) => {
        expect(value.text()).toBe('0')
      })
    })

    it('should display large numbers correctly', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: {
            totalDwellersCreated: 999,
            totalCapsEarned: 1000000,
            totalExplorations: 5000,
            totalRoomsBuilt: 500
          }
        }
      })

      const statValues = wrapper.findAll('.font-bold.text-xl')
      expect(statValues[0].text()).toBe('999')
      expect(statValues[1].text()).toBe('1000000')
      expect(statValues[2].text()).toBe('5000')
      expect(statValues[3].text()).toBe('500')
    })
  })

  describe('Styling', () => {
    it('should apply correct container styles', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: mockStatistics
        }
      })

      const container = wrapper.find('.bg-gray-800')
      expect(container.exists()).toBe(true)
      expect(container.classes()).toContain('rounded-lg')
      expect(container.classes()).toContain('p-6')
    })

    it('should render stat items with correct layout', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: mockStatistics
        }
      })

      const statItems = wrapper.findAll('.flex.justify-between.items-center')
      expect(statItems.length).toBe(4)

      statItems.forEach((item) => {
        expect(item.classes()).toContain('p-3')
        expect(item.classes()).toContain('rounded')
      })
    })
  })

  describe('Conditional Rendering', () => {
    it('should not render stats when statistics is null', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: null
        }
      })

      expect(wrapper.find('.space-y-4').exists()).toBe(false)
      expect(wrapper.findAll('.flex.justify-between').length).toBe(0)
    })

    it('should render stats when statistics is provided', () => {
      const wrapper = mount(ProfileStats, {
        props: {
          statistics: mockStatistics
        }
      })

      expect(wrapper.find('.space-y-4').exists()).toBe(true)
      expect(wrapper.findAll('.flex.justify-between').length).toBe(4)
    })
  })
})
