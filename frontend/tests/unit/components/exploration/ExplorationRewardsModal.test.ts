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

/** A report with every overflow item already decided. */
const settledReport = (patch: Partial<RewardsSummary> = {}) =>
  mountModal({ ...rewardsWithOverflow, overflow_items: [], ...patch })

const overflowButtons = (wrapper: ReturnType<typeof mountModal>) =>
  wrapper.findAll('.overflow-actions button')

describe('ExplorationRewardsModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    mockResolve.mockReset()
    mockResolve.mockResolvedValue({ caps_granted: 0, unclaimed_loot: [] })
  })

  it('uses the shared wide terminal modal like other popups', () => {
    expect(mountModal().findComponent(Dialog).props('open')).toBe(true)
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

  it.each([
    ['stored items only', {}, 'Stored in Vault', 'Items Found'],
    ['nothing found at all', { items: [] }, 'No items found during this exploration', null],
  ])('labels the loot section (%s)', (_, patch, message, absent) => {
    const wrapper = settledReport(patch)

    expect(wrapper.text()).toContain(message)
    if (absent) expect(wrapper.text()).not.toContain(absent)
  })

  it('flags a recalled-early return with its completion percentage', () => {
    const wrapper = settledReport({ items: [], recalled_early: true, progress_percentage: 40 })

    expect(wrapper.text()).toContain('Recalled early (40% complete)')
    expect(wrapper.text()).toContain('Reduced rewards')
  })

  it('hides the recalled banner for a full-length return', () => {
    expect(mountModal().text()).not.toContain('Recalled early')
  })

  it('allows deferring overflow resolution so storage can be managed first', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 0, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal()

    expect(wrapper.get('.report-action-btn').text()).toContain('Resolve Later')

    await overflowButtons(wrapper)[0]!.trigger('click')
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

    await overflowButtons(wrapper)
      .filter((button) => button.text() === 'Sell')[0]!
      .trigger('click')

    expect(mockResolve).toHaveBeenCalledWith('exp-1', 'sell', 0)
    expect(wrapper.text()).not.toContain('Dropped A')
  })

  it('uses the rewards exploration ID when a stale caller ID is supplied', async () => {
    mockResolve.mockResolvedValueOnce({ caps_granted: 25, unclaimed_loot: [item('Dropped B')] })
    const wrapper = mountModal(
      { ...rewardsWithOverflow, exploration_id: 'authoritative-exp' },
      'stale-exp'
    )

    await overflowButtons(wrapper)
      .find((button) => button.text() === 'Sell')!
      .trigger('click')

    expect(mockResolve).toHaveBeenCalledWith('authoritative-exp', 'sell', 0)
  })

  it.each([
    ['a nested response status', { response: { status: 404 } }],
    ['a top-level ApiError status', { status: 404 }],
  ])(
    'closes a legacy overflow report after the missing record is reported (%s)',
    async (_, error) => {
      mockResolve.mockRejectedValueOnce(error)
      const wrapper = mountModal()

      await overflowButtons(wrapper)[0]!.trigger('click')

      expect(wrapper.text()).toContain('This report predates overflow resolution')
      expect(wrapper.get('.report-action-btn').attributes('disabled')).toBeUndefined()
      expect(wrapper.get('.report-action-btn').text()).toContain('Close Report')
      await wrapper.get('.report-action-btn').trigger('click')
      expect(wrapper.emitted('close')).toHaveLength(1)
    }
  )

  it('restores overflow actions when the next report is not legacy', async () => {
    mockResolve.mockRejectedValueOnce({ response: { status: 404 } })
    const wrapper = mountModal()

    await overflowButtons(wrapper)[0]!.trigger('click')
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
    const wrapper = settledReport()

    await wrapper.get('.report-action-btn').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('emits one close event when the modal close control is used', async () => {
    const wrapper = settledReport()

    await wrapper.get('[data-slot="dialog-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  it('labels the closing action and the settlement state truthfully', () => {
    const settled = settledReport()

    expect(settled.get('.report-action-btn').text()).toContain('Close Report')
    expect(settled.text()).not.toContain('Collect Rewards')
    expect(mountModal().get('.report-action-btn').text()).toContain('Resolve Later')
    expect(mountModal().text()).toContain(
      'Caps, XP and storable loot were credited when the crew arrived.'
    )
    // Nothing has been credited yet while the player is choosing what to drop.
    expect(mountModal(rewardsWithOverflow, 'exp-1', true).text()).not.toContain(
      'Caps, XP and storable loot were credited'
    )
  })

  it.each([
    [
      'the credited amount',
      { caps: 150, caps_credited: 0 },
      '0',
      'The vault wallet cap limited the credited caps.',
    ],
    ['found caps for legacy reports', { caps: 150 }, '150', null],
  ])('shows %s', (_, patch, value, note) => {
    const wrapper = settledReport(patch)

    expect(wrapper.get('.caps-value').text()).toBe(value)
    if (note) expect(wrapper.text()).toContain(note)
    else expect(wrapper.text()).not.toContain('vault wallet cap')
  })

  it.each([
    [
      'fully stored supplies',
      { stimpaks: 2, stimpaks_stored: 2, radaways: 1, radaways_stored: 1 },
      ['Stimpaks', '2 of 2 stored', 'Radaways', '1 of 1 stored'],
      ['lost'],
    ],
    [
      'supplies lost to full medical storage',
      { stimpaks: 3, stimpaks_stored: 0 },
      ['3 lost', 'medical storage full'],
      [],
    ],
    ['legacy reports without stored counts', { stimpaks: 2 }, ['2 carried back'], ['lost']],
  ])('reports %s', (_, patch, expected, absent) => {
    const supplies = settledReport(patch).get('.returned-supplies').text()

    for (const part of expected) expect(supplies).toContain(part)
    for (const part of absent) expect(supplies).not.toContain(part)
  })

  it('hides the returned supplies section when nothing was carried back', () => {
    expect(settledReport({ stimpaks: 0, radaways: 0 }).find('.returned-supplies').exists()).toBe(
      false
    )
  })

  it('shows a pending storage decision above the reward summary, not below the fold', () => {
    // The decision is the actionable part; opening it under a full grid of reward cards left the
    // player with nothing to click but "Resolve Later".
    const text = mountModal().text()
    expect(text).toContain('Storage Full — Needs Decision')
    expect(text).toContain('Total party XP')
    expect(text.indexOf('Storage Full — Needs Decision')).toBeLessThan(
      text.indexOf('Total party XP')
    )
  })
})
