import { describe, it, expect } from 'vitest'
import { nextTick, ref } from 'vue'
import DwellerStats from '@/modules/dwellers/components/stats/DwellerStats.vue'
import { createMockDwellerDetailContext, mountWithDwellerContext } from '../../helpers/dwellerDetailContext'
import type { Dweller } from '@/modules/dwellers/models/dweller'

const stats = {
  S: 5,
  P: 4,
  E: 6,
  C: 3,
  I: 7,
  A: 2,
  L: 8,
} as unknown as Dweller

function mountStats(highlightStat?: string) {
  const ctx = createMockDwellerDetailContext({
    dweller: ref(stats) as never,
    highlightStat: ref(highlightStat) as never,
  })
  const wrapper = mountWithDwellerContext(DwellerStats, { context: ctx })
  return { wrapper, ctx }
}

describe('DwellerStats', () => {
  describe('Rendering', () => {
    it('should render all seven SPECIAL stat rows', () => {
      const { wrapper } = mountStats()
      expect(wrapper.findAll('.stat-item')).toHaveLength(7)
    })

    it('should render stat labels', () => {
      const { wrapper } = mountStats()
      const labels = wrapper.findAll('.stat-label').map((l) => l.text())
      expect(labels).toEqual([
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
      const { wrapper } = mountStats()
      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('5')
      expect(values[1].text()).toBe('4')
      expect(values[6].text()).toBe('8')
    })
  })

  describe('Highlight Stat', () => {
    it('should add stat-highlighted class to the matching row when highlightStat is set', () => {
      const { wrapper } = mountStats('strength')
      const items = wrapper.findAll('.stat-item')
      expect(items[0].classes()).toContain('stat-highlighted')
      expect(items[0].classes()).toContain('stat-highlight-pulse')
      expect(items[1].classes()).not.toContain('stat-highlighted')
    })

    it('should show +1 badge on the highlighted row', () => {
      const { wrapper } = mountStats('strength')
      const badge = wrapper.find('.stat-badge')
      expect(badge.exists()).toBe(true)
      expect(badge.text()).toBe('+1')
      expect(badge.classes()).toContain('stat-badge-fade')
    })

    it('restarts the badge when the highlighted stat changes', async () => {
      const { wrapper, ctx } = mountStats()
      ctx.highlightStat.value = 'perception'
      await nextTick()
      expect(wrapper.find('.stat-badge').exists()).toBe(true)
    })

    it('should not show +1 badge when highlightStat is not provided', () => {
      const { wrapper } = mountStats()
      expect(wrapper.find('.stat-badge').exists()).toBe(false)
    })

    it('should not add stat-highlighted class when highlightStat is not provided', () => {
      const { wrapper } = mountStats()
      wrapper.findAll('.stat-item').forEach((item) => {
        expect(item.classes()).not.toContain('stat-highlighted')
      })
    })

    it('should handle case-insensitive stat names', () => {
      const { wrapper } = mountStats('STRENGTH')
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
        const { wrapper } = mountStats(stat)
        const items = wrapper.findAll('.stat-item')
        expect(items[index].classes()).toContain('stat-highlighted')
        items.forEach((item, i) => {
          if (i !== index) {
            expect(item.classes()).not.toContain('stat-highlighted')
          }
        })
      })
    })
  })
})
