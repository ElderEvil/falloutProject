import { afterEach, describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { Progress } from '@/core/components/ui/progress'
import QuestPartyCard from '@/modules/exploration/components/QuestPartyCard.vue'
import type { VaultQuest } from '@/modules/progression/models/quest'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-1' } }),
}))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn().mockResolvedValue({ race_mechanics: true, faction_mechanics: true }),
  getIdentityOptions: vi.fn().mockResolvedValue({ races: [], factions_by_race: {}, states_by_race: {} }),
}))

vi.mock('@iconify/vue', () => ({
  Icon: { name: 'Icon', template: '<span class="icon-mock" />' },
}))

const quest = {
  id: 'quest-1',
  title: 'A Pier into the Future',
  started_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  duration_minutes: 60,
} as VaultQuest

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('QuestPartyCard', () => {
  afterEach(() => vi.useRealTimers())

  it('presents quest progress and its assigned party in the shared card language', () => {
    const wrapper = mount(QuestPartyCard, {
      props: {
        quest,
        partyMembers: [
          { id: 'dweller-1', first_name: 'Lucy', last_name: 'MacLean', level: 5 },
          { id: 'dweller-2', first_name: 'Maximus', last_name: null, level: 4 },
        ],
      },
    })

    expect(wrapper.findComponent(Progress).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('Quest party')
    expect(wrapper.text()).toContain('Lucy MacLean')
    expect(wrapper.text()).toContain('2 / 3 assigned')

    wrapper.unmount()
  })

  it('shows a travelling badge and ETA instead of progress while the party returns', () => {
    const wrapper = mount(QuestPartyCard, {
      props: {
        quest: {
          ...quest,
          is_reward_ready: false,
          return_started_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
          return_completes_at: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
        },
        partyMembers: [],
      },
    })

    expect(wrapper.text()).toContain('RETURNING')
    expect(wrapper.text()).toContain('Travelling home')
    expect(wrapper.findComponent(Progress).exists()).toBe(false)

    wrapper.unmount()
  })
})
