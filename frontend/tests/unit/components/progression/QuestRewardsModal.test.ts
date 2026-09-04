import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { UButton, UModal } from '@/core/components/ui'
import QuestRewardsModal from '@/modules/progression/components/QuestRewardsModal.vue'
import type { VaultQuest } from '@/modules/progression/models/quest'

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
    expect(wrapper.get('.quest-return-banner').classes()).toContain('mt-5')
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
    expect(actions.classes()).toContain('flex-nowrap')
    expect(actions.classes()).toContain('justify-between')
    expect(actions.findAllComponents(UButton).every(button => button.classes().includes('shrink-0'))).toBe(true)
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
})
