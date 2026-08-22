import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ChildrenList from '@/modules/social/components/relationships/ChildrenList.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'

// The component uses `const { filter: dwellerStore } = useDwellerStore()`
// so the mock must return an object with a `filter` property containing the dwellers array.
const mockDwellers: any[] = []

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    filter: { dwellers: mockDwellers },
  }) as any,
}))

describe('ChildrenList', () => {
  beforeEach(() => {
    mockDwellers.length = 0
  })

  it('should not render fake growth progress bar', () => {
    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.find('.growth-bar').exists()).toBe(false)
    expect(wrapper.find('.growth-fill').exists()).toBe(false)
    expect(wrapper.find('.growth-time').exists()).toBe(false)
  })

  it('should not contain hardcoded fake text', () => {
    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.text()).not.toContain('Growth Progress')
    expect(wrapper.text()).not.toContain('1.5 hours')
    expect(wrapper.text()).not.toContain('50%')
  })

  it('should still render real data fields', () => {
    mockDwellers.push({
      id: 'child-1',
      first_name: 'Test',
      last_name: 'Child',
      age_group: 'child',
      health: 80,
      max_health: 100,
      happiness: 90,
      strength: 5,
      perception: 5,
      endurance: 5,
      charisma: 5,
      intelligence: 5,
      agility: 5,
      luck: 5,
    })

    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    const childCard = wrapper.find('.child-card')
    expect(childCard.exists()).toBe(true)

    // Each detail-row shows one field — check both individually
    const detailRows = wrapper.findAll('[class*="detail-row"]')
    const rowTexts = detailRows.map((r) => r.text())
    expect(rowTexts.join(' ')).toContain('Health')
    expect(rowTexts.join(' ')).toContain('Happiness')
  })

  it('should keep SPECIAL stats in a compact row', () => {
    mockDwellers.push({
      id: 'child-1',
      first_name: 'Test',
      last_name: 'Child',
      age_group: 'child',
      health: 80,
      max_health: 100,
      happiness: 90,
      strength: 5,
      perception: 5,
      endurance: 5,
      charisma: 5,
      intelligence: 5,
      agility: 5,
      luck: 5,
    })

    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    const specialStats = wrapper.find('.special-preview')
    expect(specialStats.exists()).toBe(true)
    expect(specialStats.findAll('.stat-mini')).toHaveLength(7)
  })
})
