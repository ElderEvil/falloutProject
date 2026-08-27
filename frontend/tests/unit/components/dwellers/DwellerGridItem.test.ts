import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerGridItem from '@/modules/dwellers/components/grid/DwellerGridItem.vue'

describe('DwellerGridItem', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const mockDweller = {
    id: '123',
    first_name: 'John',
    last_name: 'Doe',
    level: 5,
    health: 80,
    max_health: 100,
    happiness: 75,
    strength: 8,
    perception: 6,
    endurance: 7,
    charisma: 5,
    intelligence: 4,
    agility: 6,
    luck: 7,
    status: 'working',
    room_id: 'room-123',
  }

  const mockRoom = {
    id: 'room-123',
    name: 'Power Generator',
    ability: 'strength',
  }

  describe('Job Stat Display', () => {
    const mockStat = {
      icon: 'mdi:arm-flex',
      label: 'STR',
      value: 8,
      isPower: false,
    }

    it('should display relevant stat when dweller has room assignment', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: mockRoom.name,
          roomStat: mockStat,
        },
      })

      expect(wrapper.text()).toContain('STR')
      expect(wrapper.text()).toContain('8')
    })

    it('should display the stat icon for the room', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: mockRoom.name,
          roomStat: { ...mockStat, icon: 'mdi:test-tube' },
        },
      })

      const jobStat = wrapper.find('.job-stat')
      expect(jobStat.exists()).toBe(true)
      expect(wrapper.find('.job-stat-icon').exists()).toBe(true)
    })

    it('should not display job stat when roomStat is absent', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
        },
      })

      const jobStat = wrapper.find('.job-stat')
      expect(jobStat.exists()).toBe(false)
    })

    it('should apply green color class for high stats (7-10)', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: mockRoom.name,
          roomStat: { ...mockStat, value: 8 },
        },
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-green-400')
    })

    it('should apply yellow color class for medium stats (4-6)', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: 'Science Lab',
          roomStat: { icon: 'mdi:brain', label: 'INT', value: 5, isPower: false },
        },
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-yellow-400')
    })

    it('should apply red color class for low stats (1-3)', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: 'Radio Station',
          roomStat: { icon: 'mdi:broadcast', label: 'CHA', value: 2, isPower: false },
        },
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-red-400')
    })

    it('should apply orange color class for combat power (arena) stats', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: 'Arena',
          roomStat: { icon: 'mdi:sword-cross', label: 'Power', value: 18, isPower: true },
        },
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-orange-400')
    })

    it('should render the provided label and value', () => {
      const testCases = [
        { stat: { icon: 'mdi:arm-flex', label: 'STR', value: 8, isPower: false } },
        { stat: { icon: 'mdi:eye', label: 'PER', value: 6, isPower: false } },
        { stat: { icon: 'mdi:heart', label: 'END', value: 7, isPower: false } },
        { stat: { icon: 'mdi:account-voice', label: 'CHA', value: 5, isPower: false } },
        { stat: { icon: 'mdi:brain', label: 'INT', value: 4, isPower: false } },
        { stat: { icon: 'mdi:run', label: 'AGI', value: 6, isPower: false } },
        { stat: { icon: 'mdi:four-leaf-clover', label: 'LCK', value: 7, isPower: false } },
      ]

      testCases.forEach(({ stat }) => {
        const wrapper = mount(DwellerGridItem, {
          props: {
            dweller: mockDweller,
            roomName: 'Test Room',
            roomStat: stat,
          },
        })

        const jobStat = wrapper.find('.job-stat')
        expect(jobStat.text()).toContain(stat.label)
        expect(jobStat.text()).toContain(stat.value.toString())
      })
    })
  })

  describe('Component Structure', () => {
    it('should render dweller name', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
        },
      })

      expect(wrapper.text()).toContain('John Doe')
    })

    it('should render level information', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
        },
      })

      expect(wrapper.text()).toContain('5') // Level
    })
  })
})
