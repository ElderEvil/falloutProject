import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { apiGet } from '@/core/utils/api'

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))

vi.mock('@/core/utils/api', () => ({
  apiGet: vi.fn(),
}))

describe('Feature flags store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shares one request between concurrent callers', async () => {
    vi.mocked(apiGet).mockResolvedValue({ race_mechanics: true, faction_mechanics: true })
    const store = useFeatureFlagsStore()

    // The filter panel and the roster mount together; both must see the resolved flags.
    await Promise.all([store.fetchFlags(), store.fetchFlags()])

    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(store.factionMechanics).toBe(true)
  })

  it('defaults player connections off when the backend omits the flag', async () => {
    vi.mocked(apiGet).mockResolvedValue({ race_mechanics: true, faction_mechanics: true })
    const store = useFeatureFlagsStore()

    await store.fetchFlags()

    expect(store.playerConnections).toBe(false)
  })

  it('turns player connections on when the backend ships the flag', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      race_mechanics: true,
      faction_mechanics: true,
      player_connections: true,
    })
    const store = useFeatureFlagsStore()

    await store.fetchFlags()

    expect(store.playerConnections).toBe(true)
  })

  it('retries a failed fetch instead of caching the failure', async () => {
    vi.mocked(apiGet).mockRejectedValueOnce(new Error('offline'))
    const store = useFeatureFlagsStore()

    await store.fetchFlags()
    expect(store.loaded).toBe(false)

    vi.mocked(apiGet).mockResolvedValue({ race_mechanics: true, faction_mechanics: true })
    await store.fetchFlags()
    expect(store.factionMechanics).toBe(true)
  })
})
