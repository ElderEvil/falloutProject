import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
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
})
