import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, getActivePinia, setActivePinia } from 'pinia'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import VaultView from '@/modules/vault/views/VaultView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { incidentApi } from '@/modules/combat/api/incident'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useObjectivesStore } from '@/modules/progression/stores/objectives'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { craftingService } from '@/modules/crafting/services/craftingService'
import type { OverseerBriefingData } from '@/modules/vault/models/overseerBriefing'
import BuildModeButton from '@/core/components/common/BuildModeButton.vue'

enableAutoUnmount(afterEach)
afterEach(() => {
  const pinia = getActivePinia()
  if (pinia) disposePinia(pinia)
})

const vaultFixture = {
  id: 'vault-1',
  number: 101,
  bottle_caps: 1000,
  happiness: 75,
  power: 50,
  power_max: 100,
  food: 60,
  food_max: 100,
  water: 70,
  water_max: 100,
  population_max: 20,
  radio_mode: 'recruitment',
  incidents_disabled: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  room_count: 5,
  dweller_count: 10,
  stimpack: 0,
  radaway: 0,
}

// Heavy/independent panels are stubbed so the tests focus on the build control.
const stubs = {
  SidePanel: { template: '<aside data-testid="side-panel" />' },
  RoomGrid: {
    name: 'RoomGrid',
    template: '<div data-testid="room-grid" />',
    props: ['openRoomId', 'overseerBriefing', 'overseerAttentionCount'],
  },
  GameControlPanel: true,
  IncidentAlert: true,
  UnassignedDwellers: true,
  WastelandPanel: true,
}

interface ReadyActionSeed {
  quests?: unknown[]
  objectives?: unknown[]
  trainings?: unknown[]
  orders?: unknown[]
  explorationOverflow?: unknown[]
  incidentOverflow?: unknown[]
}

async function mountLoadedVault(seed: ReadyActionSeed = {}) {
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()
  const roomStore = useRoomStore()
  const { filter: dwellerStore } = useDwellerStore()
  const explorationStore = useExplorationStore()
  const incidentStore = useIncidentStore()
  const questStore = useQuestStore()
  const objectivesStore = useObjectivesStore()
  const trainingStore = useTrainingStore()

  authStore.token = 'test-token'
  vaultStore.loadedVaults['vault-1'] = vaultFixture

  // Seed the authoritative ready-action sources before the view loads.
  questStore.vaultQuests = (seed.quests ?? []) as never
  objectivesStore.objectives = (seed.objectives ?? []) as never
  for (const [index, training] of (seed.trainings ?? []).entries()) {
    trainingStore.activeTrainings.set(`training-${index}`, training as never)
  }

  vi.spyOn(vaultStore, 'fetchVaults').mockResolvedValue(true)
  vi.spyOn(vaultStore, 'revalidateVault').mockResolvedValue()
  vi.spyOn(vaultStore, 'fetchGameState').mockResolvedValue()
  vi.spyOn(vaultStore, 'startResourcePolling').mockImplementation(() => {})
  vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
  vi.spyOn(roomStore, 'fetchBuildableRooms').mockResolvedValue()
  vi.spyOn(roomStore, 'deselectRoom').mockImplementation(() => {})
  vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue()
  vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue()
  vi.spyOn(incidentStore, 'startPolling').mockImplementation(() => {})
  vi.spyOn(questStore, 'fetchVaultQuests').mockResolvedValue()
  vi.spyOn(objectivesStore, 'fetchObjectives').mockResolvedValue()
  vi.spyOn(trainingStore, 'fetchVaultTrainings').mockResolvedValue()
  vi.spyOn(craftingService, 'listOrders').mockResolvedValue((seed.orders ?? []) as never)
  vi.spyOn(explorationStore, 'fetchPendingOverflow').mockResolvedValue(
    (seed.explorationOverflow ?? []) as never
  )
  vi.spyOn(incidentApi, 'getPendingIncidentOverflow').mockResolvedValue(
    (seed.incidentOverflow ?? []) as never
  )

  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/vault/:id?', component: VaultView },
    ],
  })
  await router.push('/vault/vault-1')
  await router.isReady()

  const wrapper = mount(VaultView, {
    global: { plugins: [router], stubs },
  })
  await flushPromises()

  return { wrapper, roomStore }
}

const buildDialog = (wrapper: ReturnType<typeof mount>) =>
  wrapper.find('[role="dialog"][aria-label="Room menu"]')

