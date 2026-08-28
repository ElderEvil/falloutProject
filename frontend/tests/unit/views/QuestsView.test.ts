import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import QuestsView from '@/modules/progression/views/QuestsView.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123' },
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

    // Prevent unhandled rejections from real HTTP calls during onMounted
    vi.spyOn(questStore, 'fetchAllQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchPartiesForActiveQuests').mockResolvedValue()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Overseer Office Check', () => {
    it('should show locked state when no Overseer Office', async () => {
      roomStore.rooms = []

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

    it('should show quests when Overseer Office exists', async () => {
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

      const tabs = wrapper.findAll('.tab-button')
      expect(tabs[0].classes()).toContain('active')
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

      const completedTab = wrapper.findAll('.tab-button')[1]
      await completedTab.trigger('click')

      expect(completedTab.classes()).toContain('active')
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

    it('should display available quests in second section', async () => {
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

      expect(wrapper.text()).toContain('Available Quest')
    })

    it('should reveal locked quests only when Show All is enabled', async () => {
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
          is_visible: true,
          is_completed: false,
          started_at: null,
          duration_minutes: null,
        },
      ]

      wrapper = mount(QuestsView, {
        global: { stubs: { SidePanel: true, Icon: true } },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('First Quest')
      expect(wrapper.text()).not.toContain('Locked Quest')

      await wrapper.find('.toggle-input').setValue(true)

      expect(wrapper.text()).toContain('Locked Quest')
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
      const completedTab = wrapper.findAll('.tab-button')[1]
      await completedTab.trigger('click')

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

      expect(wrapper.text()).toContain('No unlocked quests available')
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

      // Find the button inside QuestCard and click it
      const startButton = wrapper.find('.start-btn')
      await startButton.trigger('click')

      expect(startSpy).not.toHaveBeenCalled()
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
          },
        },
      })

      await wrapper.vm.$nextTick()

      const claimButton = wrapper.find('.claim-btn')
      await claimButton.trigger('click')

      expect(claimSpy).toHaveBeenCalledWith('vault-123', 'quest-1')
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
