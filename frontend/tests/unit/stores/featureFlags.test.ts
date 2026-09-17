import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useFeatureFlagsStore } from '@/modules/dwellers/stores/featureFlags'
import { getFeatureFlags } from '@/modules/dwellers/services/dwellerService'

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))

vi.mock('@/modules/dwellers/services/dwellerService', () => ({
  getFeatureFlags: vi.fn(),
}))

describe('Feature flags store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shares one request between concurrent callers', async () => {
    vi.mocked(getFeatureFlags).mockResolvedValue({ race_mechanics: true, faction_mechanics: true })
    const store = useFeatureFlagsStore()

    // The filter panel and the roster mount together; both must see the resolved flags.
    await Promise.all([store.fetchFlags(), store.fetchFlags()])

    expect(getFeatureFlags).toHaveBeenCalledTimes(1)
    expect(store.factionMechanics).toBe(true)
  })

  it('retries a failed fetch instead of caching the failure', async () => {
    vi.mocked(getFeatureFlags).mockRejectedValueOnce(new Error('offline'))
    const store = useFeatureFlagsStore()

    await store.fetchFlags()
    expect(store.loaded).toBe(false)

    vi.mocked(getFeatureFlags).mockResolvedValue({ race_mechanics: true, faction_mechanics: true })
    await store.fetchFlags()
    expect(store.factionMechanics).toBe(true)
  })
})
