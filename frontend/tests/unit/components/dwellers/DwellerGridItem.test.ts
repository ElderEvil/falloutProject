import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DwellerGridItem from '@/components/dwellers/DwellerGridItem.vue'

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
    room_id: 'room-123'
  }

  const mockRoom = {
    id: 'room-123',
    name: 'Power Generator',
    ability: 'strength'
  }

  describe('Job Stat Display', () => {
    it('should display relevant stat when dweller has room assignment', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: mockRoom.name,
          roomAbility: mockRoom.ability
        }
      })

      // Should show strength stat (💪 STR: 8)
      expect(wrapper.text()).toContain('STR')
      expect(wrapper.text()).toContain('8')
    })

    it('should display correct stat icon based on room ability', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller,
          roomName: mockRoom.name,
          roomAbility: 'strength'
        }
      })

      const jobStat = wrapper.find('.job-stat')
      expect(jobStat.exists()).toBe(true)
      expect(jobStat.text()).toContain('💪') // Strength icon
    })

    it('should not display job stat when dweller has no room', () => {
      const unassignedDweller = { ...mockDweller, room_id: null }

      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: unassignedDweller,
          roomAbility: undefined
        }
      })

      const jobStat = wrapper.find('.job-stat')
      expect(jobStat.exists()).toBe(false)
    })

    it('should apply green color class for high stats (7-10)', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller, // strength = 8
          roomName: mockRoom.name,
          roomAbility: 'strength'
        }
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-green-400')
    })

    it('should apply yellow color class for medium stats (4-6)', () => {
      const mediumStatDweller = { ...mockDweller, intelligence: 5 }

      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mediumStatDweller,
          roomName: 'Science Lab',
          roomAbility: 'intelligence'
        }
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-yellow-400')
    })

    it('should apply red color class for low stats (1-3)', () => {
      const lowStatDweller = { ...mockDweller, charisma: 2 }

      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: lowStatDweller,
          roomName: 'Radio Station',
          roomAbility: 'charisma'
        }
      })

      const statValue = wrapper.find('.job-stat-value')
      expect(statValue.classes()).toContain('text-red-400')
    })

    it('should display correct stat label for each SPECIAL attribute', () => {
      const testCases = [
        { ability: 'strength', label: 'STR', value: mockDweller.strength, icon: '💪' },
        { ability: 'perception', label: 'PER', value: mockDweller.perception, icon: '👁️' },
        { ability: 'endurance', label: 'END', value: mockDweller.endurance, icon: '❤️' },
        { ability: 'charisma', label: 'CHA', value: mockDweller.charisma, icon: '💬' },
        { ability: 'intelligence', label: 'INT', value: mockDweller.intelligence, icon: '🧠' },
        { ability: 'agility', label: 'AGI', value: mockDweller.agility, icon: '⚡' },
        { ability: 'luck', label: 'LCK', value: mockDweller.luck, icon: '🍀' }
      ]

      testCases.forEach(({ ability, label, value, icon }) => {
        const wrapper = mount(DwellerGridItem, {
          props: {
            dweller: mockDweller,
            roomName: 'Test Room',
            roomAbility: ability
          }
        })

        const jobStat = wrapper.find('.job-stat')
        expect(jobStat.text()).toContain(icon)
        expect(jobStat.text()).toContain(label)
        expect(jobStat.text()).toContain(value.toString())
      })
    })
  })

  describe('Component Structure', () => {
    it('should render dweller name', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller
        }
      })

      expect(wrapper.text()).toContain('John Doe')
    })

    it('should render level information', () => {
      const wrapper = mount(DwellerGridItem, {
        props: {
          dweller: mockDweller
        }
      })

      expect(wrapper.text()).toContain('5') // Level
    })
  })
})
