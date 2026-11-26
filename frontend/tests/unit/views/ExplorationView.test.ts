import { afterEach, beforeEach, describe, expect, it, vi } from 'vite-plus/test'
import { createIconifyMock, createRouterMock, createToastMock } from '../helpers/mocks'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ExplorationView from '@/modules/exploration/views/ExplorationView.vue'
import {
  ACTIVE_EXPLORATIONS_REFRESH_MS,
  useExplorationStore,
} from '@/modules/exploration/stores/exploration'
import type { Exploration, PendingOverflow } from '@/modules/exploration/stores/exploration'
import type { ExplorationPartyMember } from '@/modules/exploration/api/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import {
  acknowledgeReport,
  addPendingReport,
  removePendingReport,
  usePendingReports,
} from '@/modules/exploration/composables/usePendingReports'

vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' } }))

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-mock" />', props: [] })
)

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

const pollState = vi.hoisted(() => ({
  callback: null as null | (() => Promise<void> | void),
  interval: null as number | null,
}))
vi.mock('@/core/composables/usePolling', () => ({
  usePolling: (callback: () => Promise<void> | void, options?: { interval?: number }) => {
    pollState.callback = callback
    pollState.interval = options?.interval ?? null
    return {
      run: vi.fn(),
      pause: vi.fn(),
      resume: vi.fn(),
      isActive: { value: false },
      isRefreshing: { value: false },
    }
  },
}))

const soundMock = vi.hoisted(() => ({
  playMusic: vi.fn(),
  playSound: vi.fn(),
  stopMusic: vi.fn(),
}))

vi.mock('@/core/composables/useSound', () => ({
  useSound: () => soundMock,
}))

const quest = (overrides: Record<string, unknown> = {}) => ({
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
  ...overrides,
})

const returningQuest = quest({
  id: 'quest-returning',
  title: 'Returning Quest',
  return_started_at: '2025-01-02T01:00:00Z',
  return_completes_at: '2025-01-02T01:15:00Z',
})

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

