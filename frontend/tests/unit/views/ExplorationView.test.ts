import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ExplorationView from '@/modules/exploration/views/ExplorationView.vue'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useAuthStore } from '@/modules/auth/stores/auth'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'vault-123' } }),
}))

vi.mock('@iconify/vue', () => ({
  Icon: { name: 'Icon', template: '<span class="icon-mock" />' },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  }),
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
})
