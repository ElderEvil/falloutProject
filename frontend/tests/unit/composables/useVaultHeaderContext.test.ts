import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import {
  useVaultHeaderContext,
  type VaultHeaderContext,
} from '@/modules/vault/composables/useVaultHeaderContext'
import { useVaultStore, type VaultWithNumbers } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'

const fakeVault = {
  id: 'vault-1',
  number: 1,
  bottle_caps: 500,
  happiness: 80,
  power: 90,
  power_max: 100,
  food: 80,
  food_max: 100,
  water: 70,
  water_max: 100,
  population_max: 20,
  radio_mode: 'recruitment',
  incidents_disabled: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  room_count: 5,
  dweller_count: 15,
  stimpack: 3,
  radaway: 2,
} satisfies VaultWithNumbers

const Harness = defineComponent({
  setup() {
    const ctx = useVaultHeaderContext()
    return { ctx }
  },
  template: '<div />',
})

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div />' } },
      { path: '/vault/:id', name: 'vault', component: { template: '<div />' } },
      { path: '/login', name: 'login', component: { template: '<div />' } },
      { path: '/profile', name: 'profile', component: { template: '<div />' } },
      { path: '/dweller/:id/chat', name: 'DwellerChatPage', component: { template: '<div />' } },
    ],
  })
}

async function mountContext(router: Router, path: string) {
  await router.push(path)
  await router.isReady()
  const wrapper = mount(Harness, { global: { plugins: [router] } })
  await flushPromises()
  const ctx = (wrapper.vm as unknown as { ctx: VaultHeaderContext }).ctx
  return { wrapper, ctx }
}

describe('useVaultHeaderContext', () => {
  let router: Router
  let vaultStore: ReturnType<typeof useVaultStore>
  let ensureSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'mock-token'
    vaultStore = useVaultStore()
    ensureSpy = vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)
    router = makeRouter()
  })

  it('hydrates the vault for the current route exactly once', async () => {
    const { ctx } = await mountContext(router, '/vault/vault-1')

    expect(ensureSpy).toHaveBeenCalledTimes(1)
    expect(ensureSpy).toHaveBeenCalledWith('vault-1', 'mock-token')
    expect(ctx.isVaultRoute.value).toBe(true)
    expect(ctx.vaultId.value).toBe('vault-1')
    expect(ctx.isReady.value).toBe(false)
  })

  it('re-hydrates with the new id on a route change and never shows a stale vault', async () => {
    vaultStore.loadedVaults['vault-1'] = fakeVault
    const { ctx } = await mountContext(router, '/vault/vault-1')

    expect(ctx.isReady.value).toBe(true)
    expect(ctx.vault.value?.id).toBe('vault-1')
    expect(ctx.dwellersCount.value).toBe(15)

    await router.push('/vault/vault-2')
    await flushPromises()

    expect(ensureSpy).toHaveBeenCalledTimes(2)
    expect(ensureSpy).toHaveBeenLastCalledWith('vault-2', 'mock-token')
    // The route decides what the strip shows: vault-1 must not leak through.
    expect(ctx.vaultId.value).toBe('vault-2')
    expect(ctx.vault.value).toBeNull()
    expect(ctx.isReady.value).toBe(false)
  })

  it.each(['/login', '/profile', '/'])(
    'makes no request on the non-vault route %s',
    async (path) => {
      const { ctx } = await mountContext(router, path)

      expect(ensureSpy).not.toHaveBeenCalled()
      expect(ctx.isVaultRoute.value).toBe(false)
      expect(ctx.vaultId.value).toBeNull()
    }
  )

  it('makes no request on the dweller chat route (DwellerChatPage)', async () => {
    const { ctx } = await mountContext(router, '/dweller/dweller-1/chat')

    expect(ensureSpy).not.toHaveBeenCalled()
    expect(ctx.isVaultRoute.value).toBe(false)
    expect(ctx.vaultId.value).toBeNull()
  })

  it('makes no request when the auth token is empty', async () => {
    useAuthStore().token = null
    const { ctx } = await mountContext(router, '/vault/vault-1')

    expect(ensureSpy).not.toHaveBeenCalled()
    expect(ctx.isReady.value).toBe(false)
  })

  it('keeps isReady false and the numbers at zero until the vault has loaded', async () => {
    const { ctx } = await mountContext(router, '/vault/vault-1')

    expect(ctx.isReady.value).toBe(false)
    expect(ctx.dwellersCount.value).toBe(0)
    expect(ctx.populationMax.value).toBe(0)
    expect(ctx.populationUtilization.value).toBe(0)
    expect(ctx.happiness.value).toBe(0)
    expect(ctx.bottleCaps.value).toBe(0)
    expect(ctx.energy.value).toEqual({ current: 0, max: 100 })
    expect(ctx.food.value).toEqual({ current: 0, max: 100 })
    expect(ctx.water.value).toEqual({ current: 0, max: 100 })
    expect(ctx.resourceRates.value).toBeUndefined()
  })

  it('flags loadFailed when hydration rejects without rethrowing', async () => {
    ensureSpy.mockRejectedValueOnce(new Error('boom'))
    const { ctx } = await mountContext(router, '/vault/vault-1')

    expect(ctx.loadFailed.value).toBe(true)
    expect(ctx.isReady.value).toBe(false)
  })

  it('ignores a late failure from the previous vault route', async () => {
    let rejectOldLoad!: (reason: Error) => void
    ensureSpy.mockImplementationOnce(
      () => new Promise((_, reject) => { rejectOldLoad = reject })
    )
    const { ctx } = await mountContext(router, '/vault/vault-1')

    await router.push('/vault/vault-2')
    await flushPromises()
    vaultStore.loadedVaults['vault-2'] = { ...fakeVault, id: 'vault-2' }
    rejectOldLoad(new Error('old vault failed'))
    await flushPromises()

    expect(ctx.isReady.value).toBe(true)
    expect(ctx.loadFailed.value).toBe(false)
  })
})
