import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { handleStoreError } from '@/core/utils/errorHandler'
import { worldEventService } from '@/modules/world-event/services/worldEventService'
import { ALREADY_CLAIMED, useWorldEventStore } from '@/modules/world-event/stores/worldEvent'

vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError: vi.fn(),
}))

vi.mock('@/modules/world-event/services/worldEventService', () => ({
  worldEventService: { getEvent: vi.fn(), claim: vi.fn() },
}))

const state = {
  event_id: 'e1',
  title: 'Signal Boost',
  target_amount: 1000,
  progress_amount: 900,
  participant_count: 4,
  contribution: 250,
  personal_min: 100,
  can_claim: true,
}

describe('world event store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('claim success closes the claim and records the paid contribution', async () => {
    vi.mocked(worldEventService.getEvent).mockResolvedValue(state)
    vi.mocked(worldEventService.claim).mockResolvedValue({
      event_id: 'e1',
      claimed: true,
      contribution: 250,
      rewards: [],
    })
    const store = useWorldEventStore()
    await store.load('v1')

    expect(await store.claim('v1')).toBe(true)
    expect(store.claimed).toBe(true)
    expect(store.event?.can_claim).toBe(false)
  })

  it('surfaces a friendly message on 409 without throwing', async () => {
    vi.mocked(worldEventService.claim).mockRejectedValue(
      Object.assign(new Error('Conflict'), { status: 409 })
    )
    const store = useWorldEventStore()

    await expect(store.claim('v1')).resolves.toBe(false)
    expect(store.claimError).toBe(ALREADY_CLAIMED)
    expect(handleStoreError).not.toHaveBeenCalled()
  })

  it('keeps a failed background poll silent', async () => {
    vi.mocked(worldEventService.getEvent).mockRejectedValue(new Error('offline'))
    const store = useWorldEventStore()

    await expect(store.load('v1', { silent: true })).resolves.toBeUndefined()
    expect(handleStoreError).not.toHaveBeenCalled()
  })
})