describe('VaultView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps a completed incident report reachable until the player dismisses it', async () => {
    const incidentStore = useIncidentStore()
    useRoomStore().rooms = [{ id: 'room-1', vault_id: 'vault-1' }] as never
    incidentStore.aftermaths.set('room-1', {
      incidentId: 'incident-1',
      roomId: 'room-1',
      type: 'fire',
      roomName: 'Generator',
      outcome: 'victory',
      capsEarned: 10,
      experienceEarned: 5,
      loot: null,
      unclaimed: [],
      enemiesDefeated: 0,
      damageDealt: 0,
      rounds: 1,
    } as never)
    const { wrapper } = await mountLoadedVault()
    const report = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Review incident report'))
    expect(report).toBeDefined()
    await report!.trigger('click')
    expect(wrapper.findComponent({ name: 'RoomGrid' }).props('openRoomId')).toBe('room-1')
    incidentStore.clearAftermath('room-1')
    await flushPromises()
    expect(wrapper.text()).not.toContain('Review incident report')
    wrapper.unmount()
  })

  it('renders the vault loading error state with a way back', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/vault/:id?', component: VaultView },
      ],
    })
    await router.push('/vault/test-vault')
    await router.isReady()

    const wrapper = mount(VaultView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('h2').text()).toContain('Error Loading Vault')
    expect(wrapper.text()).toContain('Go to Vault List')
  })

  it('surfaces ready actions in urgency order with authoritative routes', async () => {
    const { wrapper } = await mountLoadedVault({
      quests: [
        {
          id: 'quest-1',
          is_visible: true,
          is_completed: false,
          is_reward_ready: true,
          started_at: null,
        },
      ],
      objectives: [
        { id: 'objective-1', is_completed: false, progress: 1, total: 1, category: 'daily' },
      ],
      trainings: [
        {
          dweller_id: 'dweller-1',
          estimated_completion_at: new Date(Date.now() - 1000).toISOString(),
          status: 'active',
        },
      ],
      orders: [{ id: 'order-1', room_id: 'room-craft', status: 'completed' }],
      explorationOverflow: [
        { exploration_id: 'exploration-1', dweller_id: 'dweller-2', unclaimed_loot: [] },
      ],
      incidentOverflow: [
        { incident_id: 'incident-1', room_id: 'room-incident', type: 'fire', unclaimed_loot: [] },
      ],
    })

    const grid = wrapper.findComponent({ name: 'RoomGrid' })
    const briefing = grid.props('overseerBriefing') as OverseerBriefingData

    expect(briefing.readyActions).toEqual([
      {
        kind: 'incident_aftermath',
        label: 'INCIDENT LOOT AWAITS DECISION',
        route: '/vault/vault-1?roomId=room-incident',
        count: 1,
      },
      {
        kind: 'exploration_outcome',
        label: 'EXPEDITION LOOT WAITING',
        route: '/vault/vault-1/exploration',
        count: 1,
      },
      {
        kind: 'quest_claim',
        label: 'QUEST REWARD READY',
        route: '/vault/vault-1/quests?claimQuest=quest-1',
        count: 1,
      },
      {
        kind: 'objective_claim',
        label: 'OBJECTIVE REWARD READY',
        route: '/vault/vault-1/objectives',
        count: 1,
      },
      {
        kind: 'crafting_collect',
        label: 'CRAFTING ORDER READY',
        route: '/vault/vault-1?roomId=room-craft',
        count: 1,
      },
      {
        kind: 'training_complete',
        label: 'TRAINING COMPLETE',
        route: '/vault/vault-1/dwellers/dweller-1?tab=stats',
        count: 1,
      },
    ])
    expect(grid.props('overseerAttentionCount')).toBe(0)
  })

  describe('Build control', () => {
    it('renders the build control in the room grid container', async () => {
      const { wrapper } = await mountLoadedVault()

      const grid = wrapper.find('[data-testid="room-grid"]')
      const buildButton = wrapper.findComponent(BuildModeButton)
      const buildControl = wrapper.find('.build-control')

      expect(grid.exists()).toBe(true)
      expect(buildButton.exists()).toBe(true)
      expect(buildButton.isVisible()).toBe(true)
      expect(buildControl.element.parentElement).toBe(grid.element.parentElement)
      expect(
        buildButton.element.compareDocumentPosition(grid.element) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy()
    })

    it('enters build mode from the control and cancels again', async () => {
      const { wrapper, roomStore } = await mountLoadedVault()

      await wrapper.findComponent(BuildModeButton).find('button').trigger('click')
      await flushPromises()

      expect(roomStore.fetchBuildableRooms).toHaveBeenCalledWith('vault-1')
      expect(buildDialog(wrapper).exists()).toBe(true)
      expect(wrapper.findComponent(BuildModeButton).text()).toContain('Cancel Building')

      await wrapper.findComponent(BuildModeButton).find('button').trigger('click')
      await flushPromises()

      expect(roomStore.deselectRoom).toHaveBeenCalled()
      expect(buildDialog(wrapper).exists()).toBe(false)
      expect(wrapper.findComponent(BuildModeButton).text()).toContain('Build')
    })

    it('keeps the B and Escape keyboard shortcuts working', async () => {
      const { wrapper, roomStore } = await mountLoadedVault()

      window.dispatchEvent(new KeyboardEvent('keydown', { code: 'KeyB' }))
      await flushPromises()

      expect(roomStore.fetchBuildableRooms).toHaveBeenCalled()
      expect(buildDialog(wrapper).exists()).toBe(true)

      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      await flushPromises()

      expect(roomStore.deselectRoom).toHaveBeenCalled()
      expect(buildDialog(wrapper).exists()).toBe(false)
    })
  })
})
