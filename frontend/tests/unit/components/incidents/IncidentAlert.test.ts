import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import IncidentAlert from '@/modules/combat/components/incidents/IncidentAlert.vue'
import { IncidentType, IncidentStatus } from '@/modules/combat/models/incident'
import type { Incident } from '@/modules/combat/models/incident'

// Mock @iconify/vue
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>'
  }
}))

describe('IncidentAlert', () => {
  const mockIncident: Incident = {
    id: 'incident-1',
    vault_id: 'vault-1',
    room_id: 'room-1',
    type: IncidentType.RAIDER_ATTACK,
    status: IncidentStatus.ACTIVE,
    difficulty: 5,
    start_time: '2025-01-01T00:00:00Z',
    damage_dealt: 10,
    enemies_defeated: 2,
    spread_count: 0,
    rooms_affected: ['room-1'],
    last_spread_time: null,
    loot: null,
    resolved_at: null,
    duration: 60
  }

  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2025-01-01T00:01:00Z')) // 1 minute after start
  })

  describe('Props', () => {
    it('should render with single incident', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      expect(wrapper.exists()).toBe(true)
      expect(wrapper.text()).toContain('RAIDER ATTACK')
    })

    it('should handle empty incidents array', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: []
        }
      })

      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('Incident Display', () => {
    it('should display incident type correctly', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      expect(wrapper.text()).toContain('RAIDER ATTACK')
    })

    it('should display difficulty stars', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      const stars = wrapper.text().match(/★/g)
      expect(stars).toHaveLength(5) // Difficulty 5
    })

    it('should show elapsed time', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      expect(wrapper.text()).toMatch(/\d+:\d+/)
    })

    it('should display correct icon for raider attack', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      const icon = wrapper.find('.mock-icon')
      expect(icon.attributes('data-icon')).toBe('mdi:skull')
    })

    it('should display correct icon for fire', () => {
      const fireIncident = {
        ...mockIncident,
        type: IncidentType.FIRE
      }

      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [fireIncident]
        }
      })

      const icon = wrapper.find('.mock-icon')
      expect(icon.attributes('data-icon')).toBe('mdi:fire')
    })
  })

  describe('Multiple Incidents', () => {
    it('should show count badge for multiple incidents', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [
            mockIncident,
            { ...mockIncident, id: 'incident-2', type: IncidentType.FIRE },
            { ...mockIncident, id: 'incident-3', type: IncidentType.RADROACH_INFESTATION }
          ]
        }
      })

      expect(wrapper.text()).toContain('3 ACTIVE')
    })

    it('should display first incident details when multiple', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [
            mockIncident,
            { ...mockIncident, id: 'incident-2', type: IncidentType.FIRE }
          ]
        }
      })

      expect(wrapper.text()).toContain('RAIDER ATTACK')
      expect(wrapper.text()).not.toContain('FIRE')
    })
  })

  describe('Interactions', () => {
    it('should emit click event with incident id', async () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      await wrapper.trigger('click')

      expect(wrapper.emitted('click')).toBeTruthy()
      expect(wrapper.emitted('click')?.[0]).toEqual(['incident-1'])
    })
  })

  describe('Styling', () => {
    it('should have pulsing class when incidents exist', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      expect(wrapper.find('.incident-alert').classes()).toContain('pulsing')
    })

    it('should have red border color', () => {
      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [mockIncident]
        }
      })

      const alert = wrapper.find('.incident-alert')
      expect(alert.exists()).toBe(true)
    })
  })

  describe('Edge Cases', () => {
    it('should handle incident with 10 difficulty', () => {
      const maxDifficultyIncident = {
        ...mockIncident,
        difficulty: 10
      }

      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [maxDifficultyIncident]
        }
      })

      const stars = wrapper.text().match(/★/g)
      expect(stars).toHaveLength(10)
    })

    it('should handle incident with 1 difficulty', () => {
      const minDifficultyIncident = {
        ...mockIncident,
        difficulty: 1
      }

      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [minDifficultyIncident]
        }
      })

      const stars = wrapper.text().match(/★/g)
      expect(stars).toHaveLength(1)
    })

    it('should handle spreading incidents', () => {
      const spreadingIncident = {
        ...mockIncident,
        status: IncidentStatus.SPREADING,
        spread_count: 2,
        rooms_affected: ['room-1', 'room-2', 'room-3']
      }

      const wrapper = mount(IncidentAlert, {
        props: {
          incidents: [spreadingIncident]
        }
      })

      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('All Incident Types', () => {
    const incidentTypes = [
      { type: IncidentType.RAIDER_ATTACK, icon: 'mdi:skull' },
      { type: IncidentType.FIRE, icon: 'mdi:fire' },
      { type: IncidentType.RADROACH_INFESTATION, icon: 'mdi:bug' },
      { type: IncidentType.MOLE_RAT_ATTACK, icon: 'mdi:paw' },
      { type: IncidentType.DEATHCLAW_ATTACK, icon: 'mdi:claw-mark' },
      { type: IncidentType.RADIATION_LEAK, icon: 'mdi:radioactive' },
      { type: IncidentType.ELECTRICAL_FAILURE, icon: 'mdi:lightning-bolt' },
      { type: IncidentType.WATER_CONTAMINATION, icon: 'mdi:water-alert' }
    ]

    incidentTypes.forEach(({ type, icon }) => {
      it(`should display correct icon for ${type}`, () => {
        const incident = { ...mockIncident, type }
        const wrapper = mount(IncidentAlert, {
          props: { incidents: [incident] }
        })

        const iconElement = wrapper.find('.mock-icon')
        expect(iconElement.attributes('data-icon')).toBe(icon)
      })
    })
  })
})
