import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createIconifyMock, createRouterMock, createToastMock } from '../helpers/mocks'
import { flushPromises, mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ExplorationView from '@/modules/exploration/views/ExplorationView.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { ExplorationPartyMember } from '@/modules/exploration/api/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useAuthStore } from '@/modules/auth/stores/auth'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' } }))

vi.mock('@iconify/vue', () => createIconifyMock({ template: '<span class="icon-mock" />', props: [] }))

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

vi.mock('@/core/composables/usePolling', () => ({
  usePolling: () => ({
    run: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    isActive: { value: false },
    isRefreshing: { value: false },
  }),
}))

const soundMock = vi.hoisted(() => ({
  playMusic: vi.fn(),
  playSound: vi.fn(),
  stopMusic: vi.fn(),
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => soundMock,
}))

const returningQuest = {
  id: 'quest-returning',
  title: 'Returning Quest',
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
}

const activeQuest = {
  id: 'quest-active',
  title: 'Active Quest',
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
}

const partyMember = {
  id: 'pm-1',
  quest_id: 'quest-returning',
  vault_id: 'vault-123',
  dweller_id: 'dweller-1',
  slot_number: 1,
  status: 'in_progress',
  created_at: '2025-01-01',
  updated_at: '2025-01-01',
}

const activeRun = (id: string, dwellerId: string): Exploration =>
  ({
    id,
    vault_id: 'vault-123',
    dweller_id: dwellerId,
    status: 'active',
    duration: 4,
    start_time: '2025-01-02T00:00:00Z',
    end_time: null,
    events: [],
    loot_collected: [],
    total_distance: 0,
    total_caps_found: 0,
    enemies_encountered: 0,
    created_at: '2025-01-01',
    updated_at: '2025-01-01',
    dweller_strength: 1,
    dweller_perception: 1,
    dweller_endurance: 1,
    dweller_charisma: 1,
    dweller_intelligence: 1,
    dweller_agility: 1,
    dweller_luck: 1,
    stimpaks: 0,
    radaways: 0,
  }) as Exploration

const explorationPartyMember = (
  id: string,
  dwellerId: string,
  slot: number
): ExplorationPartyMember => ({
  id,
  exploration_id: 'exploration-party',
  vault_id: 'vault-123',
  dweller_id: dwellerId,
  slot_number: slot,
  status: 'assigned',
  created_at: null,
  updated_at: null,
})

describe('ExplorationView', () => {
  let wrapper: VueWrapper
  let explorationStore: ReturnType<typeof useExplorationStore>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let questStore: ReturnType<typeof useQuestStore>
  let authStore: ReturnType<typeof useAuthStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    explorationStore = useExplorationStore()
    dwellerStore = useDwellerStore().filter
    questStore = useQuestStore()
    authStore = useAuthStore()

    vi.clearAllMocks()

    // Keep onMounted off the network.
    vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue([])
    vi.spyOn(explorationStore, 'fetchPartiesForActiveExplorations').mockResolvedValue()
    vi.spyOn(explorationStore, 'fetchPendingOverflow').mockResolvedValue([])
    vi.spyOn(explorationStore, 'startSseSubscription').mockImplementation(() => {})
    vi.spyOn(explorationStore, 'stopSseSubscription').mockImplementation(() => {})
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue([])
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(undefined)
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchPartiesForActiveQuests').mockResolvedValue()

    authStore.token = 'mock-token'
    dwellerStore.dwellers = [
      { id: 'dweller-1', first_name: 'Lucy', last_name: 'MacLean', level: 5 },
    ]
  })

  afterEach(() => {
    wrapper?.unmount()
  })

  it('keeps quest parties visible while they travel home', async () => {
    questStore.vaultQuests = [activeQuest, returningQuest]
    questStore.questPartyMap = {
      'quest-active': [{ ...partyMember, quest_id: 'quest-active' }],
      'quest-returning': [partyMember],
    }

    wrapper = mount(ExplorationView, {
      global: {
        stubs: {
          SidePanel: true,
          QuestPartyCard: {
            name: 'QuestPartyCard',
            template:
              '<div class="quest-party-stub" :data-quest-id="quest.id">{{ quest.title }}</div>',
            props: ['quest', 'partyMembers', 'selected'],
            emits: ['select'],
          },
          ExplorationRewardsModal: {
            name: 'ExplorationRewardsModal',
            template: '<div class="rewards-modal-mock" v-if="show"></div>',
            props: ['show', 'rewards', 'dwellerName', 'explorationId', 'pendingOnly'],
            emits: ['close', 'resolved'],
          },
        },
      },
    })
    await flushPromises()

    // The outbound party renders as before…
    expect(wrapper.find('[data-quest-id="quest-active"]').exists()).toBe(true)
    // …and the returning party stays on Exploration until it arrives.
    expect(wrapper.find('[data-quest-id="quest-returning"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Returning Quest')
    expect(wrapper.find('.empty-state').exists()).toBe(false)
  })

  it('plays exploration music on mount and restores the vault loop on unmount', async () => {
    wrapper = mount(ExplorationView, {
      global: {
        stubs: {
          SidePanel: true,
          QuestPartyCard: true,
          ExplorationRewardsModal: true,
        },
      },
    })
    await flushPromises()

    expect(soundMock.playMusic).toHaveBeenCalledWith('exploration')

    wrapper.unmount()
    expect(soundMock.playMusic).toHaveBeenCalledWith('vaultAmbient')
  })

  it('passes dispatch party members to the card and counts dwellers across active runs', async () => {
    explorationStore.activeExplorations = {
      'exploration-party': activeRun('exploration-party', 'dweller-1'),
      'exploration-solo': activeRun('exploration-solo', 'dweller-3'),
    }
    explorationStore.explorationPartyMap = {
      'exploration-party': [
        explorationPartyMember('p-1', 'dweller-1', 1),
        explorationPartyMember('p-2', 'dweller-2', 2),
      ],
      'exploration-solo': [],
    }
    dwellerStore.dwellers = [
      { id: 'dweller-1', first_name: 'Lucy', last_name: 'MacLean', level: 5 },
      { id: 'dweller-2', first_name: 'Carla', last_name: 'Vault', level: 4 },
      { id: 'dweller-3', first_name: 'Bea', last_name: 'Vault', level: 3 },
    ]

    wrapper = mount(ExplorationView, {
      global: {
        stubs: {
          SidePanel: true,
          QuestPartyCard: true,
          ExplorationRewardsModal: true,
          ExplorerCard: {
            name: 'ExplorerCard',
            template:
              '<div class="explorer-card-stub" :data-exploration-id="exploration.id" :data-party-count="partyMembers?.length ?? 0" />',
            props: ['exploration', 'dweller', 'partyMembers', 'selected'],
            emits: ['select', 'complete', 'recall'],
          },
        },
      },
    })
    await flushPromises()

    expect(wrapper.find('.page-header-metric-value').text()).toBe('3')
    expect(
      wrapper.find('[data-exploration-id="exploration-party"]').attributes('data-party-count')
    ).toBe('2')
  })
})
