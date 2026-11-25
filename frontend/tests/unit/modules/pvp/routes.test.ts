import { beforeEach, describe, expect, it } from 'vite-plus/test'
import { createPinia, setActivePinia } from 'pinia'
import { pvpRoutes } from '@/modules/pvp/routes'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'

describe('pvpRoutes', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('allows the route only when duels are enabled', async () => {
    const flags = useFeatureFlagsStore()
    flags.loaded = true
    const to = { params: { id: 'vault-1' } }
    const beforeEnter = pvpRoutes[0]!.beforeEnter as (to: typeof to) => Promise<unknown>

    flags.pvpDuels = false
    expect(await beforeEnter(to)).toEqual({ name: 'vault', params: { id: 'vault-1' } })
    flags.pvpDuels = true
    expect(await beforeEnter(to)).toBe(true)
  })
})
