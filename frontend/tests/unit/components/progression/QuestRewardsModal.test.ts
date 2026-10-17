import { describe, expect, it, vi } from 'vitest'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import { Button } from '@/core/components/ui/button'
import RewardItemCard from '@/core/components/common/RewardItemCard.vue'
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

describe('QuestRewardsModal', () => {
  it('uses a compact terminal modal frame without redundant status text', () => {
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.find('[data-slot="dialog-content"]').classes()).toContain('max-w-xl')
    expect(wrapper.get('.quest-complete-header').text()).not.toContain('MISSION REPORT // COMPLETE')
    expect(wrapper.get('.quest-return-banner').classes()).toContain('border-theme-primary/30')
    expect(wrapper.get('.quest-return-banner').classes()).toContain('mb-6')
    expect(wrapper.get('.quest-return-banner').classes()).not.toContain('mt-5')
    expect(wrapper.get('.quest-return-banner').classes()).not.toContain('terminal-glow')
  })

  it('uses the shared terminal actions for reviewing and claiming rewards', () => {
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    const actions = wrapper.findComponent({ name: 'TerminalModalActions' })

    expect(actions.exists()).toBe(true)
    expect(actions.props('alignment')).toBe('between')
    expect(actions.classes()).toContain('w-full')
    expect(actions.classes()).toContain('max-sm:flex-col')
    expect(actions.classes()).toContain('justify-between')
    expect(actions.findAll('button').every(button => button.classes().includes('max-sm:w-full'))).toBe(true)
    expect(actions.findAll('button').every(button => button.classes().includes('whitespace-nowrap'))).toBe(true)
    expect(actions.text()).toContain('Review Later')
    expect(actions.text()).toContain('Confirm & Claim')
  })

  it('keeps review and claim actions distinct', async () => {
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    const actions = wrapper.findComponent({ name: 'TerminalModalActions' })
    await actions.get('.cancel').trigger('click')
    await actions.get('.confirm').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('disables the claim action while a claim is in flight', () => {
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest, isSubmitting: true },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    const actions = wrapper.findComponent({ name: 'TerminalModalActions' })
    expect(actions.props('confirmDisabled')).toBe(true)
  })

  it('labels authored chance rewards with their roll probability', () => {
    const chanceQuest = {
      ...quest,
      quest_rewards: [
        {
          id: 'reward-1',
          quest_id: 'quest-1',
          reward_type: 'caps',
          reward_data: { amount: 100 },
          reward_chance: 0.5,
        },
      ] as QuestReward[],
    } as VaultQuest
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest: chanceQuest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('50% chance')
  })

  it('is a single confirm screen — no separate delivery-confirmed state after claiming', () => {
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('Quest Complete!')
    expect(wrapper.text()).toContain('Confirm delivery to your vault')
    expect(wrapper.text()).toContain('Confirm & Claim')
    expect(wrapper.text()).not.toContain('Delivery Confirmed!')
    expect(wrapper.text()).not.toContain('Done')
  })

  it('shows the empty state for a quest with no authored rewards', () => {
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('No rewards listed for this quest')
    expect(wrapper.text()).not.toContain('100')
  })

  it('renders item rewards with their real artwork, item type and rarity', () => {
    const itemQuest = {
      ...quest,
      quest_rewards: [
        {
          id: 'reward-item',
          quest_id: 'quest-1',
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
      ] as QuestReward[],
    } as VaultQuest
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest: itemQuest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

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
    const dwellerQuest = {
      ...quest,
      quest_rewards: [
        {
          id: 'reward-dweller',
          quest_id: 'quest-1',
          reward_type: 'dweller',
          reward_data: { template_id: 'vault-dweller', name: 'jane doe', rarity: 'legendary' },
          reward_chance: 0.75,
        },
      ] as QuestReward[],
    } as VaultQuest
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest: dwellerQuest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

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
    const capsQuest = {
      ...quest,
      quest_rewards: [
        {
          id: 'reward-caps',
          quest_id: 'quest-1',
          reward_type: 'caps',
          reward_data: { amount: 100 },
          reward_chance: 1,
        },
      ] as QuestReward[],
    } as VaultQuest
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest: capsQuest },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

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
