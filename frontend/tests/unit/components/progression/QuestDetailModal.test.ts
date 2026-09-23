import { beforeEach, describe, expect, it, vi } from 'vitest'
import { config, flushPromises, mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QuestDetailModal from '@/modules/progression/components/QuestDetailModal.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'

const routerPushMock = vi.hoisted(() => vi.fn())

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-123' } }),
  useRouter: () => ({
    push: routerPushMock,
  }),
}))

// Mock @iconify/vue so icon names are assertable via data-icon.
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>',
  },
}))

// The modal composes shadcn primitives; stub them so the suite stays context-free.
config.global.stubs = {
  Dialog: { props: ['open'], template: '<div v-if="open" class="mock-modal"><slot /></div>' },
  DialogContent: { template: '<div><slot /></div>' },
  DialogHeader: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<div class="mock-dialog-title"><slot /></div>' },
  Button: {
    props: ['disabled'],
    template: '<button class="mock-button" :disabled="disabled"><slot /></button>',
  },
}

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
  chain_id: 'chain-1',
  chain_order: 1,
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

describe('QuestDetailModal chain links', () => {
  let wrapper: VueWrapper
  let questStore: ReturnType<typeof useQuestStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    questStore = useQuestStore()
    vi.clearAllMocks()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
  })

  function mountModal() {
    return mount(QuestDetailModal, {
      props: { questId: 'quest-2', vaultId: 'vault-123' },
    })
  }

  it('lists every chain quest with completion states', async () => {
    questStore.vaultQuests = [{ ...previousQuest }, { ...chainedQuest }, { ...nextQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('First Steps')
    expect(text).toContain('Completed')
    expect(text).toContain('Second Steps')
    expect(text).toContain('Current')
    expect(text).toContain('Final Steps')
    expect(text).toContain('Upcoming')
  })

  it('shows state icons next to the status text and no order numbers', async () => {
    questStore.vaultQuests = [{ ...previousQuest }, { ...chainedQuest }, { ...nextQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.chain-row-order')).toHaveLength(0)
    const icons = wrapper.findAll('.mock-icon').map((node) => node.attributes('data-icon'))
    expect(icons).toContain('mdi:check-circle')
    expect(icons).toContain('mdi:play-circle')
    expect(icons).toContain('mdi:circle-outline')
    for (const row of wrapper.findAll('.chain-row')) {
      const container = row.element.firstElementChild!
      const classes = Array.from(container.children).map((node) => node.getAttribute('class') ?? '')
      expect(classes.findIndex((name) => name.includes('chain-row-title'))).toBe(0)
      expect(classes.findIndex((name) => name.includes('chain-row-icon'))).toBe(1)
      expect(classes.findIndex((name) => name.includes('chain-row-state'))).toBe(2)
    }
  })

  it('reloads the quest when the questId prop changes (chain navigation)', async () => {
    questStore.vaultQuests = [{ ...previousQuest }, { ...chainedQuest }]

    wrapper = mountModal()
    await flushPromises()
    expect(wrapper.find('.mock-dialog-title').text()).toBe('Second Steps')

    await wrapper.setProps({ questId: 'quest-1' })
    await flushPromises()

    expect(wrapper.find('.mock-dialog-title').text()).toBe('First Steps')
  })

  it('emits select for a chain quest when its row is clicked', async () => {
    questStore.vaultQuests = [{ ...previousQuest }, { ...chainedQuest }, { ...nextQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    const rows = wrapper.findAll('.chain-row-button')
    expect(rows).toHaveLength(2)
    await rows[0].trigger('click')

    expect(wrapper.emitted('select')).toEqual([['quest-1']])
  })
})

describe('QuestDetailModal start button', () => {
  let wrapper: VueWrapper
  let questStore: ReturnType<typeof useQuestStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    questStore = useQuestStore()
    vi.clearAllMocks()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
  })

  function mountModal() {
    return mount(QuestDetailModal, {
      props: { questId: 'quest-2', vaultId: 'vault-123' },
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

    wrapper = mountModal()
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

    wrapper = mountModal()
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

    wrapper = mountModal()
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

      wrapper = mountModal()
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

  it('hides the prerequisites and chain sections when a completed quest has neither', async () => {
    questStore.vaultQuests = [
      {
        id: 'quest-2',
        title: 'Lone Quest',
        short_description: 'Done',
        long_description: 'Done the journey.',
        requirements: '',
        rewards: '',
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
        is_visible: true,
        is_completed: true,
        started_at: '2025-01-02T00:00:00Z',
        duration_minutes: 60,
        chain_id: null,
        chain_order: 0,
        previous_quest_id: null,
        next_quest_id: null,
        quest_type: 'side',
        quest_requirements: [],
        quest_rewards: [],
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('REQUIREMENTS')
    expect(wrapper.text()).not.toContain('QUEST CHAIN')
  })

  it('formats reward rows with labels instead of raw type slugs', async () => {
    questStore.vaultQuests = [
      {
        id: 'quest-2',
        title: 'Rewarded Quest',
        short_description: 'Done',
        long_description: 'Done the journey.',
        requirements: '',
        rewards: '',
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
        is_visible: true,
        is_completed: true,
        started_at: '2025-01-02T00:00:00Z',
        duration_minutes: 60,
        chain_id: null,
        chain_order: 0,
        previous_quest_id: null,
        next_quest_id: null,
        quest_type: 'side',
        quest_requirements: [],
        quest_rewards: [
          { id: 'reward-1', reward_type: 'caps', reward_data: { amount: 50 }, reward_chance: 1 },
        ],
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('50 Caps')
    expect(wrapper.text()).not.toMatch(/^\s*caps\s*$/m)
  })

  it('omits the type, category and chain badge row', async () => {
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: true,
        is_completed: true,
        quest_category: 'collection',
        quest_requirements: [],
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.quest-badges').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Side')
    expect(wrapper.text()).not.toContain('Collection')
  })

  it('humanizes prerequisite slugs', async () => {
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: true,
        is_completed: true,
        quest_category: 'collection',
        quest_requirements: [
          { id: 'req-1', requirement_type: 'dweller_count', requirement_data: { count: 10 }, is_mandatory: true },
          { id: 'req-2', requirement_type: 'mystery_flag', requirement_data: {}, is_mandatory: false },
        ],
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('collection')
    expect(wrapper.text()).toContain('Reach 10 dwellers')
    expect(wrapper.text()).toContain('Mystery flag')
    expect(wrapper.text()).not.toContain('dweller_count')
    expect(wrapper.text()).not.toContain('mystery_flag')
  })

  it('renders the party roster with member names and statuses', async () => {
    const { filter: dwellerFilterStore } = useDwellerStore()
    dwellerFilterStore.dwellers = [
      { id: 'dweller-1', first_name: 'John', last_name: 'Doe', level: 5 },
    ] as never
    vi.spyOn(questStore, 'getParty').mockResolvedValue([
      {
        id: 'link-1',
        quest_id: 'quest-2',
        vault_id: 'vault-123',
        dweller_id: 'dweller-1',
        slot_number: 0,
        status: 'in_progress',
        created_at: '',
        updated_at: '',
      },
    ])
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: true,
        is_completed: false,
        is_reward_ready: false,
        started_at: '2025-01-02T00:00:00Z',
        duration_minutes: 60,
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await flushPromises()

    expect(wrapper.text()).toContain('PARTY (1)')
    expect(wrapper.text()).toContain('John Doe')
    expect(wrapper.text()).toContain('Lv.5')

    await wrapper.find('.party-row-button').trigger('click')
    expect(routerPushMock).toHaveBeenCalledWith({
      name: 'dwellerDetail',
      params: { id: 'vault-123', dwellerId: 'dweller-1' },
    })
  })

  it('renders live mission tracking while the quest runs', async () => {
    questStore.vaultQuests = [
      {
        ...chainedQuest,
        is_visible: true,
        is_completed: false,
        is_reward_ready: false,
        started_at: new Date(Date.now() - 30 * 60_000).toISOString(),
        duration_minutes: 60,
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('MISSION PROGRESS')
    expect(wrapper.text()).toMatch(/m left/)
  })

  it('shows chain neighbours with their completion states', async () => {
    questStore.vaultQuests = [{ ...previousQuest }, { ...chainedQuest }, { ...nextQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('First Steps')
    expect(wrapper.text()).toContain('Completed')
    expect(wrapper.text()).toContain('Final Steps')
    expect(wrapper.text()).toContain('Upcoming')
  })
})

describe('QuestDetailModal completed state', () => {
  let wrapper: VueWrapper
  let questStore: ReturnType<typeof useQuestStore>

  const completedQuest = {
    ...chainedQuest,
    is_visible: true,
    is_completed: true,
    is_reward_ready: false,
    started_at: '2025-01-02T00:00:00Z',
    duration_minutes: 60,
    completed_at: '2025-01-05T12:00:00Z',
    quest_requirements: [
      { id: 'req-1', requirement_type: 'dweller_count', requirement_data: { count: 10 }, is_mandatory: true },
    ],
    quest_rewards: [
      { id: 'reward-1', reward_type: 'caps', reward_data: { amount: 50 }, reward_chance: 1 },
    ],
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    questStore = useQuestStore()
    vi.clearAllMocks()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
  })

  function mountModal() {
    return mount(QuestDetailModal, {
      props: { questId: 'quest-2', vaultId: 'vault-123' },
    })
  }

  it('drops the sidebar and centers a single column when completed', async () => {
    questStore.vaultQuests = [{ ...completedQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.quest-sidebar').exists()).toBe(false)
    expect(wrapper.find('.quest-content-grid.is-completed').exists()).toBe(true)
  })

  it('keeps the completion badge and appends the date to it', async () => {
    questStore.vaultQuests = [{ ...completedQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.quest-banner--completed').exists()).toBe(true)
    expect(wrapper.find('.quest-status-line').exists()).toBe(false)
    expect(wrapper.text()).toContain('Quest Completed - Rewards Claimed')
    const expectedDate = new Date(parseStartTimeMs('2025-01-05T12:00:00Z')).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    })
    expect(wrapper.text()).toContain(expectedDate)
  })

  it('uses the full width with no frame or inner centering when completed', async () => {
    questStore.vaultQuests = [{ ...completedQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.quest-box').exists()).toBe(false)
    expect(wrapper.find('.quest-detail.is-completed').exists()).toBe(false)
    expect(wrapper.find('.quest-content-grid.is-completed').exists()).toBe(true)
  })

  it('lists granted rewards in a single REWARDS section', async () => {
    questStore.vaultQuests = [
      {
        ...completedQuest,
        granted_rewards: [
          { reward_type: 'caps', amount: 100 },
          { reward_type: 'item', item_type: 'weapon', name: 'Rusty Pistol', amount: 1 },
        ],
      },
    ]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('REWARDS')
    expect(wrapper.text()).not.toContain('REWARDS GRANTED')
    expect(wrapper.text()).toContain('100 caps')
    expect(wrapper.text()).toContain('Rusty Pistol')
  })

  it('falls back to the planned rewards when nothing was granted', async () => {
    questStore.vaultQuests = [{ ...completedQuest, granted_rewards: null }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('50 Caps')
  })

  it('renders requirements unfolded when completed, like the list card', async () => {
    questStore.vaultQuests = [{ ...completedQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.text()).toContain('REQUIREMENTS')
    expect(wrapper.text()).toContain('Reach 10 dwellers')
  })

  it('renders requirements unfolded for quests that are not completed', async () => {
    questStore.vaultQuests = [{ ...completedQuest, is_completed: false, completed_at: null }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.text()).toContain('Reach 10 dwellers')
  })

  it('relabels the party as COMPLETED BY and links dwellers to their detail page', async () => {
    const { filter: dwellerFilterStore } = useDwellerStore()
    dwellerFilterStore.dwellers = [
      { id: 'dweller-1', first_name: 'John', last_name: 'Doe', level: 5 },
    ] as never
    vi.spyOn(questStore, 'getParty').mockResolvedValue([
      {
        id: 'link-1',
        quest_id: 'quest-2',
        vault_id: 'vault-123',
        dweller_id: 'dweller-1',
        slot_number: 0,
        status: 'completed',
        created_at: '',
        updated_at: '',
      },
    ])
    questStore.vaultQuests = [{ ...completedQuest }]

    wrapper = mountModal()
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()
    await flushPromises()

    expect(wrapper.text()).toContain('COMPLETED BY (1)')
    expect(wrapper.text()).toContain('John Doe')
    expect(wrapper.find('.member-chevron').exists()).toBe(true)

    await wrapper.find('.party-row-button').trigger('click')
    expect(routerPushMock).toHaveBeenCalledWith({
      name: 'dwellerDetail',
      params: { id: 'vault-123', dwellerId: 'dweller-1' },
    })
  })
})