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

  describe('Item-Improved Stats', () => {
    function mountWithOutfit() {
      const dweller = {
        ...stats,
        outfit: { name: 'Vault Suit', strength: 5 },
        identity_modifiers: {},
      } as unknown as Dweller
      const ctx = createMockDwellerDetailContext({
        dweller: ref(dweller) as never,
        highlightStat: ref(undefined) as never,
      })
      return mountWithDwellerContext(DwellerStats, { context: ctx })
    }

    it('should show effective value when outfit improves a stat', () => {
      const wrapper = mountWithOutfit()
      expect(wrapper.findAll('.stat-value')[0].text()).toBe('10')
    })

    it('should render base to effective breakdown with source', () => {
      const wrapper = mountWithOutfit()
      const breakdowns = wrapper.findAll('.stat-breakdown')
      expect(breakdowns).toHaveLength(1)
      expect(breakdowns[0].text()).toBe('5 → 10 (+5 Vault Suit)')
    })

    it('should render no breakdown without bonuses', () => {
      const { wrapper } = mountStats()
      expect(wrapper.find('.stat-breakdown').exists()).toBe(false)
    })
  })

  describe('Bonus Bar Segments', () => {
    function mountWithBonus(overrides: object) {
      const dweller = {
        ...stats,
        outfit: null,
        identity_modifiers: {},
        ...overrides,
      } as unknown as Dweller
      const ctx = createMockDwellerDetailContext({
        dweller: ref(dweller) as never,
        highlightStat: ref(undefined) as never,
      })
      return mountWithDwellerContext(DwellerStats, { context: ctx })
    }

    it('should render base segment only without bonuses', () => {
      const wrapper = mountWithBonus({})
      const base = wrapper.findAll('.stat-fill-base')[0]
      expect(base.attributes('style')).toContain('width: 50%')
      expect(wrapper.find('.stat-fill-bonus').exists()).toBe(false)
      expect(wrapper.find('.stat-tick').exists()).toBe(false)
    })

    it('should stack striped bonus segment on base', () => {
      const wrapper = mountWithBonus({ outfit: { name: 'Vault Suit', strength: 5 } })
      const base = wrapper.findAll('.stat-fill-base')[0]
      const bonus = wrapper.find('.stat-fill-bonus')
      expect(base.attributes('style')).toContain('width: 50%')
      expect(bonus.exists()).toBe(true)
      expect(bonus.attributes('style')).toContain('width: 50%')
      expect(bonus.classes()).not.toContain('stat-overflow')
    })

    it('should clamp bonus segment and glow on partial overflow', () => {
      const wrapper = mountWithBonus({ S: 8, outfit: { name: 'Combat Armor', strength: 5 } })
      const bonus = wrapper.find('.stat-fill-bonus')
      expect(bonus.attributes('style')).toContain('width: 20%')
      expect(bonus.classes()).toContain('stat-overflow')
    })

    it('should flag overflow when effective exceeds 10', () => {
      const wrapper = mountWithBonus({ S: 10, outfit: { name: 'Power Armor', strength: 5 } })
      expect(wrapper.find('.stat-overflow-bar').exists()).toBe(true)
      expect(wrapper.find('.stat-bar').attributes('title')).toContain('= 15 effective')
    })

    it('should render effective fill plus base tick on penalty', () => {
      const wrapper = mountWithBonus({ identity_modifiers: { strength: -3 } })
      const base = wrapper.findAll('.stat-fill-base')[0]
      expect(base.attributes('style')).toContain('width: 20%')
      const tick = wrapper.find('.stat-tick')
      expect(tick.exists()).toBe(true)
      expect(tick.attributes('style')).toContain('left: 50%')
    })

    it('should expose breakdown in bar title and aria-label', () => {
      const wrapper = mountWithBonus({ outfit: { name: 'Vault Suit', strength: 5 } })
      const bar = wrapper.findAll('.stat-bar')[0]
      expect(bar.attributes('title')).toBe('Base 5 + +5 Vault Suit = 10 effective')
      expect(bar.attributes('aria-label')).toContain('Strength: Base 5')
    })

    it('should render taglines from the shared guide', () => {
      const { wrapper } = mountStats()
      const descriptions = wrapper.findAll('.stat-description').map((d) => d.text())
      expect(descriptions[0]).toContain('power rooms')
      expect(descriptions[3]).toContain('recruits')
    })
  })

  describe('Field Guide', () => {
    it('should open the guide modal from the info button', async () => {
      const { wrapper } = mountStats()
      const modal = wrapper.findComponent({ name: 'SpecialGuideModal' })
      expect(modal.props('modelValue')).toBe(false)
      await wrapper.find('button[aria-label="Open SPECIAL field guide"]').trigger('click')
      expect(modal.props('modelValue')).toBe(true)
    })
  })
})
