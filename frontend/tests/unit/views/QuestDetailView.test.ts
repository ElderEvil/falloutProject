import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QuestDetailView from '@/modules/progression/views/QuestDetailView.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123', questId: 'quest-2' },
  }),
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

const previousQuest = {
  id: 'quest-1',
  title: 'First Steps',
  short_description: 'Begin',
  long_description: 'Begin the journey.',
  requirements: '',
  rewards: '',
  created_at: '2025-01-01',
  updated_at: '2025-01-01',
  is_visible: true,
  is_completed: true,
  started_at: '2025-01-02T00:00:00Z',
  duration_minutes: 60,
  quest_type: 'side',
}

const chainedQuest = {
  id: 'quest-2',
  title: 'Second Steps',
  short_description: 'Continue',
  long_description: 'Continue the journey.',
  requirements: '',
  rewards: '',
  created_at: '2025-01-01',
  updated_at: '2025-01-01',
  is_visible: true,
  is_completed: false,
  started_at: null,
  duration_minutes: 60,
  chain_id: 'chain-1',
  chain_order: 2,
  previous_quest_id: 'quest-1',
  next_quest_id: 'quest-3',
  quest_type: 'side',
}

const nextQuest = {
  id: 'quest-3',
  title: 'Final Steps',
  short_description: 'Finish',
  long_description: 'Finish the journey.',
  requirements: '',
  rewards: '',
  created_at: '2025-01-01',
  updated_at: '2025-01-01',
  is_visible: false,
  is_completed: false,
  started_at: null,
  duration_minutes: 60,
  chain_id: 'chain-1',
  chain_order: 3,
  quest_type: 'side',
}

describe('QuestDetailView chain links', () => {
  let wrapper: VueWrapper
  let questStore: ReturnType<typeof useQuestStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    questStore = useQuestStore()
    vi.clearAllMocks()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
  })

  function mountView() {
    return mount(QuestDetailView, {
      global: {
        stubs: {
          SidePanel: true,
          PageNavigation: true,
          Icon: true,
        },
      },
    })
  }

  it('names the exact previous and next quests in the chain card', async () => {
    questStore.vaultQuests = [{ ...previousQuest }, { ...chainedQuest }, { ...nextQuest }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('First Steps')
    expect(text).toContain('Final Steps')
    expect(text).not.toContain('Previous quest must be completed first')
  })

  it('falls back to generic text when the linked quest is not loaded', async () => {
    questStore.vaultQuests = [{ ...chainedQuest }]

    wrapper = mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Previous quest must be completed first')
  })
})
