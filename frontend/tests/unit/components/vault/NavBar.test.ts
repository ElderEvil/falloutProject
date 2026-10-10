import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NavBar from '@/modules/vault/components/shell/NavBar.vue'
import PageHeaderMetric from '@/core/components/common/PageHeaderMetric.vue'
import ResourceBar from '@/modules/vault/components/shell/ResourceBar.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { useRoomStore } from '@/modules/rooms/stores/room'
import type { Room } from '@/modules/rooms/models/room'
import type { IncidentTeamMember } from '@/modules/combat/models/incident'
import { audioManager } from '@/core/audio/audioManager'
import type { User } from '@/modules/auth/types/user'

vi.mock('@/core/composables/useVersionDetection', () => ({
  useVersionDetection: () => ({
    versionBadgeVisible: { value: false },
    showChangelog: vi.fn(),
  }),
}))

// Armable one-shot failure for the lazily imported rooms module: the mock
// namespace is created once, so the getter flips per import instead of being
// cached by the module runner. The first read after arming rejects (simulating
// a chunk-load failure after a deploy); later reads return the real export.
const roomsLoadState = vi.hoisted(() => ({ failNext: false }))

vi.mock('@/modules/rooms/models/roomParts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/modules/rooms/models/roomParts')>()
  return {
    ...actual,
    get findProductionRoom() {
      if (roomsLoadState.failNext) {
        roomsLoadState.failNext = false
        throw new Error('Failed to fetch dynamically imported module')
      }
      return actual.findProductionRoom
    },
  }
})

const vaultHeader = vi.hoisted(() => ({
  vault: null as { value: { number: number } | null } | null,
  isVaultRoute: null as { value: boolean } | null,
  isReady: null as { value: boolean } | null,
  loadFailed: null as { value: boolean } | null,
  energy: null as { value: { current: number; max: number } } | null,
  food: null as { value: { current: number; max: number } } | null,
  water: null as { value: { current: number; max: number } } | null,
  resourceRates: null as { value: Record<'power' | 'food' | 'water', number> } | null,
}))
vi.mock('@/modules/vault/composables/useVaultHeaderContext', () => {
  const vault = ref<{ number: number } | null>(null)
  const isVaultRoute = ref(false)
  const isReady = ref(true)
  const loadFailed = ref(false)
  const energy = ref({ current: 50, max: 100 })
  const food = ref({ current: 60, max: 100 })
  const water = ref({ current: 70, max: 100 })
  const resourceRates = ref({ power: 1, food: 2, water: 3 })
  vaultHeader.vault = vault
  vaultHeader.isVaultRoute = isVaultRoute
  vaultHeader.isReady = isReady
  vaultHeader.loadFailed = loadFailed
  vaultHeader.energy = energy
  vaultHeader.food = food
  vaultHeader.water = water
  vaultHeader.resourceRates = resourceRates
  return {
    useVaultHeaderContext: () => ({
      vault,
      isVaultRoute,
      isReady,
      loadFailed,
      dwellersCount: ref(10),
      populationMax: ref(20),
      populationColor: ref('text-terminal-green'),
      happiness: ref(80),
      happinessColor: ref('text-terminal-green'),
      energy,
      food,
      water,
      resourceRates,
      bottleCaps: ref(500),
      dwellersTooltip: ref('10 of 20 dwellers'),
      happinessTooltip: ref('80% happiness'),
      capsTooltip: ref('500 bottle caps'),
    }),
  }
})

