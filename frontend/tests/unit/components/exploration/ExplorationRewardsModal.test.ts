import { beforeEach, describe, expect, it, vi } from 'vite-plus/test'

import { createIconifyMock, createToastMock } from '../../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Dialog } from '@/core/components/ui/dialog'
import ExplorationRewardsModal from '@/modules/exploration/components/ExplorationRewardsModal.vue'
import type { RewardsSummary } from '@/modules/exploration/stores/exploration'

vi.mock('@iconify/vue', () => createIconifyMock())

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

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

const mountModal = (
  rewards: RewardsSummary | null = rewardsWithOverflow,
  explorationId = 'exp-1',
  pendingOnly = false
) =>
  mount(ExplorationRewardsModal, {
    props: { show: true, rewards, dwellerName: 'Lucy MacLean', explorationId, pendingOnly },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

describe('ExplorationRewardsModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    mockResolve.mockReset()
    mockResolve.mockResolvedValue({ caps_granted: 0, unclaimed_loot: [] })
  })

  it('uses the shared wide terminal modal like other popups', () => {
    const wrapper = mountModal()

    expect(wrapper.findComponent(Dialog).props('open')).toBe(true)
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

  it('flags a recalled-early return with its completion percentage', () => {
    const wrapper = mountModal({
      ...rewardsWithOverflow,
      items: [],
      overflow_items: [],
      recalled_early: true,
      progress_percentage: 40,
    })

    expect(wrapper.text()).toContain('Recalled early (40% complete)')
    expect(wrapper.text()).toContain('Reduced rewards')
  })

  it('hides the recalled banner for a full-length return', () => {
    expect(mountModal().text()).not.toContain('Recalled early')
  })

  it('allows deferring overflow resolution so storage can be managed first', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 0, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal()
    const takeButtons = wrapper.findAll('.overflow-actions button')

    expect(wrapper.get('.report-action-btn').text()).toContain('Resolve Later')

    await takeButtons[0]!.trigger('click')
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'take', 0)
    expect(wrapper.text()).not.toContain('Dropped A')
    expect(wrapper.text()).toContain('Dropped B')
    expect(wrapper.get('.report-action-btn').text()).toContain('Resolve Later')

    await wrapper.get('.report-action-btn').trigger('click')
    expect(wrapper.emitted('close')).toEqual([[true]])
  })

  it('sells a single overflow item for caps', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal()
    const sellButtons = wrapper
      .findAll('.overflow-actions button')
      .filter((button) => button.text() === 'Sell')

    await sellButtons[0]!.trigger('click')
    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'sell', 0)
    expect(wrapper.text()).not.toContain('Dropped A')
  })

  it('uses the rewards exploration ID when a stale caller ID is supplied', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal(
      { ...rewardsWithOverflow, exploration_id: 'authoritative-exp' },
      'stale-exp'
    )

    await wrapper
      .findAll('.overflow-actions button')
      .find((button) => button.text() === 'Sell')!
      .trigger('click')

    expect(mockResolve).toHaveBeenCalledWith('authoritative-exp', 'sell', 0)
  })

  it('allows a legacy overflow report to close after the missing record is reported', async () => {
    mockResolve.mockRejectedValueOnce({ response: { status: 404 } })
    const wrapper = mountModal()

    await wrapper.findAll('.overflow-actions button')[0]!.trigger('click')

    expect(wrapper.text()).toContain('This report predates overflow resolution')
    expect(wrapper.get('.report-action-btn').attributes('disabled')).toBeUndefined()
    await wrapper.get('.report-action-btn').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('treats a top-level ApiError status as a legacy overflow report', async () => {
    mockResolve.mockRejectedValueOnce({ status: 404 })
    const wrapper = mountModal()

    await wrapper.findAll('.overflow-actions button')[0]!.trigger('click')

    expect(wrapper.text()).toContain('This report predates overflow resolution')
    expect(wrapper.get('.report-action-btn').attributes('disabled')).toBeUndefined()
    await wrapper.get('.report-action-btn').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('restores overflow actions when the next report is not legacy', async () => {
    mockResolve.mockRejectedValueOnce({ response: { status: 404 } })
    const wrapper = mountModal()

    await wrapper.findAll('.overflow-actions button')[0]!.trigger('click')
    await wrapper.setProps({
      rewards: { ...rewardsWithOverflow, overflow_items: [item('Dropped C')] },
    })

    expect(wrapper.find('.overflow-actions').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('This report predates overflow resolution')
  })

  it('sells every overflow item without relying on a delayed prop update', async () => {
    mockResolve
      .mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
      .mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [] })
    const wrapper = mountModal()

    await wrapper.get('.sell-all-btn').trigger('click')
    await flushPromises()

    expect(mockResolve).toHaveBeenNthCalledWith(1, 'exp-1', 'sell', 0)
    expect(mockResolve).toHaveBeenNthCalledWith(2, 'exp-1', 'sell', 0)
    expect(mockToast.success).toHaveBeenCalledTimes(1)
    expect(mockToast.success).toHaveBeenCalledWith('Sold 2 items for +50 caps')
    expect(wrapper.find('.sell-all-btn').exists()).toBe(false)
  })

  it('keeps unsold items and reports the partial total and failure', async () => {
    mockResolve
      .mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
      .mockRejectedValueOnce(new Error('Sale unavailable'))
    const wrapper = mountModal()
    await wrapper.get('.sell-all-btn').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Dropped B')
    expect(mockToast.success).toHaveBeenCalledWith('Sold 1 item for +25 caps')
    expect(mockToast.error).toHaveBeenCalledTimes(1)
  })

  it('closes once every overflow item is decided', async () => {
    const wrapper = mountModal({ ...rewardsWithOverflow, overflow_items: [] })

    await wrapper.get('.report-action-btn').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits one close event when the modal close control is used', async () => {
    const wrapper = mountModal({ ...rewardsWithOverflow, overflow_items: [] })

    await wrapper.get('[data-slot="dialog-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('labels the closing action truthfully instead of claiming an unclaimed reward', () => {
    const settled = mountModal({ ...rewardsWithOverflow, overflow_items: [] })

    expect(settled.get('.report-action-btn').text()).toContain('Close Report')
    expect(settled.text()).not.toContain('Collect Rewards')

    const unresolved = mountModal()

    expect(unresolved.get('.report-action-btn').text()).toContain('Resolve Later')
  })

  it('explains that rewards were already settled on arrival', () => {
    expect(mountModal().text()).toContain(
      'Caps, XP and storable loot were credited when the crew arrived.'
    )
  })

  it('omits the settlement clarification for a pending-overflow view', () => {
    const wrapper = mountModal(rewardsWithOverflow, 'exp-1', true)

    expect(wrapper.text()).not.toContain('Caps, XP and storable loot were credited')
  })

  it('shows only the caps the vault actually credited', () => {
    const wrapper = mountModal({
      ...rewardsWithOverflow,
      overflow_items: [],
      caps: 150,
      caps_credited: 0,
    })

    expect(wrapper.get('.caps-value').text()).toBe('0')
    expect(wrapper.text()).toContain('The vault wallet cap limited the credited caps.')
  })

  it('falls back to the found caps for legacy reports without a credited amount', () => {
    const wrapper = mountModal({ ...rewardsWithOverflow, overflow_items: [], caps: 150 })

    expect(wrapper.get('.caps-value').text()).toBe('150')
    expect(wrapper.text()).not.toContain('vault wallet cap')
  })

  it('reports supplies that were fully stored', () => {
    const wrapper = mountModal({
      ...rewardsWithOverflow,
      overflow_items: [],
      stimpaks: 2,
      stimpaks_stored: 2,
      radaways: 1,
      radaways_stored: 1,
    })

    const supplies = wrapper.get('.returned-supplies').text()
    expect(supplies).toContain('Stimpaks')
    expect(supplies).toContain('2 of 2 stored')
    expect(supplies).toContain('Radaways')
    expect(supplies).toContain('1 of 1 stored')
    expect(supplies).not.toContain('lost')
  })

  it('reports supplies lost to full medical storage', () => {
    const wrapper = mountModal({
      ...rewardsWithOverflow,
      overflow_items: [],
      stimpaks: 3,
      stimpaks_stored: 0,
    })

    const supplies = wrapper.get('.returned-supplies').text()
    expect(supplies).toContain('3 lost')
    expect(supplies).toContain('medical storage full')
  })

  it('never invents a loss for legacy reports without stored counts', () => {
    const wrapper = mountModal({
      ...rewardsWithOverflow,
      overflow_items: [],
      stimpaks: 2,
    })

    const supplies = wrapper.get('.returned-supplies').text()
    expect(supplies).toContain('2 carried back')
    expect(supplies).not.toContain('lost')
  })

  it('hides the returned supplies section when nothing was carried back', () => {
    const wrapper = mountModal({
      ...rewardsWithOverflow,
      overflow_items: [],
      stimpaks: 0,
      radaways: 0,
    })

    expect(wrapper.find('.returned-supplies').exists()).toBe(false)
  })
})
