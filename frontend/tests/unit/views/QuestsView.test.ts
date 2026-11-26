import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import { createPinia, disposePinia, getActivePinia, setActivePinia } from 'pinia'
import QuestsView from '@/modules/progression/views/QuestsView.vue'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'

const routerReplaceMock = vi.hoisted(() => vi.fn())
const routerPushMock = vi.hoisted(() => vi.fn())

// Reactive query for claim reward links.
const routeQuery = reactive<Record<string, string | undefined>>({})

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123' },
    query: routeQuery,
  }),
  useRouter: () => ({
    replace: routerReplaceMock,
    push: routerPushMock,
  }),
}))

/** The Overseer's Office room that gates the quest board. */
const office = (overrides: Record<string, unknown> = {}) => ({
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
  ...overrides,
})

/** Unstarted, startable vault quest — the baseline every row tweaks. */
const quest = (overrides: Record<string, unknown> = {}) => ({
  id: 'quest-1',
  title: 'Test Quest',
  short_description: 'Test quest',
  long_description: 'Test quest description',
  requirements: 'Level 5',
  rewards: '50 caps',
  created_at: '2025-01-01',
  updated_at: '2025-01-01',
  is_visible: true,
  is_locked: false,
  lock_reason: null,
  is_completed: false,
  is_reward_ready: false,
  started_at: null,
  duration_minutes: null,
  ...overrides,
})

/** A quest that is out on a run. */
const travelling = (overrides: Record<string, unknown> = {}) =>
  quest({ started_at: '2025-01-02T00:00:00Z', duration_minutes: 60, ...overrides })

/** A quest whose party is back and whose rewards can be claimed. */
const returned = (overrides: Record<string, unknown> = {}) =>
  travelling({ is_reward_ready: true, ...overrides })

const questCard = (template: string, emits: string[] = []) => ({
  template,
  props: ['quest', 'vaultId', 'status', 'partyMembers'],
  ...(emits.length ? { emits } : {}),
})

const rewardsModal = (template: string) => ({
  template,
  props: ['quest', 'show'],
  emits: ['close', 'confirm'],
})