const loot = (overrides: Record<string, unknown> = {}) => ({
  item_name: 'Wonderglue',
  quantity: 1,
  rarity: 'Common',
  found_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

const overflow = (explorationId: string, items: Record<string, unknown>[] = [loot()]) => ({
  exploration_id: explorationId,
  dweller_id: 'dweller-1',
  unclaimed_loot: items,
})

/** A queued local return report; the rewards payload is what the modal renders. */
const pendingReport = (explorationId: string, overrides: Record<string, unknown> = {}) => ({
  explorationId,
  vaultId: 'vault-123',
  dwellerId: 'dweller-1',
  dwellerName: 'Lucy MacLean',
  rewards: {
    caps: 25,
    items: [],
    experience: 10,
    distance: 5,
    enemies_defeated: 0,
    events_encountered: 1,
  },
  ...overrides,
})

const partyCards = (template: string) => ({
  name: 'QuestPartyCard',
  template,
  props: ['quest', 'partyMembers', 'selected'],
  emits: ['select'],
})

const explorerCards = (template: string) => ({
  name: 'ExplorerCard',
  template,
  props: ['exploration', 'dweller', 'partyMembers', 'selected'],
  emits: ['select', 'complete', 'recall'],
})

const rewardsModal = () => ({
  name: 'ExplorationRewardsModal',
  template: '<div class="rewards-modal-mock" v-if="show" />',
  props: ['show', 'rewards', 'dwellerName', 'explorationId', 'pendingOnly'],
  emits: ['close', 'resolved'],
})

describe('ExplorationView', () => {
  let wrapper: VueWrapper
  let explorationStore: ReturnType<typeof useExplorationStore>
  let dwellerStore: ReturnType<typeof useDwellerStore>['filter']
  let questStore: ReturnType<typeof useQuestStore>
  let authStore: ReturnType<typeof useAuthStore>

  async function mountView(stubs: Record<string, unknown> = {}, attachTo?: HTMLElement) {
    wrapper = mount(ExplorationView, {
      ...(attachTo ? { attachTo } : {}),
      global: {
        stubs: {
          SidePanel: true,
          QuestPartyCard: true,
          ExplorationRewardsModal: true,
          ...stubs,
        },
      },
    })
    await flushPromises()
    return wrapper
  }

  const modal = () => wrapper.findComponent({ name: 'ExplorationRewardsModal' })
  const banner = () => wrapper.find('.deferred-overflow-banner')
  const reviewDeferred = async () => {
    await wrapper.find('.deferred-overflow-banner button').trigger('click')
    await flushPromises()
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    explorationStore = useExplorationStore()
    dwellerStore = useDwellerStore().filter
    questStore = useQuestStore()
    authStore = useAuthStore()

    vi.clearAllMocks()

    for (const report of usePendingReports().pendingReports.value) removePendingReport(report.id)

    // Keep onMounted off the network.
    vi.spyOn(explorationStore, 'refreshActiveExplorations').mockResolvedValue([])
    vi.spyOn(explorationStore, 'fetchPendingOverflow').mockResolvedValue([])
    vi.spyOn(explorationStore, 'startSseSubscription').mockImplementation(() => {})
    vi.spyOn(explorationStore, 'stopSseSubscription').mockImplementation(() => {})
    vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue([])
    vi.spyOn(dwellerStore, 'fetchDwellerDetails').mockResolvedValue(undefined)
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchPartiesForActiveQuests').mockResolvedValue()
    vi.spyOn(useVaultStore(), 'ensureVaultLoaded').mockResolvedValue()

    authStore.token = 'mock-token'
    dwellerStore.dwellers = [
      { id: 'dweller-1', first_name: 'Lucy', last_name: 'MacLean', level: 5 },
    ]
  })

  afterEach(() => {
    wrapper?.unmount()
  })

  it('loads the list and parties through the store on mount', async () => {
    await mountView()

    expect(explorationStore.refreshActiveExplorations).toHaveBeenCalledWith('vault-123', {
      includeParties: true,
    })
  })

  it('stops loading when vault adoption fails', async () => {
    vi.mocked(useVaultStore().ensureVaultLoaded).mockRejectedValueOnce(
      new Error('Vault unavailable')
    )

    await mountView()

    expect(dwellerStore.fetchDwellersByVault).not.toHaveBeenCalled()
    expect(questStore.fetchVaultQuests).not.toHaveBeenCalled()
    expect(questStore.fetchPartiesForActiveQuests).not.toHaveBeenCalled()
  })

  it('refreshes the list with a silent poll and keeps the quest refreshes', async () => {
    await mountView()

    vi.mocked(explorationStore.refreshActiveExplorations).mockClear()
    await pollState.callback?.()

    expect(explorationStore.refreshActiveExplorations).toHaveBeenCalledWith('vault-123', {
      includeParties: true,
      silent: true,
    })
    expect(questStore.fetchVaultQuests).toHaveBeenCalledWith('vault-123', { silent: true })
    expect(questStore.fetchPartiesForActiveQuests).toHaveBeenCalledWith('vault-123')
  })

  it('polls at the shared active-exploration cadence', async () => {
    await mountView()

    expect(pollState.interval).toBe(ACTIVE_EXPLORATIONS_REFRESH_MS)
  })

  it('explains return settlement through optional page help', async () => {
    await mountView({ Teleport: { template: '<div><slot /></div>' } }, document.body)

    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    await vi.waitFor(() =>
      expect(wrapper.find('button[aria-label="About Wasteland Exploration"]').exists()).toBe(true)
    )
    await wrapper.find('button[aria-label="About Wasteland Exploration"]').trigger('click')
    await flushPromises()

    const help = wrapper.find('[role="dialog"]')
    expect(help.text()).toContain('Recall starts the journey home')
    expect(help.text()).toContain('settled on arrival')
    expect(help.text()).toContain('Quest parties have a separate reward claim')
  })

  it('keeps quest parties visible while they travel home', async () => {
    questStore.vaultQuests = [quest(), returningQuest] as never
    questStore.questPartyMap = {
      'quest-active': [{ ...partyMember, quest_id: 'quest-active' }],
      'quest-returning': [partyMember],
    } as never

    await mountView({
      QuestPartyCard: partyCards(
        '<div class="quest-party-stub" :data-quest-id="quest.id">{{ quest.title }}</div>'
      ),
      ExplorationRewardsModal: rewardsModal(),
    })

    expect(wrapper.findAll('[role="tab"]')[1]!.attributes('aria-selected')).toBe('true')

    // The outbound party renders as before…
    expect(wrapper.find('[data-quest-id="quest-active"]').exists()).toBe(true)
    // …and the returning party stays on Exploration until it arrives.
    expect(wrapper.find('[data-quest-id="quest-returning"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Returning Quest')
    expect(wrapper.find('.empty-state').exists()).toBe(false)
  })

  it('plays exploration music on mount and restores the vault loop on unmount', async () => {
    await mountView()

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
    ] as never

    await mountView({
      ExplorerCard: explorerCards(
        '<div class="explorer-card-stub" :data-exploration-id="exploration.id" :data-party-count="partyMembers?.length ?? 0" />'
      ),
    })

    expect(wrapper.find('.page-header-metric-value').text()).toBe('3')
    expect(
      wrapper.find('[data-exploration-id="exploration-party"]').attributes('data-party-count')
    ).toBe('2')
  })

  it('switches between the Active explorers and Quest parties tabs', async () => {
    explorationStore.activeExplorations = {
      'exploration-party': activeRun('exploration-party', 'dweller-1'),
    }
    explorationStore.explorationPartyMap = {
      'exploration-party': [explorationPartyMember('p-1', 'dweller-1', 1)],
    }
    questStore.vaultQuests = [quest()] as never
    questStore.questPartyMap = {
      'quest-active': [{ ...partyMember, quest_id: 'quest-active' }],
    } as never

    await mountView({
      ExplorationEventLog: true,
      ExplorerCard: explorerCards(
        '<div class="explorer-card-stub" :data-exploration-id="exploration.id" />'
      ),
      QuestPartyCard: partyCards('<div class="quest-party-stub" :data-quest-id="quest.id" />'),
    })

    let tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map((tab) => tab.text())).toEqual(['Active explorers (1)', 'Quest parties (1)'])
    expect(tabs[0]!.attributes('aria-selected')).toBe('true')

    // Active explorers is the default tab: its grid renders, quest content does not.
    expect(wrapper.find('[data-exploration-id="exploration-party"]').exists()).toBe(true)
    expect(wrapper.find('[data-quest-id="quest-active"]').exists()).toBe(false)

    wrapper.findComponent({ name: 'ExplorerCard' }).vm.$emit('select')
    await flushPromises()
    expect(wrapper.find('.timeline-section').exists()).toBe(true)

    // reka-ui activates tabs on mousedown (not click).
    await tabs[1]!.trigger('mousedown')
    await flushPromises()

    tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[1]!.attributes('aria-selected')).toBe('true')
    expect(wrapper.find('[data-quest-id="quest-active"]').exists()).toBe(true)
    expect(wrapper.find('[data-exploration-id="exploration-party"]').exists()).toBe(false)
    expect(wrapper.find('.timeline-section').exists()).toBe(false)

    await tabs[0]!.trigger('mousedown')
    await flushPromises()

    tabs = wrapper.findAll('[role="tab"]')
    expect(tabs[0]!.attributes('aria-selected')).toBe('true')
    expect(wrapper.find('[data-exploration-id="exploration-party"]').exists()).toBe(true)
    expect(wrapper.find('[data-quest-id="quest-active"]').exists()).toBe(false)
    expect(wrapper.find('.timeline-section').exists()).toBe(true)

    explorationStore.activeExplorations = {}
    await flushPromises()
    expect(wrapper.findAll('[role="tab"]')[0]!.attributes('aria-selected')).toBe('true')
    expect(wrapper.findAll('[role="tab"]')[0]!.text()).toBe('Active explorers (0)')
  })

  it('keeps a deferred return available for review without remounting', async () => {
    vi.mocked(explorationStore.fetchPendingOverflow).mockResolvedValue([
      overflow('exploration-overflow'),
    ])
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    expect(modal().props('show')).toBe(true)
    expect(modal().props('pendingOnly')).toBe(true)

    modal().vm.$emit('close', true)
    await flushPromises()

    expect(modal().props('show')).toBe(false)
    expect(banner().exists()).toBe(true)
    expect(wrapper.text()).toContain('1 return still needs a storage decision')

    await reviewDeferred()

    expect(modal().props('show')).toBe(true)
    expect(modal().props('pendingOnly')).toBe(true)
  })

  it('clears a deferred return the backend no longer reports, and says so', async () => {
    vi.mocked(explorationStore.fetchPendingOverflow).mockResolvedValue([
      overflow('exploration-overflow'),
    ])
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    // Player walks away from the storage decision: the return is remembered.
    modal().vm.$emit('close', true)
    await flushPromises()
    expect(banner().exists()).toBe(true)

    // The decisions were settled elsewhere, so the backend reports nothing pending.
    let resolvePending!: (value: PendingOverflow[]) => void
    vi.mocked(explorationStore.fetchPendingOverflow).mockImplementation(
      () =>
        new Promise<PendingOverflow[]>((resolve) => {
          resolvePending = resolve
        })
    )

    const reviewButton = wrapper.find('.deferred-overflow-banner button')
    await reviewButton.trigger('click')
    expect(reviewButton.text()).toBe('Checking…')
    expect(reviewButton.attributes('disabled')).toBeDefined()

    resolvePending([])
    await flushPromises()

    expect(modal().props('show')).toBe(false)
    expect(banner().exists()).toBe(false)
    expect(mockToast.info).toHaveBeenCalledWith(
      'Nothing left to resolve — those storage decisions were already settled.'
    )
  })

  it('drops a local deferred id after its queued report is acknowledged elsewhere', async () => {
    addPendingReport(
      pendingReport('exploration-settled-elsewhere', { dwellerName: 'Christina Reid' })
    )
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    modal().vm.$emit('close', true)
    await flushPromises()
    expect(banner().exists()).toBe(true)

    acknowledgeReport('exploration-settled-elsewhere')
    await flushPromises()

    expect(banner().exists()).toBe(false)
  })

  it('still shows a queued return report when unresolved returns cannot load', async () => {
    addPendingReport(pendingReport('exploration-report'))
    vi.mocked(explorationStore.fetchPendingOverflow).mockRejectedValue(new Error('offline'))
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    expect(modal().props('show')).toBe(true)
    expect(modal().props('pendingOnly')).toBe(false)
    expect(modal().props('explorationId')).toBe('exploration-report')
  })

  it('surfaces a deferred report overflow through the review banner', async () => {
    vi.mocked(explorationStore.fetchPendingOverflow)
      .mockResolvedValueOnce([])
      .mockResolvedValue([overflow('exploration-report-overflow')])
    addPendingReport(
      pendingReport('exploration-report-overflow', {
        rewards: {
          caps: 25,
          items: [],
          overflow_items: [loot()],
          experience: 10,
          distance: 5,
          enemies_defeated: 0,
          events_encountered: 1,
        },
      })
    )
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    expect(modal().props('show')).toBe(true)
    expect(modal().props('pendingOnly')).toBe(false)

    modal().vm.$emit('close', true)
    await flushPromises()
    expect(banner().exists()).toBe(true)

    await reviewDeferred()

    expect(modal().props('show')).toBe(true)
    expect(modal().props('pendingOnly')).toBe(true)
  })

  it('opens a queued report with no decision when the overflow was settled already', async () => {
    // The report was written while an overflow item was pending; by the time it is opened the
    // backend reports none, so the modal must not advertise "Resolve Later" over a stale list.
    addPendingReport(
      pendingReport('exploration-settled', {
        dwellerName: 'Christina Reid',
        rewards: {
          caps: 18,
          items: [],
          overflow_items: [loot({ item_name: 'Shovel', rarity: 'Rare' })],
          experience: 18,
          distance: 0,
          enemies_defeated: 0,
          events_encountered: 0,
        },
      })
    )
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    expect(modal().props('show')).toBe(true)
    expect(modal().props('rewards').overflow_items).toEqual([])
  })

  it('does not reopen a report that was acknowledged when SSE replays', async () => {
    acknowledgeReport('exploration-replayed')
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    explorationStore.pendingSseRewards = {
      rewards: {
        caps: 10,
        items: [],
        experience: 1,
        distance: 1,
        enemies_defeated: 0,
        events_encountered: 0,
      },
      dwellerId: 'dweller-1',
      explorationId: 'exploration-replayed',
    } as never
    await flushPromises()

    expect(modal().props('show')).toBe(false)
    expect(explorationStore.pendingSseRewards).toBeNull()
  })

  it('keeps the queued full report after resolving its pending-only overflow', async () => {
    vi.mocked(explorationStore.fetchPendingOverflow).mockResolvedValue([
      overflow('exploration-both'),
    ])
    addPendingReport(
      pendingReport('exploration-both', {
        rewards: {
          caps: 50,
          items: [],
          experience: 10,
          distance: 5,
          enemies_defeated: 0,
          events_encountered: 1,
        },
      })
    )
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    expect(modal().props('pendingOnly')).toBe(true)

    modal().vm.$emit('close', false)
    await flushPromises()

    expect(modal().props('show')).toBe(true)
    expect(modal().props('pendingOnly')).toBe(false)
    expect(modal().props('explorationId')).toBe('exploration-both')
    expect(usePendingReports().pendingReports.value).toHaveLength(1)

    modal().vm.$emit('close', false)
    await flushPromises()

    expect(usePendingReports().pendingReports.value).toHaveLength(0)
  })

  it('keeps a deferred queued report reviewable when overflow loading fails', async () => {
    vi.mocked(explorationStore.fetchPendingOverflow).mockRejectedValue(new Error('offline'))
    addPendingReport(
      pendingReport('exploration-deferred-report', {
        rewards: {
          caps: 25,
          items: [],
          overflow_items: [loot()],
          experience: 10,
          distance: 5,
          enemies_defeated: 0,
          events_encountered: 1,
        },
      })
    )
    await mountView({ ExplorationRewardsModal: rewardsModal() })

    expect(modal().props('pendingOnly')).toBe(false)
    expect(modal().props('rewards').overflow_items).toHaveLength(1)

    modal().vm.$emit('close', true)
    await flushPromises()
    expect(banner().exists()).toBe(true)

    await reviewDeferred()

    expect(modal().props('show')).toBe(true)
    expect(modal().props('explorationId')).toBe('exploration-deferred-report')
    expect(modal().props('rewards').overflow_items).toHaveLength(1)
  })
})
