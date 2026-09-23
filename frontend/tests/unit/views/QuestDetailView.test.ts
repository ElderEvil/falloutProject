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

describe('QuestDetailView start button', () => {
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

  it('does not render the Start button for a locked quest', async () => {
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: false,
        is_locked: true,
        lock_reason: 'Not available in this vault',
      },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.action-btn').exists()).toBe(false)
    expect(wrapper.text()).toContain('Not available in this vault')
  })

  it('renders the Start button for an available quest', async () => {
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: true,
        is_locked: false,
        lock_reason: null,
      },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const startButton = wrapper.find('.action-btn')
    expect(startButton.exists()).toBe(true)
    expect(startButton.text()).toContain('Start Quest')
  })

  it('shows a disabled travelling-home message while the party returns', async () => {
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: true,
        is_locked: false,
        lock_reason: null,
        is_completed: false,
        is_reward_ready: false,
        started_at: '2025-01-02T00:00:00Z',
        duration_minutes: 60,
        return_started_at: '2025-01-02T01:00:00Z',
        return_completes_at: '2025-01-02T01:15:00Z',
      },
    ]

    wrapper = mountView()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const travellingButton = wrapper.find('.action-btn')
    expect(travellingButton.exists()).toBe(true)
    expect(travellingButton.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Party travelling home')
  })

  it('refreshes the quest when the return ETA passes so arrival becomes claimable', async () => {
    vi.useFakeTimers()
    try {
      questStore.vaultQuests = [
        {
          ...chainedQuest,
          is_visible: true,
          is_locked: false,
          lock_reason: null,
          is_completed: false,
          is_reward_ready: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: new Date(Date.now() - 60_000).toISOString(),
        },
      ]

      wrapper = mountView()
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('Party travelling home')

      questStore.vaultQuests = [
        { ...questStore.vaultQuests[0], is_reward_ready: true },
      ]
      await vi.advanceTimersByTimeAsync(30_000)

      expect(questStore.fetchVaultQuests).toHaveBeenCalledWith('vault-123')
      expect(wrapper.text()).toContain('Claim Rewards')
    } finally {
      vi.useRealTimers()
    }
  })
})
