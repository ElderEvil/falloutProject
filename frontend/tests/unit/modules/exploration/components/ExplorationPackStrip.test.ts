import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../../helpers/mocks'
import { createExploration } from '../../../helpers/explorationFixtures'
import { mount } from '@vue/test-utils'
import { Progress } from '@/core/components/ui/progress'
import ExplorationPackStrip from '@/modules/exploration/components/ExplorationPackStrip.vue'
import type { Exploration, LootItem } from '@/modules/exploration/stores/exploration'

vi.mock('@iconify/vue', () => createIconifyMock({ template: '<span class="icon-mock" />' }))

const baseExploration = createExploration({
  dweller_strength: 5,
  carry_capacity: 25,
  pack_slots_used: 12,
})

function loot(item_name: string, overrides: Partial<LootItem> = {}): LootItem {
  return {
    item_name,
    quantity: 1,
    rarity: 'common',
    item_type: 'junk',
    found_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function mountStrip(overrides: Partial<Exploration> = {}) {
  return mount(ExplorationPackStrip, {
    props: { exploration: { ...baseExploration, ...overrides } as Exploration },
  })
}

describe('ExplorationPackStrip', () => {
  it('renders the used / capacity count and one icon per carried item', () => {
    const wrapper = mountStrip({
      loot_collected: [loot('Scrap'), loot('Pistol', { item_type: 'weapon' }), loot('Vault Suit')],
    })

    expect(wrapper.find('.pack-count').text()).toBe('12 / 25')
    expect(wrapper.findAll('.pack-item')).toHaveLength(3)
    expect(wrapper.findComponent(Progress).props('modelValue')).toBe(48)
  })

  it('marks a full pack with warning text and a visible Pack full tag', () => {
    const wrapper = mountStrip({ pack_slots_used: 25 })

    expect(wrapper.find('.pack-count').text()).toBe('25 / 25')
    // Assert the semantic tone the meter is given, not the Tailwind class that paints it.
    expect(wrapper.findComponent(Progress).props('tone')).toBe('warning')
    expect(wrapper.text()).toContain('Pack full')
    expect(wrapper.findComponent(Progress).props('tone')).toBe('warning')
  })

  it('excludes stimpaks, radaways and equipped entries from the slot count', () => {
    const wrapper = mountStrip({
      pack_slots_used: undefined,
      loot_collected: [
        loot('Scrap', { quantity: 2 }),
        loot('Stimpak', { quantity: 3, item_type: 'stimpak' }),
        loot('RadAway', { quantity: 2, item_type: 'radaway' }),
        loot('Old Stim', { quantity: 1, item_type: undefined, item_name: 'Stimpak' }),
        loot('Combat Rifle', { item_type: 'weapon', equipped: true }),
      ],
    })

    expect(wrapper.find('.pack-count').text()).toBe('2 / 25')
    expect(wrapper.findAll('.pack-item')).toHaveLength(1)
  })

  it('derives capacity from Strength when the payload omits it', () => {
    const wrapper = mountStrip({ carry_capacity: undefined, pack_slots_used: undefined })

    expect(wrapper.find('.pack-count').text()).toBe('0 / 25')
  })

  it('caps the icon row at ten and shows a +N chip for the remainder', () => {
    const items = Array.from({ length: 13 }, (_, index) => loot(`Item ${index + 1}`))
    const wrapper = mountStrip({ loot_collected: items, pack_slots_used: 13 })

    expect(wrapper.findAll('.pack-item')).toHaveLength(10)
    expect(wrapper.find('.pack-overflow').text()).toBe('+3')
  })
})
