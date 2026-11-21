import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { getFeatureFlags } from '@/modules/dwellers/services/dwellerService'
import { worldEventRoutes } from '@/modules/world-event/routes'

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn(),
}))

const stub = { template: '<div />' }

function buildRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/vault/:id', name: 'vault', component: stub, meta: { requiresAuth: true } },
      ...worldEventRoutes,
    ],
  })
}

describe('world event route', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('declares requiresAuth and the vault parent', () => {
    const resolved = buildRouter().resolve('/vault/abc/world-event')
    expect(resolved.name).toBe('world-event')
    expect(resolved.meta.requiresAuth).toBe(true)
    expect(resolved.meta.parentRoute).toBe('/vault/:id')
  })

  it('redirects to the vault when the flag is off', async () => {
    vi.mocked(getFeatureFlags).mockResolvedValue({
      race_mechanics: true,
      faction_mechanics: false,
      world_events: false,
    })
    const router = buildRouter()

    await router.push('/vault/abc/world-event')

    expect(router.currentRoute.value.name).toBe('vault')
    expect(router.currentRoute.value.params.id).toBe('abc')
  })

  it('enters the view when the flag is on', async () => {
    vi.mocked(getFeatureFlags).mockResolvedValue({
      race_mechanics: true,
      faction_mechanics: false,
      world_events: true,
    })
    const router = buildRouter()

    await router.push('/vault/abc/world-event')

    expect(router.currentRoute.value.name).toBe('world-event')
  })
})
