import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Icon } from '@iconify/vue'
import { UProgressBar } from '@/core/components/ui'
import QuestCard from '@/modules/progression/components/QuestCard.vue'
import type { VaultQuest } from '@/modules/progression/models/quest'

const quest = {
  id: 'quest-1',
  title: 'A Very Long Expedition',
  short_description: 'A description that can be much longer than the other quest cards.',
  long_description: '',
  requirements: '',
  rewards: '100 Caps',
  quest_type: 'side',
  quest_category: null,
  chain_id: null,
  chain_order: 0,
  previous_quest_id: null,
  next_quest_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  is_visible: true,
  is_completed: false,
  started_at: null,
  duration_minutes: 60,
  quest_requirements: [],
  quest_rewards: [],
} as VaultQuest

describe('QuestCard', () => {
  it('keeps the primary action in a card footer below variable quest content', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest, vaultId: 'vault-1', status: 'available', partyMembers: [] },
    })

    expect(wrapper.find('.quest-card-content').classes()).toContain('flex-1')
    expect(wrapper.html()).toContain('mt-4')
    expect(wrapper.text()).toContain('Start Quest')
  })

  it('starts building quests without opening party selection', async () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest: { ...quest, quest_category: 'building' }, vaultId: 'vault-1', status: 'available' },
    })

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('start')).toEqual([['quest-1']])
    expect(wrapper.emitted('assignParty')).toBeUndefined()
  })

  it('capitalizes a dweller reward template name', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          quest_rewards: [
            {
              id: 'reward-1',
              reward_type: 'dweller',
              reward_data: { template_id: 'lucy-maclean' },
              reward_chance: 1,
            },
          ],
        },
        vaultId: 'vault-1',
        status: 'available',
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('Lucy Maclean')
  })

  it('shows elapsed progress for an active timed quest', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          started_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
          duration_minutes: 60,
        },
        vaultId: 'vault-1',
        status: 'active',
        partyMembers: [],
      },
    })

    expect(wrapper.findComponent(UProgressBar).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.find('.quest-progress-bar').exists()).toBe(true)
    expect(wrapper.find('.timer-progress').text()).toMatch(/% complete/)
  })

  it('keeps completed progress visible while rewards await a claim', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: {
        quest: {
          ...quest,
          started_at: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
          duration_minutes: 60,
        },
        vaultId: 'vault-1',
        status: 'ready',
        partyMembers: [],
      },
    })

    expect(wrapper.findComponent(UProgressBar).props('modelValue')).toBe(100)
    expect(wrapper.text()).toContain('Complete')
  })

  it('uses a reward icon when a quest is ready to claim', () => {
    setActivePinia(createPinia())
    const wrapper = mount(QuestCard, {
      props: { quest, vaultId: 'vault-1', status: 'ready', partyMembers: [] },
    })

    expect(wrapper.findAllComponents(Icon).some((icon) => icon.props('icon') === 'mdi:treasure-chest')).toBe(true)
  })
})