const testUser: User = {
  id: 'user-1',
  username: 'Overseer',
  email: 'overseer@example.com',
  is_active: true,
  is_superuser: false,
  email_verified: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('NavBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vaultHeader.vault!.value = null
    vaultHeader.isVaultRoute!.value = false
    vaultHeader.isReady!.value = true
    vaultHeader.loadFailed!.value = false
    vaultHeader.energy!.value = { current: 50, max: 100 }
    vaultHeader.food!.value = { current: 60, max: 100 }
    vaultHeader.water!.value = { current: 70, max: 100 }
    vaultHeader.resourceRates!.value = { power: 1, food: 2, water: 3 }
    audioManager.setMuted(true)
    audioManager.setVolume('ui', 0.6)
    audioManager.setVolume('sfx', 0.8)
    audioManager.setVolume('music', 0.4)
  })

  afterEach(() => {
    roomsLoadState.failNext = false
    vi.restoreAllMocks()
  })

  it('keeps the Vaults link aria-label verbatim', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: {
        plugins: [router],
        stubs: { Icon: true, NotificationBell: true },
      },
    })

    const link = wrapper.find('a[aria-label="Navigate to vaults list"]')
    expect(link.exists()).toBe(true)
    expect(link.attributes('aria-label')).toBe('Navigate to vaults list')
    expect(link.text()).toContain('Vaults')
  })

  it('shows a prominent vault number beside the list link above the sidebar', async () => {
    vaultHeader.vault!.value = { number: 42 }

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: {
        plugins: [router],
        stubs: { Icon: true, NotificationBell: true },
      },
    })

    const link = wrapper.find('a[aria-label="Navigate to vaults list"]')
    expect(link.text()).not.toContain('Vault 42')
    expect(wrapper.find('[aria-label="Vaults and current vault"]').text()).toContain('Vault 42')
  })

  it('keeps the five navbar groups in order with currency separate from account controls', async () => {
    useAuthStore().token = 'test-token'
    vaultHeader.isVaultRoute!.value = true
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: {
        plugins: [router],
        stubs: { Icon: true, NotificationBell: true },
      },
    })

    const vaults = wrapper.find('[aria-label="Vaults and current vault"]')
    const population = wrapper.find('[aria-label="Vault population"]')
    const resources = wrapper.find('[aria-label="Vault resources"]')
    const currency = wrapper.find('[aria-label="Vault currency"]')
    const account = wrapper.find('[aria-label="Account and notifications"]')
    expect(vaults.element.nextElementSibling).toBe(account.element.parentElement)
    expect(population.element.nextElementSibling).toBe(resources.element)
    expect(resources.element.nextElementSibling).toBe(currency.element)
    expect(currency.element.parentElement?.nextElementSibling).toBe(account.element)
    expect(account.classes()).toContain('ml-auto')
    expect(
      population.findAllComponents(PageHeaderMetric).map((metric) => metric.props('label'))
    ).toEqual(['Dwellers', 'Happiness'])
    expect(resources.findAllComponents(ResourceBar).map((bar) => bar.props('label'))).toEqual([
      'Power',
      'Food',
      'Water',
    ])
    expect(
      resources.findAllComponents(ResourceBar).map((bar) => bar.props('productionRate'))
    ).toEqual([1, 2, 3])
    const [bottles, caps] = currency.findAllComponents(PageHeaderMetric)
    const bell = account.find('notification-bell-stub')
    expect(bottles?.props('label')).toBe('Nuka bottles')
    expect(bottles?.props('value')).toBe('—')
    expect(caps?.props('label')).toBe('Caps')
    expect(bell.exists()).toBe(true)
    expect(currency.element.textContent).toContain('500')
  })

  it('points a critical resource warning at the production room that fixes it', async () => {
    useAuthStore().token = 'test-token'
    vaultHeader.isVaultRoute!.value = true
    vaultHeader.food!.value = { current: 15, max: 100 }
    vaultHeader.resourceRates!.value = { power: 1, food: -5, water: 3 }
    useRoomStore().rooms = [
      { id: 'garden-1', name: 'Garden', category: 'production', ability: 'agility' },
    ] as Room[]

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: { plugins: [router], stubs: { Icon: true, NotificationBell: true } },
    })

    const foodBar = wrapper
      .findAllComponents(ResourceBar)
      .find((bar) => bar.props('label') === 'Food')
    // The rooms module resolves behind a dynamic import, so the link lands one tick later.
    await vi.waitFor(() =>
      expect(foodBar?.props('criticalTo')).toBe('/vault/vault-1?roomId=garden-1')
    )
    expect(foodBar?.text()).toContain('Food empty in ~3 min')
  })

  it('retries the production rooms load after a failed dynamic import', async () => {
    useAuthStore().token = 'test-token'
    vaultHeader.isVaultRoute!.value = true
    useRoomStore().rooms = [
      { id: 'garden-1', name: 'Garden', category: 'production', ability: 'agility' },
    ] as Room[]

    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    roomsLoadState.failNext = true
    const wrapper = mount(NavBar, {
      global: { plugins: [router], stubs: { Icon: true, NotificationBell: true } },
    })

    const foodBar = () =>
      wrapper.findAllComponents(ResourceBar).find((bar) => bar.props('label') === 'Food')

    await vi.waitFor(() =>
      expect(consoleError).toHaveBeenCalledWith(
        expect.stringContaining('production room'),
        expect.any(Error)
      )
    )
    expect(foodBar()?.props('criticalTo')).toBeUndefined()

    vaultHeader.isReady!.value = false
    await nextTick()
    vaultHeader.isReady!.value = true
    await vi.waitFor(() =>
      expect(foodBar()?.props('criticalTo')).toBe('/vault/vault-1?roomId=garden-1')
    )
  })

  it('shows loading and failure states without placeholder status values', async () => {
    useAuthStore().token = 'test-token'
    vaultHeader.isVaultRoute!.value = true
    vaultHeader.isReady!.value = false
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: { plugins: [router], stubs: { Icon: true, NotificationBell: true } },
    })

    expect(wrapper.text()).toContain('Syncing vault status')
    expect(wrapper.findAllComponents(ResourceBar)).toHaveLength(0)
    expect(wrapper.text()).not.toContain('0 / 0')

    vaultHeader.loadFailed!.value = true
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Vault status unavailable')
    expect(wrapper.findAllComponents(ResourceBar)).toHaveLength(0)
  })

  it('uses a terminal-green highlight for user menu items', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = testUser

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
    })
    await router.push('/vault/vault-1')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: {
        plugins: [router],
        stubs: {
          Icon: true,
          NotificationBell: true,
        },
      },
    })

    await wrapper.find('button[aria-label="User menu for Overseer"]').trigger('click')

    const profileItem = wrapper.find('a[aria-label="View profile"]')
    expect(profileItem.classes()).toContain('hover:bg-theme-primary/10')
    expect(profileItem.classes()).toContain('focus:bg-theme-primary/15')
    expect(profileItem.classes()).not.toContain('hover:bg-gray-900')
  })

  it('marks the profile control active on the profile route', async () => {
    const authStore = useAuthStore()
    authStore.token = 'test-token'
    authStore.user = testUser

    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/profile', component: { template: '<div />' } }],
    })
    await router.push('/profile')
    await router.isReady()

    const wrapper = mount(NavBar, {
      global: { plugins: [router], stubs: { Icon: true, NotificationBell: true } },
    })

    expect(wrapper.find('button[aria-label="User menu for Overseer"]').classes()).toContain(
      'bg-theme-primary/10'
    )
  })

  describe('sound toggle', () => {
    async function mountNavBar() {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
      })
      await router.push('/vault/vault-1')
      await router.isReady()

      return mount(NavBar, {
        global: {
          plugins: [router],
          stubs: { Icon: true, NotificationBell: true },
        },
      })
    }

    it('is hidden while no incident is active', async () => {
      const wrapper = await mountNavBar()

      expect(wrapper.find('button[aria-label="Unmute sounds"]').exists()).toBe(false)
      expect(wrapper.find('button[aria-label="Mute sounds"]').exists()).toBe(false)
    })

    it('shows the unmute action while sounds are muted', async () => {
      useIncidentStore().activeIncidentIds = ['incident-1']

      const wrapper = await mountNavBar()

      expect(wrapper.find('button[aria-label="Unmute sounds"]').exists()).toBe(true)
    })

    it('mutes and unmutes without leaving the page', async () => {
      useIncidentStore().activeIncidentIds = ['incident-1']
      audioManager.setMuted(false)

      const wrapper = await mountNavBar()

      await wrapper.find('button[aria-label="Mute sounds"]').trigger('click')

      expect(audioManager.muted).toBe(true)
      expect(wrapper.find('button[aria-label="Unmute sounds"]').exists()).toBe(true)
    })
  })

  describe('responder chip', () => {
    const teamMember: IncidentTeamMember = {
      id: 'tm-1',
      team_id: 'team-1',
      dweller_id: 'dweller-1',
      slot_number: 1,
      status: 'assigned',
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    }

    async function mountNavBar() {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/vault/:id', component: { template: '<div />' } }],
      })
      await router.push('/vault/vault-1')
      await router.isReady()

      return mount(NavBar, {
        global: {
          plugins: [router],
          stubs: { Icon: true, NotificationBell: true },
        },
      })
    }

    it('is hidden while no incident is active', async () => {
      const wrapper = await mountNavBar()

      expect(wrapper.find('[aria-label*="responders on scene"]').exists()).toBe(false)
    })

    it('shows the total responder count while incidents are active', async () => {
      const store = useIncidentStore()
      store.activeIncidentIds = ['incident-1', 'incident-2']
      store.incidentTeams.set('incident-1', [teamMember])
      store.incidentTeams.set('incident-2', [
        { ...teamMember, id: 'tm-2', dweller_id: 'dweller-2' },
        { ...teamMember, id: 'tm-3', dweller_id: 'dweller-3' },
      ])

      const wrapper = await mountNavBar()

      const chip = wrapper.find('[aria-label="3 responders on scene"]')
      expect(chip.exists()).toBe(true)
      expect(chip.text()).toContain('3')
    })

    it('is informational: no glow or hover intent classes', async () => {
      useIncidentStore().activeIncidentIds = ['incident-1']

      const wrapper = await mountNavBar()

      const chip = wrapper.find('[aria-label="0 responders on scene"]')
      expect(chip.classes()).toContain('badge-info')
      expect(chip.classes()).not.toContain('badge-live')
      expect(chip.classes()).not.toContain('badge-action')
    })
  })
})
