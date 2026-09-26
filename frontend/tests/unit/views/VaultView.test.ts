import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import VaultView from '@/modules/vault/views/VaultView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import BuildModeButton from '@/core/components/common/BuildModeButton.vue'

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
  RoomGrid: { template: '<div data-testid="room-grid" />' },
  ResourceBar: true,
  GameControlPanel: true,
  IncidentAlert: true,
  UnassignedDwellers: true,
  WastelandPanel: true,
  Tooltip: true,
  TooltipContent: true,
  TooltipProvider: true,
  TooltipTrigger: true,
}

async function mountLoadedVault() {
  const authStore = useAuthStore()
  const vaultStore = useVaultStore()
  const roomStore = useRoomStore()
  const { filter: dwellerStore } = useDwellerStore()
  const explorationStore = useExplorationStore()
  const incidentStore = useIncidentStore()

  authStore.token = 'test-token'
  vaultStore.loadedVaults['vault-1'] = vaultFixture

  vi.spyOn(vaultStore, 'fetchVaults').mockResolvedValue(true)
  vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue()
  vi.spyOn(vaultStore, 'fetchGameState').mockResolvedValue()
  vi.spyOn(vaultStore, 'startResourcePolling').mockImplementation(() => {})
  vi.spyOn(roomStore, 'fetchRooms').mockResolvedValue()
  vi.spyOn(roomStore, 'fetchBuildableRooms').mockResolvedValue()
  vi.spyOn(roomStore, 'deselectRoom').mockImplementation(() => {})
  vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue()
  vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue()
  vi.spyOn(incidentStore, 'startPolling').mockImplementation(() => {})

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

  describe('Build control', () => {
    it('renders the build control below the room grid so it never covers rooms', async () => {
      const { wrapper } = await mountLoadedVault()

      const grid = wrapper.find('[data-testid="room-grid"]')
      const buildButton = wrapper.findComponent(BuildModeButton)

      expect(grid.exists()).toBe(true)
      expect(buildButton.exists()).toBe(true)
      expect(buildButton.isVisible()).toBe(true)
      // In-flow sibling rendered after the grid (bottom placement), not overlaid on it.
      expect(
        grid.element.compareDocumentPosition(buildButton.element) &
          Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy()
    })

    it('enters build mode from the control and cancels again', async () => {
      const { wrapper, roomStore } = await mountLoadedVault()

      await wrapper.findComponent(BuildModeButton).find('button').trigger('click')
      await flushPromises()

      expect(roomStore.fetchBuildableRooms).toHaveBeenCalledWith('test-token', 'vault-1')
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