describe('QuestsView', () => {
  let wrapper: VueWrapper
  let questStore: ReturnType<typeof useQuestStore>
  let roomStore: ReturnType<typeof useRoomStore>

  function mountView(stubs: Record<string, unknown> = {}) {
    return mount(QuestsView, { global: { stubs: { SidePanel: true, Icon: true, ...stubs } } })
  }

  /** Seed quests, mount, and wait for the initial load. */
  async function mountWithQuests(quests: Record<string, unknown>[], stubs = {}) {
    questStore.vaultQuests = quests as never
    wrapper = mountView(stubs)
    await flushPromises()
    return wrapper
  }

  const tab = (index: number) => wrapper.findAll('[role="tab"]')[index]!
  const selectTab = async (index: number) => {
    await tab(index).trigger('mousedown')
    await flushPromises()
  }
  const signedIn = () => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('user', JSON.stringify({ id: 'test-user' }))
  }

  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    questStore = useQuestStore()
    roomStore = useRoomStore()
    roomStore.rooms = [office()] as never

    vi.clearAllMocks()
    routeQuery.claimQuest = undefined

    // Tooltip content is teleported to <body>; drop leftovers between tests.
    document.querySelectorAll('[role="tooltip"]').forEach((element) => element.remove())

    // Prevent unhandled rejections from real HTTP calls during onMounted
    vi.spyOn(questStore, 'fetchAllQuests').mockResolvedValue()
    vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
    vi.spyOn(useVaultStore(), 'ensureVaultLoaded').mockResolvedValue()
    vi.spyOn(questStore, 'fetchPartiesForActiveQuests').mockResolvedValue()
  })

  afterEach(() => {
    wrapper?.unmount()
    const pinia = getActivePinia()
    if (pinia) disposePinia(pinia)
    vi.useRealTimers()
    document.querySelectorAll('[role="tooltip"]').forEach((element) => element.remove())
  })

  it('stops before the dweller read when the session changes during the room fetch', async () => {
    localStorage.setItem('token', 'test-token')
    const authStore = useAuthStore()
    const fetchDwellersSpy = vi
      .spyOn(useDwellerStore().filter, 'fetchDwellersByVault')
      .mockResolvedValue()
    let resolveRooms!: (value: 'loaded') => void
    vi.spyOn(roomStore, 'fetchRooms').mockImplementation(
      () =>
        new Promise<'loaded'>((resolve) => {
          resolveRooms = resolve
        })
    )

    wrapper = mountView()
    await flushPromises()

    authStore.sessionGeneration++
    resolveRooms('loaded')
    await flushPromises()

    expect(fetchDwellersSpy).not.toHaveBeenCalled()
  })

  describe('Overseer Office lock', () => {
    it.each([
      [
        'the office lock is reported',
        { is_locked: true, lock_reason: "Requires Overseer's Office" },
        "OVERSEER'S OFFICE REQUIRED",
      ],
      ['no quest reports the lock', {}, 'Test Quest'],
    ])('renders the board when %s', async (_, overrides, expected) => {
      await mountWithQuests([quest(overrides)])
      await nextTick()

      expect(wrapper.find('.locked-container').exists()).toBe(
        expected === "OVERSEER'S OFFICE REQUIRED"
      )
      expect(wrapper.text()).toContain(expected)
    })
  })

  describe('Tabs', () => {
    it('defaults to Available when there are no active quests', async () => {
      await mountWithQuests([])

      expect(tab(1).attributes('aria-selected')).toBe('true')
    })

    it('opens the Overseer Office room from the parties metric', async () => {
      await mountWithQuests([])

      const metric = wrapper
        .findAll('[role="button"]')
        .find((element) => element.attributes('aria-label')?.startsWith('Open Office'))
      expect(metric).toBeTruthy()

      await metric!.trigger('click')

      expect(routerPushMock).toHaveBeenCalledWith({
        path: '/vault/vault-123',
        query: { roomId: 'room-1' },
      })
    })

    it('switches to the completed tab when clicked', async () => {
      await mountWithQuests([])
      await selectTab(2)

      expect(tab(2).attributes('aria-selected')).toBe('true')
      expect(tab(1).attributes('aria-selected')).toBe('false')
    })

    it('switches back to the available tab when clicked', async () => {
      await mountWithQuests([])
      await selectTab(1)

      expect(tab(1).attributes('aria-selected')).toBe('true')
      expect(tab(2).attributes('aria-selected')).toBe('false')
    })
  })

  describe('Quest display', () => {
    it.each([
      ['active', travelling({ title: 'Active Quest' }), 0, 'Active Quest'],
      ['available', quest({ title: 'Available Quest' }), 1, 'Available Quest'],
      ['completed', quest({ title: 'Completed Quest', is_completed: true }), 2, 'Completed Quest'],
    ])('lists %s quests in their tab', async (_, overrides, tabIndex, title) => {
      await mountWithQuests([quest(overrides)])
      if (tabIndex !== 0) await selectTab(tabIndex)

      expect(wrapper.text()).toContain(title)
      expect(wrapper.text()).toContain('Test quest')
    })

    it('refreshes active quests while a party is away', async () => {
      signedIn()
      vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
      await mountWithQuests([travelling({ title: 'Active Quest' })])

      await vi.advanceTimersByTimeAsync(30_000)

      expect(questStore.fetchVaultQuests).toHaveBeenCalledWith('vault-123', { silent: true })
      expect(questStore.fetchPartiesForActiveQuests).toHaveBeenCalledWith('vault-123')
    })

    it('renders travelling quests without a claim action and keeps polling', async () => {
      signedIn()
      vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
      await mountWithQuests([
        travelling({
          title: 'Travelling Quest',
          return_started_at: '2025-01-02T01:00:00Z',
          return_completes_at: '2025-01-02T01:15:00Z',
        }),
      ])
      await nextTick()

      expect(wrapper.text()).toContain('Travelling Quest')
      expect(wrapper.text()).not.toContain('Claim Rewards')

      await vi.advanceTimersByTimeAsync(30_000)
      expect(questStore.fetchVaultQuests).toHaveBeenCalledWith('vault-123', { silent: true })
    })

    it.each([
      ['an unstarted quest', 'Available Quest', {}, '1', true],
      [
        'a started check-objective state quest',
        'Started State Quest',
        { is_reward_ready: true, quest_category: 'training' },
        '0',
        false,
      ],
    ])('places %s in Available by reward state', async (_, title, overrides, metric, shown) => {
      await mountWithQuests([quest({ title, ...overrides })])
      await selectTab(1)

      expect(wrapper.text().includes(title)).toBe(shown)
      expect(wrapper.get('.page-header-metric-value').text()).toBe(metric)
    })

    it('reveals locked quests only when Show All is enabled and renders their lock reason', async () => {
      await mountWithQuests([
        quest({ title: 'First Quest', short_description: 'Start the chain' }),
        quest({
          id: 'daily-visible-locked',
          title: 'Daily Patrol',
          quest_type: 'daily',
          is_locked: true,
          lock_reason: 'Requires a higher dweller level',
        }),
        quest({
          id: 'daily-hidden',
          title: 'Hidden Daily',
          quest_type: 'daily',
          is_visible: false,
          is_locked: true,
          lock_reason: 'Not currently offered',
        }),
        quest({
          id: 'quest-2',
          title: 'Locked Quest',
          is_visible: false,
          is_locked: true,
          lock_reason: 'Requires completing a previous quest',
        }),
      ])
      await selectTab(1)

      expect(wrapper.text()).toContain('First Quest')
      expect(wrapper.text()).not.toContain('Locked Quest')
      // Default filter: startable quests only - the locked daily is not shown yet.
      expect(wrapper.text()).toContain('Other quests (1)')
      expect(wrapper.text()).not.toContain('Daily Patrol')
      expect(wrapper.text()).not.toContain('Hidden Daily')

      await wrapper.find('.toggle-input').setValue(true)

      expect(wrapper.text()).toContain('Locked Quest')
      expect(wrapper.text()).toContain('Requires completing a previous quest')
      // Show All adds the locked previews: the daily group counts its one card,
      // while the hidden scheduler daily stays excluded in both modes.
      expect(wrapper.text()).toContain('Daily quests (1)')
      expect(wrapper.text()).toContain('Daily Patrol')
      expect(wrapper.text()).toContain('Other quests (2)')
      expect(wrapper.text()).not.toContain('Hidden Daily')
    })

    it('shows the empty state when no active quests', async () => {
      await mountWithQuests([])
      await selectTab(0)

      expect(wrapper.text()).toContain('No active quests')
    })
  })

  describe('Quest actions', () => {
    it('opens party selection instead of starting a quest directly', async () => {
      const startSpy = vi.spyOn(questStore, 'startQuest').mockResolvedValue()
      await mountWithQuests([quest({ title: 'Available Quest' })], {
        QuestCard: questCard(
          '<div><button class="start-btn" @click="$emit(\'assign-party\', quest.id)">Start Quest</button></div>',
          ['assign-party']
        ),
      })
      await selectTab(1)

      await wrapper.find('.start-btn').trigger('click')

      expect(startSpy).not.toHaveBeenCalled()
    })

    it('keeps party selection open when both start and its recovery refresh fail', async () => {
      roomStore.rooms = [office({ tier: 1 })] as never
      roomStore.roomsLoadedVaultId = 'vault-123'
      await mountWithQuests([quest({ title: 'Available Quest' })], {
        QuestCard: true,
        PartySelectionModal: true,
      })
      vi.spyOn(questStore, 'startQuest').mockRejectedValue(new Error('No quest slots'))
      vi.spyOn(questStore, 'fetchVaultQuests').mockRejectedValue(new Error('Connection lost'))
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const actions = wrapper.vm as unknown as {
        handleAssignParty: (id: string) => void
        handleAssignAndStart: (ids: string[]) => Promise<void>
      }
      actions.handleAssignParty('quest-1')

      try {
        await expect(actions.handleAssignAndStart(['dweller-1'])).resolves.toBeUndefined()
        expect(questStore.startQuest).toHaveBeenCalledWith('vault-123', 'quest-1', ['dweller-1'])
        expect(questStore.fetchVaultQuests).toHaveBeenLastCalledWith('vault-123', { silent: true })
        expect(
          wrapper.findComponent({ name: 'PartySelectionModal' }).attributes('modelvalue')
        ).toBe('true')
        expect(warn).toHaveBeenCalledWith(
          'Failed to refresh quests after rejected start',
          'Connection lost'
        )
      } finally {
        warn.mockRestore()
      }
    })

    it('orders available quests by required level', async () => {
      const requirement = (questId: string, level: number) => ({
        id: `r-${questId}`,
        quest_id: questId,
        requirement_type: 'level',
        requirement_data: { level },
        is_mandatory: true,
      })
      await mountWithQuests(
        [
          quest({ id: 'q-hard', title: 'Hard', quest_requirements: [requirement('q-hard', 20)] }),
          quest({ id: 'q-any', title: 'Any' }),
          quest({ id: 'q-easy', title: 'Easy', quest_requirements: [requirement('q-easy', 3)] }),
        ],
        { QuestCard: questCard('<div class="quest-card-stub">{{ quest.title }}</div>') }
      )
      await selectTab(1)

      const titles = wrapper.findAll('.quest-card-stub').map((node) => node.text())
      expect(titles).toEqual(['Any', 'Easy', 'Hard'])
    })

    it('claims rewards only after a quest returns', async () => {
      const claimSpy = vi.spyOn(questStore, 'claimQuestRewards').mockResolvedValue()
      await mountWithQuests([returned({ title: 'Active Quest' })], {
        QuestCard: questCard(
          '<div><button class="claim-btn" @click="$emit(\'claim\', quest.id)">Claim Rewards</button></div>',
          ['claim']
        ),
        UModal: { template: '<div><slot /><slot name="footer" /></div>', props: ['modelValue'] },
        QuestRewardsModal: rewardsModal(
          '<div v-if="show"><button class="confirm-claim-btn" @click="$emit(\'confirm\')">Confirm & Claim</button></div>'
        ),
      })

      await wrapper.find('.claim-btn').trigger('click')

      expect(claimSpy).not.toHaveBeenCalled()
      await wrapper.find('.confirm-claim-btn').trigger('click')
      expect(claimSpy).toHaveBeenCalledWith('vault-123', 'quest-1')
    })

    it('opens a returned quest reward dialog from the claimQuest query param', async () => {
      routeQuery.claimQuest = 'quest-1'
      await mountWithQuests([returned({ title: 'Returned Quest' })], {
        QuestRewardsModal: rewardsModal(
          '<div v-if="show" class="claim-modal" :data-quest-id="quest.id"><button @click="$emit(\'close\')">Close</button></div>'
        ),
      })

      expect(wrapper.find('.claim-modal').attributes('data-quest-id')).toBe('quest-1')
      await wrapper.find('.claim-modal button').trigger('click')
      expect(routerReplaceMock).toHaveBeenCalledWith({
        query: { quest: undefined, claimQuest: undefined },
      })
    })

    it('keeps a manually selected reward quest when the list refreshes', async () => {
      routeQuery.claimQuest = 'quest-a'
      const claimSpy = vi.spyOn(questStore, 'claimQuestRewards').mockResolvedValue()
      await mountWithQuests([returned({ id: 'quest-a' }), returned({ id: 'quest-b' })], {
        QuestCard: questCard(
          '<button class="claim-btn" :data-quest-id="quest.id" @click="$emit(\'claim\', quest.id)">Claim</button>',
          ['claim']
        ),
        QuestRewardsModal: rewardsModal(
          '<div v-if="show" class="claim-modal" :data-quest-id="quest.id"><button @click="$emit(\'confirm\')">Confirm</button></div>'
        ),
      })

      await wrapper.find('[data-quest-id="quest-b"].claim-btn').trigger('click')
      questStore.vaultQuests = [...questStore.vaultQuests]
      await flushPromises()

      expect(wrapper.find('.claim-modal').attributes('data-quest-id')).toBe('quest-b')
      routeQuery.claimQuest = undefined
      await flushPromises()
      expect(wrapper.find('.claim-modal').attributes('data-quest-id')).toBe('quest-b')
      await wrapper.find('.claim-modal button').trigger('click')
      expect(claimSpy).toHaveBeenCalledWith('vault-123', 'quest-b')
    })

    it('closes a query-opened reward dialog when Browser Back removes the query', async () => {
      routeQuery.claimQuest = 'quest-a'
      const dialog = {
        QuestCard: true,
        QuestRewardsModal: rewardsModal('<div v-if="show" class="claim-modal">Claim Rewards</div>'),
      }
      await mountWithQuests([returned({ id: 'quest-a' })], dialog)

      expect(wrapper.find('.claim-modal').exists()).toBe(true)
      routeQuery.claimQuest = undefined
      await flushPromises()
      expect(wrapper.find('.claim-modal').exists()).toBe(false)
    })

    it('opens a query-linked reward when its quest first becomes ready', async () => {
      routeQuery.claimQuest = 'quest-a'
      await mountWithQuests([travelling({ id: 'quest-a', title: 'Returning Quest' })], {
        QuestCard: true,
        QuestRewardsModal: rewardsModal('<div v-if="show" class="claim-modal">Claim Rewards</div>'),
      })

      expect(wrapper.find('.claim-modal').exists()).toBe(false)
      questStore.vaultQuests = [{ ...questStore.vaultQuests[0]!, is_reward_ready: true }]
      await flushPromises()
      expect(wrapper.find('.claim-modal').exists()).toBe(true)
    })
  })

  describe('Quest card actions', () => {
    it('starts an available state quest from its card', async () => {
      const startSpy = vi.spyOn(questStore, 'startQuest').mockResolvedValue()
      await mountWithQuests(
        [quest({ id: 'quest-9', title: 'Training Quest', quest_category: 'training' })],
        {
          QuestCard: questCard(
            '<button class="start-quest" @click="$emit(\'start\', quest.id)">Start</button>',
            ['start']
          ),
        }
      )
      await selectTab(1)
      await wrapper.find('.start-quest').trigger('click')

      expect(startSpy).toHaveBeenCalledWith('vault-123', 'quest-9')
    })
  })

  describe('Header metrics and tab badges', () => {
    it.each([
      { started_at: '2025-01-02T00:00:00Z' },
      { started_at: '2025-01-02T00:00:00Z', return_completes_at: '2099-01-01T00:00:00Z' },
      { is_reward_ready: true },
    ])(
      'keeps Active selected while a mission is active, returning or claimable: %j',
      async (state) => {
        await mountWithQuests([quest(state)])

        expect(wrapper.get('[role="tab"][data-state="active"]').text()).toContain('Active')
      }
    )

    it('switches to Available after the last reward is claimed', async () => {
      await mountWithQuests([quest({ is_reward_ready: true })])
      questStore.vaultQuests = [quest({ is_completed: true })] as never
      await flushPromises()

      expect(wrapper.get('[role="tab"][data-state="active"]').text()).toContain('Available')
    })

    it('preserves Completed selection when the last active quest disappears', async () => {
      await mountWithQuests([quest({ is_reward_ready: true })])
      await selectTab(2)
      questStore.vaultQuests = [quest({ is_completed: true })] as never
      await flushPromises()

      expect(wrapper.get('[role="tab"][data-state="active"]').text()).toContain('Completed')
    })

    it('puts claimable rewards before active quests regardless of server order', async () => {
      await mountWithQuests([
        quest({ id: 'active', started_at: '2025-01-02T00:00:00Z' }),
        quest({ id: 'ready-1', is_reward_ready: true }),
        quest({ id: 'ready-2', is_reward_ready: true }),
      ])
      await nextTick()

      expect(
        wrapper.findAllComponents({ name: 'QuestCard' }).map((card) => card.props('quest').id)
      ).toEqual(['ready-1', 'ready-2', 'active'])
    })

    it('shows Available and Rewards-ready totals in the page header', async () => {
      await mountWithQuests([
        quest({ id: 'quest-1' }),
        quest({ id: 'quest-2', is_reward_ready: true }),
      ])

      const header = wrapper.text()
      expect(header).toContain('Available quests')
      expect(header).toContain('Collect rewards')
    })

    it('badges the Active tab with the ready-to-claim count and explains it', async () => {
      await mountWithQuests([
        quest({ id: 'quest-1' }),
        quest({ id: 'quest-2', is_reward_ready: true }),
        quest({ id: 'quest-3', is_reward_ready: true }),
      ])

      const activeTab = wrapper.findAll('[role="tab"]').find((t) => t.text().includes('Active'))
      const badge = activeTab?.find('[data-slot="badge"]')
      expect(badge?.exists()).toBe(true)
      expect(badge?.text()).toContain('2')

      // reka-ui's TooltipTrigger opens on native focus (immediate, no delay);
      // the whole tab is the trigger so keyboard focus reveals the tip too.
      const tip = activeTab?.find('span[aria-label]')
      expect(tip?.attributes('aria-label')).toBe('2 rewards ready to claim')
      activeTab?.element.dispatchEvent(new FocusEvent('focus'))
      await nextTick()
      expect(document.querySelector('[role="tooltip"]')?.textContent).toContain(
        '2 rewards ready to claim'
      )
    })

    it('omits the Active tab badge when nothing is ready to claim', async () => {
      await mountWithQuests([quest({ id: 'quest-1' })])

      const activeTab = wrapper.findAll('[role="tab"]').find((t) => t.text().includes('Active'))
      expect(activeTab?.find('[data-slot="badge"]').exists()).toBe(false)
    })

    it('offers header help about quests', async () => {
      await mountWithQuests([quest({ id: 'quest-1' })])

      // PageHelp loads asynchronously, so poll instead of assuming one flush
      // settles the dynamic import.
      await vi.waitFor(() => {
        expect(wrapper.find('button[aria-label="About Quests"]').exists()).toBe(true)
      })
    })
  })
})
