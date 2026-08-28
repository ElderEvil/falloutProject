import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { UProgressBar } from '@/core/components/ui'
import QuestPartyCard from '@/modules/exploration/components/QuestPartyCard.vue'
import type { VaultQuest } from '@/modules/progression/models/quest'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-1' } }),
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

    expect(wrapper.findComponent(UProgressBar).props('modelValue')).toBeGreaterThan(0)
    expect(wrapper.text()).toContain('Quest party')
    expect(wrapper.text()).toContain('Lucy MacLean')
    expect(wrapper.text()).toContain('2 / 3 assigned')

    wrapper.unmount()
  })
})
