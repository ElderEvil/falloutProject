import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ChildrenList from '@/modules/social/components/relationships/ChildrenList.vue'

// The component uses `const { filter: dwellerStore } = useDwellerStore()`
// so the mock must return an object with a `filter` property containing the dwellers array.
const mockDwellers: any[] = []

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    filter: { allDwellers: mockDwellers },
  }) as any,
}))

const child = {
  id: 'child-1',
  first_name: 'Test',
  last_name: 'Child',
  age_group: 'child',
  gender: 'male',
  rarity: 'common',
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
  thumbnail_url: null,
}

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
    mockDwellers.push({ ...child })

    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.text()).toContain('Test Child')
    expect(wrapper.text()).toContain('HP 80/100')
    expect(wrapper.text()).toContain('Happy 90%')
  })

  it('should keep SPECIAL stats in a compact row', () => {
    mockDwellers.push({ ...child })

    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    expect(wrapper.findAll('.stat-mini')).toHaveLength(7)
  })

  it('emits select with the child id when a card is clicked', async () => {
    mockDwellers.push({ ...child })

    const wrapper = mount(ChildrenList, {
      props: { vaultId: 'test-vault' },
      global: { plugins: [createPinia()] },
    })

    await wrapper.find('button').trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual(['child-1'])
  })
})
