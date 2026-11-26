import { describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import QuestRewardsModal from '@/modules/progression/components/QuestRewardsModal.vue'
import type { QuestReward, VaultQuest } from '@/modules/progression/models/quest'

vi.mock('@iconify/vue', () => createIconifyMock())

const quest = {
  id: 'quest-1',
  title: 'The Water Chip',
  short_description: 'Recover the water chip.',
  long_description: 'Recover the water chip from Vault 13.',
  requirements: 'Level 5',
  rewards: '100 caps',
  quest_type: 'main',
  quest_category: null,
  chain_id: null,
  chain_order: 0,
  previous_quest_id: null,
  next_quest_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  is_visible: true,
  is_completed: false,
  started_at: '2026-01-01T00:00:00Z',
  duration_minutes: 60,
  quest_rewards: [],
} as VaultQuest

/** One confirm screen for an authored reward list. */
const mountModal = (rewards: Partial<QuestReward>[] = [], props: Record<string, unknown> = {}) =>
  mount(QuestRewardsModal, {
    props: { show: true, quest: { ...quest, quest_rewards: rewards as QuestReward[] }, ...props },
    global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
  })

const actions = (wrapper: ReturnType<typeof mountModal>) =>
  wrapper.findComponent({ name: 'TerminalModalActions' })

describe('QuestRewardsModal', () => {
  it('uses the shared terminal frame and actions without redundant status text', () => {
    const wrapper = mountModal()
    const footer = actions(wrapper)

    expect(wrapper.findComponent(TerminalModal).props('size')).toBe('xl')
    expect(wrapper.get('.quest-complete-header').text()).not.toContain('MISSION REPORT // COMPLETE')
    expect(footer.exists()).toBe(true)
    expect(footer.props('alignment')).toBe('between')
    expect(footer.text()).toContain('Review Later')
    expect(footer.text()).toContain('Confirm & Claim')
  })

  it('keeps review and claim actions distinct', async () => {
    const wrapper = mountModal()
    const footer = actions(wrapper)

    await footer.get('.cancel').trigger('click')
    await footer.get('.confirm').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('disables the claim action while a claim is in flight', () => {
    expect(actions(mountModal([], { isSubmitting: true })).props('confirmDisabled')).toBe(true)
  })

  it.each([
    [0.5, '50% chance'],
    [0.75, '75% chance'],
  ])('labels an authored chance reward (%s) with its roll probability', (reward_chance, label) => {
    const wrapper = mountModal([
      { reward_type: 'caps', reward_data: { amount: 100 }, reward_chance },
    ])

    expect(wrapper.text()).toContain(label)
  })

  it('is a single confirm screen — no separate delivery-confirmed state after claiming', () => {
    const wrapper = mountModal()

    expect(wrapper.text()).toContain('Quest Complete!')
    expect(wrapper.text()).toContain('Confirm delivery to your vault')
    expect(wrapper.text()).toContain('Confirm & Claim')
    expect(wrapper.text()).not.toContain('Delivery Confirmed!')
    expect(wrapper.text()).not.toContain('Done')
  })

  it('shows the empty state for a quest with no authored rewards', () => {
    const wrapper = mountModal()

    expect(wrapper.text()).toContain('No rewards listed for this quest')
    expect(wrapper.text()).not.toContain('100')
  })

  it('renders item rewards with their real artwork, item type and rarity', () => {
    const wrapper = mountModal([
      {
        reward_type: 'item',
        reward_data: { item_name: 'Assault rifle', quantity: 1 },
        reward_chance: 1,
        item_data: {
          name: 'Assault rifle',
          item_type: 'weapon',
          rarity: 'rare',
          image_url: '/static/weapon_images/assault_rifle.png',
        },
      },
    ])

    const card = wrapper.getComponent(RewardItemCard)
    expect(card.props('kind')).toBe('item')
    expect(card.props('imageUrl')).toBe('/static/weapon_images/assault_rifle.png')
    expect(wrapper.get('img[alt="Assault rifle"]').attributes('src')).toContain(
      '/static/weapon_images/assault_rifle.png'
    )
    expect(wrapper.text()).toContain('Weapon')
    expect(wrapper.text()).toContain('rare')
    expect(wrapper.find('.reward-card').exists()).toBe(false)
  })

  it('renders dweller rewards as dweller cards with a portrait and rarity badge', () => {
    const wrapper = mountModal([
      {
        reward_type: 'dweller',
        reward_data: { template_id: 'vault-dweller', name: 'jane doe', rarity: 'legendary' },
        reward_chance: 0.75,
      },
    ])

    const card = wrapper.getComponent(RewardItemCard)
    expect(card.props('kind')).toBe('dweller')
    expect(card.props('name')).toBe('Jane Doe')
    expect(card.props('rarity')).toBe('legendary')
    expect(wrapper.text()).toContain('New Dweller')
    expect(wrapper.text()).toContain('75% chance')
    expect(wrapper.find('[role="img"][aria-label="Jane Doe"]').exists()).toBe(true)
    expect(wrapper.find('.reward-card').exists()).toBe(false)
  })

  it('renders numeric rewards as currency tiles matching the item treatment', () => {
    const wrapper = mountModal([
      { reward_type: 'caps', reward_data: { amount: 100 }, reward_chance: 1 },
    ])

    const card = wrapper.getComponent(RewardItemCard)
    expect(card.props('kind')).toBe('currency')
    expect(card.props('icon')).toBe('mdi:coins')
    expect(card.props('label')).toBe('Bottle Caps')
    expect(card.props('name')).toBe('100')
    expect(wrapper.find('.reward-card').exists()).toBe(false)
    expect(wrapper.text()).toContain('Bottle Caps')
    expect(wrapper.text()).toContain('100')
  })
})
