import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useFeatureFlagsStore } from '@/core/stores/featureFlags'
import { apiGet } from '@/core/utils/api'

vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
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
    vi.mocked(apiGet).mockResolvedValue({
      race_mechanics: true,
      faction_mechanics: true,
      world_events: false,
      pvp_duels: false,
      combat_zone: false,
    })
    const store = useFeatureFlagsStore()

    // The filter panel and the roster mount together; both must see the resolved flags.
    await Promise.all([store.fetchFlags(), store.fetchFlags()])
    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(store.factionMechanics).toBe(true)
  })

  it('retries a failed fetch instead of caching the failure', async () => {
    vi.mocked(apiGet).mockRejectedValueOnce(new Error('offline'))
    const store = useFeatureFlagsStore()

    await store.fetchFlags()
    expect(store.loaded).toBe(false)
    vi.mocked(apiGet).mockResolvedValue({
      race_mechanics: true,
      faction_mechanics: true,
      world_events: false,
      pvp_duels: false,
      combat_zone: false,
    })
    await store.fetchFlags()
    expect(store.factionMechanics).toBe(true)
  })
})
