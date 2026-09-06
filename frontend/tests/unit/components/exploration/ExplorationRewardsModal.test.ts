import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { UModal } from '@/core/components/ui'
import ExplorationRewardsModal from '@/modules/exploration/components/ExplorationRewardsModal.vue'
import type { RewardsSummary } from '@/modules/exploration/stores/exploration'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const { mockResolve } = vi.hoisted(() => ({ mockResolve: vi.fn() }))

vi.mock('@/modules/exploration/stores/exploration', () => ({
  useExplorationStore: () => ({ resolveOverflowItem: mockResolve }),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const item = (name: string) => ({
  item_name: name,
  quantity: 1,
  rarity: 'Common',
  found_at: '2026-01-01T00:00:00Z',
})

const rewardsWithOverflow = {
  caps: 100,
  items: [item('Wonderglue')],
  overflow_items: [item('Dropped A'), item('Dropped B')],
  experience: 50,
  distance: 10,
  enemies_defeated: 2,
  events_encountered: 3,
} as RewardsSummary

const mountModal = (rewards: RewardsSummary | null = rewardsWithOverflow, explorationId = 'exp-1') =>
  mount(ExplorationRewardsModal, {
    props: { show: true, rewards, dwellerName: 'Lucy MacLean', explorationId },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

describe('ExplorationRewardsModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockResolve.mockReset()
    mockResolve.mockResolvedValue({ caps_granted: 0, unclaimed_loot: [] })
  })

  it('uses the shared wide terminal modal like other popups', () => {
    const wrapper = mountModal()

    expect(wrapper.findComponent(UModal).props('size')).toBe('wide')
    expect(wrapper.findComponent(UModal).props('modelValue')).toBe(true)
  })

  it('labels stored and undecided items truthfully', () => {
    const wrapper = mountModal()

    expect(wrapper.text()).toContain('Lucy MacLean has returned from the wasteland!')
    expect(wrapper.text()).toContain('Stored in Vault')
    expect(wrapper.text()).toContain('Wonderglue')
    expect(wrapper.text()).toContain('Storage Full — Needs Decision')
    expect(wrapper.text()).toContain('Dropped A')
    expect(wrapper.text()).not.toContain('No items found')
  })

  it('shows the plain empty state only when nothing was found at all', () => {
    const wrapper = mountModal({ ...rewardsWithOverflow, items: [], overflow_items: [] })

    expect(wrapper.text()).toContain('No items found during this exploration')
  })

  it('resolves overflow per item and unblocks collecting when empty', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 0, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal()
    const takeButtons = wrapper.findAll('.overflow-actions button')

    expect(wrapper.get('.collect-btn').attributes('disabled')).toBeDefined()

    await takeButtons[0]!.trigger('click')
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'take', 0, 'test-token')
    expect(wrapper.text()).not.toContain('Dropped A')
    expect(wrapper.text()).toContain('Dropped B')
    expect(wrapper.get('.collect-btn').attributes('disabled')).toBeDefined()

    await wrapper.get('.collect-btn').trigger('click')
    expect(wrapper.emitted('close')).toBeUndefined()
  })

  it('sells a single overflow item for caps', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal()
    const sellButtons = wrapper
      .findAll('.overflow-actions button')
      .filter((button) => button.text() === 'Sell')

    await sellButtons[0]!.trigger('click')
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'sell', 0, 'test-token')
    expect(wrapper.text()).not.toContain('Dropped A')
  })

  it('uses the rewards exploration ID when a stale caller ID is supplied', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal({ ...rewardsWithOverflow, exploration_id: 'authoritative-exp' }, 'stale-exp')

    await wrapper
      .findAll('.overflow-actions button')
      .find((button) => button.text() === 'Sell')!
      .trigger('click')

    expect(mockResolve).toHaveBeenCalledWith('authoritative-exp', 'sell', 0, 'test-token')
  })

  it('allows a legacy overflow report to close after the missing record is reported', async () => {
    mockResolve.mockRejectedValueOnce({ response: { status: 404 } })
    const wrapper = mountModal()

    await wrapper.findAll('.overflow-actions button')[0]!.trigger('click')

    expect(wrapper.text()).toContain('This report predates overflow resolution')
    expect(wrapper.get('.collect-btn').attributes('disabled')).toBeUndefined()
    await wrapper.get('.collect-btn').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('sells every overflow item without relying on a delayed prop update', async () => {
    mockResolve
      .mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
      .mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [] })
    const wrapper = mountModal()

    await wrapper.get('.sell-all-btn').trigger('click')

    expect(mockResolve).toHaveBeenNthCalledWith(1, 'exp-1', 'sell', 0, 'test-token')
    expect(mockResolve).toHaveBeenNthCalledWith(2, 'exp-1', 'sell', 0, 'test-token')
    expect(wrapper.find('.sell-all-btn').exists()).toBe(false)
  })

  it('collects once every overflow item is decided', async () => {
    const wrapper = mountModal({ ...rewardsWithOverflow, overflow_items: [] })

    await wrapper.get('.collect-btn').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits one close event when the modal close control is used', async () => {
    const wrapper = mountModal({ ...rewardsWithOverflow, overflow_items: [] })

    await wrapper.get('[aria-label="Close modal"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
