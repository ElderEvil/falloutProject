import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { UButton, UModal } from '@/core/components/ui'
import QuestRewardsModal from '@/modules/progression/components/QuestRewardsModal.vue'
import type { components } from '@/core/types/api.generated'
import type { QuestReward, VaultQuest } from '@/modules/progression/models/quest'

type GrantedReward = components['schemas']['QuestCompleteResponse']['granted_rewards'][number]

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

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

    expect(wrapper.findComponent(UModal).props('size')).toBe('wide')
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
    expect(actions.findAllComponents(UButton).every(button => button.classes().includes('max-sm:w-full'))).toBe(true)
    expect(actions.findAllComponents(UButton).every(button => button.classes().includes('whitespace-nowrap'))).toBe(true)
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

  it('renders granted rewards instead of authored definitions after claiming', () => {
    const granted: GrantedReward[] = [
      { reward_type: 'caps', amount: 100 },
      { reward_type: 'dweller', dweller_id: 'dweller-1', name: 'Jane Doe' },
    ]
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest, grantedRewards: granted },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('Delivery Confirmed!')
    expect(wrapper.text()).toContain('100')
    expect(wrapper.text()).toContain('Jane Doe')
    expect(wrapper.text()).toContain('Done')
    expect(wrapper.text()).not.toContain('Confirm & Claim')
  })

  it('points at Storage when a lunchbox arrived unopened', () => {
    const granted: GrantedReward[] = [
      { reward_type: 'item', item_type: 'lunchbox', name: 'Lunchbox', amount: 1, item_id: 'box-1', item_ids: ['box-1'] },
    ]
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest, grantedRewards: granted },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('Lunchbox')
    expect(wrapper.text()).toContain('Storage supplies tab')
  })

  it('shows the empty state instead of authored rewards for an empty grant', () => {
    const authoredQuest = {
      ...quest,
      quest_rewards: [
        {
          id: 'reward-1',
          quest_id: 'quest-1',
          reward_type: 'caps',
          reward_data: { amount: 100 },
          reward_chance: 1,
        },
      ] as QuestReward[],
    } as VaultQuest
    const wrapper = mount(QuestRewardsModal, {
      props: { show: true, quest: authoredQuest, grantedRewards: [] },
      global: { stubs: { Teleport: { template: '<div><slot /></div>' } } },
    })

    expect(wrapper.text()).toContain('Delivery Confirmed!')
    expect(wrapper.text()).toContain('No rewards listed for this quest')
    expect(wrapper.text()).not.toContain('100')
  })
})
