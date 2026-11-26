import { describe, it, expect } from 'vite-plus/test'
import { nextTick, ref } from 'vue'
import DwellerStats from '@/modules/dwellers/components/stats/DwellerStats.vue'
import {
  createMockDwellerDetailContext,
  mountWithDwellerContext,
} from '../../helpers/dwellerDetailContext'
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

const mountStats = (highlightStat?: string, overrides: object = {}) => {
  const ctx = createMockDwellerDetailContext({
    dweller: ref({ ...stats, ...overrides }) as never,
    highlightStat: ref(highlightStat) as never,
  })
  return { wrapper: mountWithDwellerContext(DwellerStats, { context: ctx }), ctx }
}

describe('DwellerStats', () => {
  describe('rendering', () => {
    it('renders the seven SPECIAL rows with exact labels and values', () => {
      const { wrapper } = mountStats()

      expect(wrapper.findAll('.stat-item')).toHaveLength(7)
      expect(wrapper.findAll('.stat-label').map((label) => label.text())).toEqual([
        'Strength',
        'Perception',
        'Endurance',
        'Charisma',
        'Intelligence',
        'Agility',
        'Luck',
      ])
      const values = wrapper.findAll('.stat-value')
      expect(values[0].text()).toBe('5')
      expect(values[1].text()).toBe('4')
      expect(values[6].text()).toBe('8')
    })

    it('renders taglines from the shared guide', () => {
      const { wrapper } = mountStats()

      const descriptions = wrapper.findAll('.stat-description').map((d) => d.text())
      expect(descriptions[0]).toContain('power rooms')
      expect(descriptions[3]).toContain('recruits')
    })
  })

  describe('highlight stat', () => {
    it.each([
      ['strength', 0],
      ['perception', 1],
      ['endurance', 2],
      ['charisma', 3],
      ['intelligence', 4],
      ['agility', 5],
      ['luck', 6],
      ['STRENGTH', 0],
    ])('highlights only the %s row', (stat, index) => {
      const { wrapper } = mountStats(stat)

      const items = wrapper.findAll('.stat-item')
      expect(items[index].classes()).toContain('stat-highlighted')
      items.forEach((item, i) => {
        if (i !== index) expect(item.classes()).not.toContain('stat-highlighted')
      })
    })

    it('shows the +1 badge with its fade animation on the highlighted row', () => {
      const { wrapper } = mountStats('strength')

      const items = wrapper.findAll('.stat-item')
      expect(items[0].classes()).toContain('stat-highlight-pulse')
      const badge = wrapper.find('.stat-badge')
      expect(badge.text()).toBe('+1')
      expect(badge.classes()).toContain('stat-badge-fade')
    })

    it('adds the badge when the highlighted stat changes, and none by default', async () => {
      const { wrapper, ctx } = mountStats()
      expect(wrapper.find('.stat-badge').exists()).toBe(false)
      wrapper.findAll('.stat-item').forEach((item) => {
        expect(item.classes()).not.toContain('stat-highlighted')
      })

      ctx.highlightStat.value = 'perception'
      await nextTick()

      expect(wrapper.find('.stat-badge').exists()).toBe(true)
    })
  })

  describe('item-improved stats', () => {
    it('shows the effective value with its breakdown', () => {
      const { wrapper } = mountStats(undefined, {
        outfit: { name: 'Vault Suit', strength: 5 },
        identity_modifiers: {},
      })

      expect(wrapper.findAll('.stat-value')[0].text()).toBe('10')
      const breakdowns = wrapper.findAll('.stat-breakdown')
      expect(breakdowns).toHaveLength(1)
      expect(breakdowns[0].text()).toBe('5 → 10 (+5 Vault Suit)')
    })

    it('renders no breakdown without bonuses', () => {
      const { wrapper } = mountStats()

      expect(wrapper.find('.stat-breakdown').exists()).toBe(false)
    })
  })

  describe('bonus bar segments', () => {
    const mountWithBonus = (overrides: object) =>
      mountStats(undefined, { outfit: null, identity_modifiers: {}, ...overrides }).wrapper

    it('renders the base segment only without bonuses', () => {
      const wrapper = mountWithBonus({})

      expect(wrapper.findAll('.stat-fill-base')[0].attributes('style')).toContain('width: 50%')
      expect(wrapper.find('.stat-fill-bonus').exists()).toBe(false)
      expect(wrapper.find('.stat-tick').exists()).toBe(false)
    })

    it('stacks a striped bonus segment on the base', () => {
      const wrapper = mountWithBonus({ outfit: { name: 'Vault Suit', strength: 5 } })

      expect(wrapper.findAll('.stat-fill-base')[0].attributes('style')).toContain('width: 50%')
      const bonus = wrapper.find('.stat-fill-bonus')
      expect(bonus.attributes('style')).toContain('width: 50%')
      expect(bonus.classes()).not.toContain('stat-overflow')
    })

    it('clamps the bonus segment and glows on partial overflow', () => {
      const wrapper = mountWithBonus({ S: 8, outfit: { name: 'Combat Armor', strength: 5 } })

      const bonus = wrapper.find('.stat-fill-bonus')
      expect(bonus.attributes('style')).toContain('width: 20%')
      expect(bonus.classes()).toContain('stat-overflow')
    })

    it('flags overflow when the effective value exceeds 10', () => {
      const wrapper = mountWithBonus({ S: 10, outfit: { name: 'Power Armor', strength: 5 } })

      expect(wrapper.find('.stat-overflow-bar').exists()).toBe(true)
      expect(wrapper.find('.stat-bar').attributes('title')).toContain('= 15 effective')
    })

    it('renders the effective fill plus a base tick on a penalty', () => {
      const wrapper = mountWithBonus({ identity_modifiers: { strength: -3 } })

      expect(wrapper.findAll('.stat-fill-base')[0].attributes('style')).toContain('width: 20%')
      const tick = wrapper.find('.stat-tick')
      expect(tick.attributes('style')).toContain('left: 50%')
    })

    it('exposes the breakdown in the bar title and aria-label', () => {
      const wrapper = mountWithBonus({ outfit: { name: 'Vault Suit', strength: 5 } })

      const bar = wrapper.findAll('.stat-bar')[0]
      expect(bar.attributes('title')).toBe('Base 5 + +5 Vault Suit = 10 effective')
      expect(bar.attributes('aria-label')).toContain('Strength: Base 5')
    })
  })

  it('opens the field guide modal from the info button', async () => {
    const { wrapper } = mountStats()

    const modal = wrapper.findComponent({ name: 'SpecialGuideModal' })
    expect(modal.props('modelValue')).toBe(false)

    await wrapper.find('button[aria-label="Open SPECIAL field guide"]').trigger('click')

    expect(modal.props('modelValue')).toBe(true)
  })
})
