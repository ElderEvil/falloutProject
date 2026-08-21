import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerStats from '@/modules/dwellers/components/stats/DwellerStats.vue'

const defaultProps = {
  S: 5,
  P: 4,
  E: 6,
  C: 3,
  I: 7,
  A: 2,
  L: 8,
}

describe('DwellerStats', () => {
  describe('Rendering', () => {
    it('should render all seven SPECIAL stat rows', () => {
      const wrapper = mount(DwellerStats, { props: defaultProps })

      const items = wrapper.findAll('.stat-item')
      expect(items).toHaveLength(7)
    })

    it('should render stat labels', () => {
      const wrapper = mount(DwellerStats, { props: defaultProps })

      const labels = wrapper.findAll('.stat-label')
      const text = labels.map((l) => l.text())
      expect(text).toEqual([
        'Strength',
        'Perception',
        'Endurance',
        'Charisma',
        'Intelligence',
        'Agility',
        'Luck',
      ])
    })

    it('should render stat values', () => {
      const wrapper = mount(DwellerStats, { props: defaultProps })

      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('5')
      expect(values[1].text()).toBe('4')
      expect(values[6].text()).toBe('8')
    })
  })

  describe('Highlight Stat', () => {
    it('should add stat-highlighted class to the matching row when highlightStat is set', () => {
      const wrapper = mount(DwellerStats, {
        props: { ...defaultProps, highlightStat: 'strength' },
      })

      const items = wrapper.findAll('.stat-item')
      expect(items[0].classes()).toContain('stat-highlighted')
      expect(items[1].classes()).not.toContain('stat-highlighted')
    })

    it('should show +1 badge on the highlighted row', () => {
      const wrapper = mount(DwellerStats, {
        props: { ...defaultProps, highlightStat: 'strength' },
      })

      const badge = wrapper.find('.stat-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('+1')
    })

    it('should not show +1 badge when highlightStat is not provided', () => {
      const wrapper = mount(DwellerStats, { props: defaultProps })

      const badge = wrapper.find('.stat-badge')
      expect(badge.exists()).toBe(false)
    })

    it('should not add stat-highlighted class when highlightStat is not provided', () => {
      const wrapper = mount(DwellerStats, { props: defaultProps })

      const items = wrapper.findAll('.stat-item')
      items.forEach((item) => {
        expect(item.classes()).not.toContain('stat-highlighted')
      })
    })

    it('should handle case-insensitive stat names', () => {
      const wrapper = mount(DwellerStats, {
        props: { ...defaultProps, highlightStat: 'STRENGTH' },
      })

      const items = wrapper.findAll('.stat-item')
      expect(items[0].classes()).toContain('stat-highlighted')
    })

    it('should highlight the correct stat for each SPECIAL letter', () => {
      const statMap = [
        { stat: 'perception', index: 1 },
        { stat: 'endurance', index: 2 },
        { stat: 'charisma', index: 3 },
        { stat: 'intelligence', index: 4 },
        { stat: 'agility', index: 5 },
        { stat: 'luck', index: 6 },
      ]

      statMap.forEach(({ stat, index }) => {
        const wrapper = mount(DwellerStats, {
          props: { ...defaultProps, highlightStat: stat },
        })

        const items = wrapper.findAll('.stat-item')
        expect(items[index].classes()).toContain('stat-highlighted')
        // Other rows should not be highlighted
        items.forEach((item, i) => {
          if (i !== index) {
            expect(item.classes()).not.toContain('stat-highlighted')
          }
        })
      })
    })
  })
})
