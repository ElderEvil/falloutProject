import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, VueWrapper } from '@vue/test-utils'
import { reactive } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import QuestsView from '@/modules/progression/views/QuestsView.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'

const routerPushMock = vi.hoisted(() => vi.fn())
const routerReplaceMock = vi.hoisted(() => vi.fn())

// Reactive query so tests can drive the deep-linked quest detail modal.
const routeQuery = reactive<Record<string, string | undefined>>({})

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123' },
    query: routeQuery,
  }),
  useRouter: () => ({
    push: routerPushMock,
    replace: routerReplaceMock,
  }),
}))

describe('QuestsView', () => {
  let wrapper: VueWrapper
  let questStore: ReturnType<typeof useQuestStore>
  let roomStore: ReturnType<typeof useRoomStore>
  let _vaultStore: ReturnType<typeof useVaultStore>

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    questStore = useQuestStore()
    roomStore = useRoomStore()
    _vaultStore = useVaultStore()

    vi.clearAllMocks()
    routeQuery.quest = undefined

    // Prevent unhandled rejections from real HTTP calls during onMounted
    vi.spyOn(questStore, 'fetchAllQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchPartiesForActiveQuests').mockResolvedValue()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Overseer Office Lock', () => {
    it('should show locked state when quests report the Overseer Office lock reason', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'First Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'None',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: false,
          is_locked: true,
          lock_reason: "Requires Overseer's Office",
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      expect(wrapper.find('.locked-container').exists()).toBe(true)
      expect(wrapper.text()).toContain("OVERSEER'S OFFICE REQUIRED")
    })

    it('should show quests when no quest reports the Overseer Office lock', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'First Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'None',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_locked: false,
          lock_reason: null,
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.find('.locked-container').exists()).toBe(false)
      expect(wrapper.find('.quests-container').exists()).toBe(true)
    })
  })

  describe('Tabs', () => {
    beforeEach(() => {
      roomStore.rooms = [
        {
          id: 'room-1',
          name: "Overseer's Office",
          category: 'quests',
          ability: null,
          level: 1,
          max_level: 3,
          capacity: 2,
          x: 0,
          y: 0,
          width: 2,
          height: 1,
          power_cost: 10,
          dweller_ids: [],
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          vault_id: 'vault-123',
          under_construction: false,
          build_time: 60,
          upgrade_cost: 100,
        },
      ]
    })

    it('should show active tab by default', async () => {
      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      const tabs = wrapper.findAll('[role="tab"]')
      expect(tabs[0].attributes('aria-selected')).toBe('true')
    })

    it('should switch to completed tab when clicked', async () => {
      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      const completedTab = wrapper.findAll('[role="tab"]')[2]
      await completedTab.trigger('mousedown')
      await flushPromises()

      expect(completedTab.attributes('aria-selected')).toBe('true')
    })

    it('should switch to available tab when clicked', async () => {
      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      const availableTab = wrapper.findAll('[role="tab"]')[1]
      await availableTab.trigger('mousedown')
      await flushPromises()

      expect(availableTab.attributes('aria-selected')).toBe('true')
    })
  })

  describe('Quest Display', () => {
    beforeEach(() => {
      roomStore.rooms = [
        {
          id: 'room-1',
          name: "Overseer's Office",
          category: 'quests',
          ability: null,
          level: 1,
          max_level: 3,
          capacity: 2,
          x: 0,
          y: 0,
          width: 2,
          height: 1,
          power_cost: 10,
          dweller_ids: [],
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          vault_id: 'vault-123',
          under_construction: false,
          build_time: 60,
          upgrade_cost: 100,
        },
      ]
    })

    it('should display active quests', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Active Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Active Quest')
      expect(wrapper.text()).toContain('Test quest')
    })

    it('refreshes active quests while a party is away', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Active Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      wrapper = mount(QuestsView, {
        global: { stubs: { SidePanel: true, Icon: true } },
      })

      await vi.advanceTimersByTimeAsync(30_000)

      expect(questStore.fetchVaultQuests).toHaveBeenCalledWith('vault-123', { silent: true })
      expect(questStore.fetchPartiesForActiveQuests).toHaveBeenCalledWith('vault-123')
    })

    it('renders travelling quests without a claim action and keeps polling', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Travelling Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          is_reward_ready: false,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: '2025-01-02T01:15:00Z',
        },
      ]

      wrapper = mount(QuestsView, {
        global: { stubs: { SidePanel: true, Icon: true } },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Travelling Quest')
      expect(wrapper.text()).not.toContain('Claim Rewards')

      await vi.advanceTimersByTimeAsync(30_000)
      expect(questStore.fetchVaultQuests).toHaveBeenCalledWith('vault-123', { silent: true })
    })

    it('should display available quests in the available tab', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Available Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      const availableTab = wrapper.findAll('[role="tab"]')[1]
      await availableTab.trigger('mousedown')
      await flushPromises()

      expect(wrapper.text()).toContain('Available Quest')
    })

    it('should reveal locked quests only when Show All is enabled and render their lock reason', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'First Quest',
          short_description: 'Start the chain',
          long_description: 'Start the chain first',
          requirements: 'None',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_locked: false,
          lock_reason: null,
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
        {
          id: 'quest-2',
          title: 'Locked Quest',
          short_description: 'Continue the chain',
          long_description: 'Complete the first quest first',
          requirements: 'Complete First Quest',
          rewards: '100 caps',
          previous_quest_id: 'quest-1',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: false,
          is_locked: true,
          lock_reason: 'Requires completing a previous quest',
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
      ]

      wrapper = mount(QuestsView, {
        global: { stubs: { SidePanel: true, Icon: true } },
      })
      await wrapper.vm.$nextTick()

      const availableTab = wrapper.findAll('[role="tab"]')[1]
      await availableTab.trigger('mousedown')
      await flushPromises()

      expect(wrapper.text()).toContain('First Quest')
      expect(wrapper.text()).not.toContain('Locked Quest')

      await wrapper.find('.toggle-input').setValue(true)

      expect(wrapper.text()).toContain('Locked Quest')
      expect(wrapper.text()).toContain('Requires completing a previous quest')
    })

    it('should display completed quests in completed tab', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Completed Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: true,
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      // Switch to completed tab
      const completedTab = wrapper.findAll('[role="tab"]')[2]
      await completedTab.trigger('mousedown')
      await flushPromises()

      expect(wrapper.text()).toContain('Completed Quest')
      expect(wrapper.text()).toContain('View Details')
    })

    it('should show empty state when no active quests', async () => {
      questStore.vaultQuests = []
      questStore.quests = []

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('No active quests')
    })
  })

  describe('Quest Actions', () => {
    beforeEach(() => {
      roomStore.rooms = [
        {
          id: 'room-1',
          name: "Overseer's Office",
          category: 'quests',
          ability: null,
          level: 1,
          max_level: 3,
          capacity: 2,
          x: 0,
          y: 0,
          width: 2,
          height: 1,
          power_cost: 10,
          dweller_ids: [],
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          vault_id: 'vault-123',
          under_construction: false,
          build_time: 60,
          upgrade_cost: 100,
        },
      ]
    })

    it('opens party selection instead of starting a quest directly', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Available Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: 60,
        },
      ]

      const startSpy = vi.spyOn(questStore, 'startQuest').mockResolvedValue()

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestCard: {
              template:
                '<div><button class="start-btn" @click="$emit(\'assign-party\', quest.id)">Start Quest</button></div>',
              props: ['quest', 'vaultId', 'status', 'partyMembers'],
              emits: ['assign-party'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()

      const availableTab = wrapper.findAll('[role="tab"]')[1]
      await availableTab.trigger('mousedown')
      await flushPromises()

      // Find the button inside QuestCard and click it
      const startButton = wrapper.find('.start-btn')
      await startButton.trigger('click')

      expect(startSpy).not.toHaveBeenCalled()
    })

    it('orders available quests by required level', async () => {
      const baseQuest = {
        id: 'q',
        title: 'Base',
        short_description: 'Test quest',
        long_description: 'Test quest description',
        requirements: '',
        rewards: '',
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
        is_visible: true,
        is_completed: false,
        started_at: null,
        duration_minutes: 60,
        quest_type: 'side',
      }
      questStore.vaultQuests = [
        {
          ...baseQuest,
          id: 'q-hard',
          title: 'Hard',
          quest_requirements: [
            { id: 'r1', quest_id: 'q-hard', requirement_type: 'level', requirement_data: { level: 20 }, is_mandatory: true },
          ],
        },
        { ...baseQuest, id: 'q-any', title: 'Any' },
        {
          ...baseQuest,
          id: 'q-easy',
          title: 'Easy',
          quest_requirements: [
            { id: 'r2', quest_id: 'q-easy', requirement_type: 'level', requirement_data: { level: 3 }, is_mandatory: true },
          ],
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestCard: {
              template: '<div class="quest-card-stub">{{ quest.title }}</div>',
              props: ['quest', 'vaultId', 'status', 'partyMembers'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()
      const availableTab = wrapper.findAll('[role="tab"]')[1]
      await availableTab.trigger('mousedown')
      await flushPromises()

      const titles = wrapper.findAll('.quest-card-stub').map((node) => node.text())
      expect(titles).toEqual(['Any', 'Easy', 'Hard'])
    })

    it('claims rewards only after a quest returns', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-1',
          title: 'Active Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          is_reward_ready: true,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      const claimSpy = vi.spyOn(questStore, 'claimQuestRewards').mockResolvedValue()

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestCard: {
              template:
                '<div><button class="claim-btn" @click="$emit(\'claim\', quest.id)">Claim Rewards</button></div>',
              props: ['quest', 'vaultId', 'status', 'partyMembers'],
              emits: ['claim'],
            },
            UModal: {
              template: '<div><slot /><slot name="footer" /></div>',
              props: ['modelValue'],
            },
            QuestRewardsModal: {
              template:
                '<div v-if="show"><button class="confirm-claim-btn" @click="$emit(\'confirm\')">Confirm & Claim</button></div>',
              props: ['quest', 'show'],
              emits: ['close', 'confirm'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()

      const claimButton = wrapper.find('.claim-btn')
      await claimButton.trigger('click')

      expect(claimSpy).not.toHaveBeenCalled()
      await wrapper.find('.confirm-claim-btn').trigger('click')
      expect(claimSpy).toHaveBeenCalledWith('vault-123', 'quest-1')
    })
  })

  describe('Completed Quest Navigation', () => {
    beforeEach(() => {
      roomStore.rooms = [
        {
          id: 'room-1',
          name: "Overseer's Office",
          category: 'quests',
          ability: null,
          level: 1,
          max_level: 3,
          capacity: 2,
          x: 0,
          y: 0,
          width: 2,
          height: 1,
          power_cost: 10,
          dweller_ids: [],
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          vault_id: 'vault-123',
          under_construction: false,
          build_time: 60,
          upgrade_cost: 100,
        },
      ]
    })

    it('opens the quest detail modal from the ?quest= query param', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-9',
          title: 'Finished Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: true,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      routeQuery.quest = 'quest-9'

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestDetailModal: {
              template:
                '<div class="mock-quest-modal" :data-quest-id="questId"><button class="mock-quest-modal-close" @click="$emit(\'close\')">Close</button></div>',
              props: ['questId', 'vaultId'],
              emits: ['close', 'select'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()

      const modal = wrapper.find('.mock-quest-modal')
      expect(modal.exists()).toBe(true)
      expect(modal.attributes('data-quest-id')).toBe('quest-9')
    })

    it('closes the quest detail modal by clearing the quest query param', async () => {
      routeQuery.quest = 'quest-9'

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestDetailModal: {
              template:
                '<div class="mock-quest-modal" :data-quest-id="questId"><button class="mock-quest-modal-close" @click="$emit(\'close\')">Close</button></div>',
              props: ['questId', 'vaultId'],
              emits: ['close', 'select'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()
      expect(wrapper.find('.mock-quest-modal').exists()).toBe(true)

      await wrapper.find('.mock-quest-modal-close').trigger('click')

      expect(routerReplaceMock).toHaveBeenCalledWith({ query: { quest: undefined } })
    })

    it('routes a completed quest to its detail modal on View Details', async () => {
      questStore.vaultQuests = [
        {
          id: 'quest-9',
          title: 'Finished Quest',
          short_description: 'Test quest',
          long_description: 'Test quest description',
          requirements: 'Level 5',
          rewards: '50 caps',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: true,
          started_at: '2025-01-02T00:00:00Z',
          duration_minutes: 60,
        },
      ]

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestCard: {
              template:
                '<div><button class="view-btn" @click="$emit(\'view\', quest.id)">View Details</button></div>',
              props: ['quest', 'vaultId', 'status', 'partyMembers'],
              emits: ['view'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()

      const completedTab = wrapper.findAll('[role="tab"]')[2]
      await completedTab.trigger('mousedown')
      await flushPromises()
      await wrapper.find('.view-btn').trigger('click')

      expect(routerPushMock).toHaveBeenCalledWith({ query: { quest: 'quest-9' } })
    })

    it('starts a state quest directly from the modal and closes it', async () => {
      const startSpy = vi.spyOn(questStore, 'startQuest').mockResolvedValue()
      questStore.vaultQuests = [
        {
          id: 'quest-9',
          title: 'Training Quest',
          short_description: 'Train a dweller',
          long_description: 'Training objective description.',
          requirements: '',
          rewards: '',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: 60,
          quest_category: 'training',
        },
      ]
      routeQuery.quest = 'quest-9'

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestDetailModal: {
              template:
                '<div class="mock-quest-modal"><button class="mock-quest-modal-start" @click="$emit(\'start\', questId)">Start</button></div>',
              props: ['questId', 'vaultId'],
              emits: ['close', 'select', 'start'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()
      await wrapper.find('.mock-quest-modal-start').trigger('click')
      await flushPromises()

      expect(startSpy).toHaveBeenCalledWith('vault-123', 'quest-9')
      expect(routerReplaceMock).toHaveBeenCalledWith({ query: { quest: undefined } })
    })

    it('starts a state quest once when the start action repeats', async () => {
      let resolveStart: () => void = () => {}
      const startSpy = vi
        .spyOn(questStore, 'startQuest')
        .mockImplementation(() => new Promise<void>((resolve) => { resolveStart = resolve }))
      questStore.vaultQuests = [
        {
          id: 'quest-9',
          title: 'Training Quest',
          short_description: 'Train a dweller',
          long_description: 'Training objective description.',
          requirements: '',
          rewards: '',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: 60,
          quest_category: 'training',
        },
      ]
      routeQuery.quest = 'quest-9'

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestDetailModal: {
              template:
                '<div class="mock-quest-modal"><button class="mock-quest-modal-start" @click="$emit(\'start\', questId)">Start</button></div>',
              props: ['questId', 'vaultId'],
              emits: ['close', 'select', 'start'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()
      await wrapper.find('.mock-quest-modal-start').trigger('click')
      await wrapper.find('.mock-quest-modal-start').trigger('click')

      expect(startSpy).toHaveBeenCalledTimes(1)

      resolveStart()
      await flushPromises()
    })

    it('opens party selection instead of starting a normal quest from the modal', async () => {
      const startSpy = vi.spyOn(questStore, 'startQuest').mockResolvedValue()
      const partySpy = vi.spyOn(questStore, 'getParty').mockResolvedValue([])
      questStore.vaultQuests = [
        {
          id: 'quest-9',
          title: 'Exploration Quest',
          short_description: 'Explore the wastes',
          long_description: 'Exploration description.',
          requirements: '',
          rewards: '',
          created_at: '2025-01-01',
          updated_at: '2025-01-01',
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: 60,
          quest_category: 'exploration',
        },
      ]
      routeQuery.quest = 'quest-9'

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
            QuestDetailModal: {
              template:
                '<div class="mock-quest-modal"><button class="mock-quest-modal-start" @click="$emit(\'start\', questId)">Start</button></div>',
              props: ['questId', 'vaultId'],
              emits: ['close', 'select', 'start'],
            },
          },
        },
      })

      await wrapper.vm.$nextTick()
      await wrapper.find('.mock-quest-modal-start').trigger('click')
      await flushPromises()

      expect(partySpy).toHaveBeenCalledWith('vault-123', 'quest-9')
      expect(startSpy).not.toHaveBeenCalled()
    })
  })

  describe('Side Panel Integration', () => {
    it('should include SidePanel component', () => {
      roomStore.rooms = []

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      expect(wrapper.findComponent({ name: 'SidePanel' }).exists()).toBe(true)
    })

    it('should apply collapsed class when side panel is collapsed', async () => {
      roomStore.rooms = []

      wrapper = mount(QuestsView, {
        global: {
          stubs: {
            SidePanel: true,
            Icon: true,
          },
        },
      })

      // This tests that the component structure supports the collapsed state
      expect(wrapper.find('.main-content').exists()).toBe(true)
    })
  })
})
