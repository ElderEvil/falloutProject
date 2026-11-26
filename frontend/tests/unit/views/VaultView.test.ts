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
    props: ['openRoomId'],
  },
  GameControlPanel: true,
  RadioNewsWidget: true,
  RaidBanner: {
    name: 'RaidBanner',
    template: '<div data-testid="raid-banner" />',
    props: ['vaultId'],
  },
  IncidentAlert: true,
  UnassignedDwellers: true,
  WastelandPanel: true,
}

const buildDialog = (wrapper: ReturnType<typeof mount>) =>
  wrapper.find('[role="dialog"][aria-label="Room menu"]')

/** Stub every store read the overview fires on entry. */
function seedStoreReads() {
  const vaultStore = useVaultStore()
  const roomStore = useRoomStore()
  const { filter: dwellerStore } = useDwellerStore()

  useAuthStore().token = 'test-token'
  vaultStore.loadedVaults['vault-1'] = vaultFixture as never

  vi.spyOn(vaultStore, 'fetchVaults').mockResolvedValue(true)
  vi.spyOn(vaultStore, 'revalidateVault').mockResolvedValue()
  vi.spyOn(vaultStore, 'fetchGameState').mockResolvedValue()
  vi.spyOn(vaultStore, 'startResourcePolling').mockImplementation(() => {})
  vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue('loaded')
  vi.spyOn(roomStore, 'fetchBuildableRooms').mockResolvedValue()
  vi.spyOn(roomStore, 'deselectRoom').mockImplementation(() => {})
  vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue()
  vi.spyOn(dwellerStore, 'fetchAllDwellers').mockResolvedValue()
  vi.spyOn(useExplorationStore(), 'fetchExplorationsByVault').mockResolvedValue()
  vi.spyOn(useIncidentStore(), 'startPolling').mockImplementation(() => {})

  return { vaultStore, roomStore, filter: dwellerStore }
}

async function createVaultRouter(path = '/vault/vault-1') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/vault/:id?', component: VaultView },
    ],
  })
  await router.push(path)
  await router.isReady()
  return router
}

const mountVault = (router: Awaited<ReturnType<typeof createVaultRouter>>) =>
  mount(VaultView, { global: { plugins: [router], stubs } })

async function mountLoadedVault() {
  const stores = seedStoreReads()
  const router = await createVaultRouter()
  const wrapper = mountVault(router)
  await flushPromises()
  return { wrapper, router, ...stores }
}

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

  it('loads the unfiltered vault roster on overview entry', async () => {
    const { filter } = await mountLoadedVault()

    expect(filter.fetchAllDwellers).toHaveBeenCalledWith('vault-1')
  })

  it('renders the raid entry banner for the loaded vault', async () => {
    const { wrapper } = await mountLoadedVault()

    const banner = wrapper.find('[data-testid="raid-banner"]')
    expect(banner.exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'RaidBanner' }).props('vaultId')).toBe('vault-1')
  })

  it('drops a superseded vault load before it reads the old vault', async () => {
    const { vaultStore, roomStore } = seedStoreReads()
    vaultStore.loadedVaults['vault-2'] = { ...vaultFixture, id: 'vault-2' } as never

    let resolveStale!: () => void
    let resolveCurrent!: () => void
    vi.spyOn(vaultStore, 'revalidateVault').mockImplementation((id) =>
      id === 'vault-1'
        ? new Promise<void>((resolve) => {
            resolveStale = resolve
          })
        : new Promise<void>((resolve) => {
            resolveCurrent = resolve
          })
    )

    const router = await createVaultRouter()
    mountVault(router)
    await flushPromises()

    await router.push('/vault/vault-2')
    await flushPromises()
    resolveCurrent()
    await flushPromises()
    expect(roomStore.fetchRooms).toHaveBeenCalledTimes(1)
    expect(roomStore.fetchRooms).toHaveBeenCalledWith('vault-2')

    resolveStale()
    await flushPromises()
    expect(roomStore.fetchRooms).toHaveBeenCalledTimes(1)
  })

  it('renders the vault loading error state with a way back', async () => {
    const router = await createVaultRouter('/vault/test-vault')
    const wrapper = mount(VaultView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('h2').text()).toContain('Error Loading Vault')
    expect(wrapper.text()).toContain('Go to Vault List')
  })

  describe('Build control', () => {
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
