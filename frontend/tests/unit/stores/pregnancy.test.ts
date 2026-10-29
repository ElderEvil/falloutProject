import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePregnancyStore } from '@/modules/social/stores/pregnancy'
import { pregnancyApi } from '@/modules/social/api/pregnancy'
import type { Pregnancy } from '@/modules/social/models/pregnancy'

const { notifyErrorOnce, toastSuccess } = vi.hoisted(() => ({
  notifyErrorOnce: vi.fn(),
  toastSuccess: vi.fn(),
}))

vi.mock('@/core/utils/errorHandler', () => ({ notifyErrorOnce }))
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: toastSuccess }),
}))
vi.mock('@/modules/social/api/pregnancy', () => ({
  pregnancyApi: { getByVault: vi.fn(), get: vi.fn(), deliver: vi.fn() },
}))

const makePregnancy = (): Pregnancy => ({
  id: 'preg-1',
  mother_id: 'mother-1',
  father_id: 'father-1',
  conceived_at: '2026-01-01T00:00:00Z',
  due_at: '2026-01-02T00:00:00Z',
  status: 'pregnant',
  progress_percentage: 40,
  time_remaining_seconds: 600,
  is_due: false,
})

describe('Pregnancy Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('loads a vault pregnancy list and clears loading', async () => {
    vi.mocked(pregnancyApi.getByVault).mockResolvedValue([makePregnancy()])

    const store = usePregnancyStore()
    await store.fetchVaultPregnancies('vault-1')

    expect(pregnancyApi.getByVault).toHaveBeenCalledWith('vault-1')
    expect(store.pregnancies).toEqual([makePregnancy()])
    expect(store.isLoading).toBe(false)
  })

  it('notifies and rethrows a failed list load', async () => {
    vi.mocked(pregnancyApi.getByVault).mockRejectedValue(new Error('Network error'))

    const store = usePregnancyStore()
    await expect(store.fetchVaultPregnancies('vault-1')).rejects.toThrow('Network error')

    expect(notifyErrorOnce).toHaveBeenCalled()
    expect(store.isLoading).toBe(false)
  })

  it('returns null when a single pregnancy cannot be loaded', async () => {
    vi.mocked(pregnancyApi.get).mockRejectedValue(new Error('Missing'))

    const store = usePregnancyStore()

    await expect(store.getPregnancy('preg-1')).resolves.toBeNull()
    expect(notifyErrorOnce).toHaveBeenCalled()
  })

  it('marks a delivered pregnancy and announces it', async () => {
    vi.mocked(pregnancyApi.deliver).mockResolvedValue({
      pregnancy_id: 'preg-1',
      children: [],
      message: 'A child is born',
    })

    const store = usePregnancyStore()
    store.pregnancies = [makePregnancy()]
    const result = await store.deliverBaby('preg-1')

    expect(pregnancyApi.deliver).toHaveBeenCalledWith('preg-1')
    expect(result?.message).toBe('A child is born')
    expect(store.pregnancies[0].status).toBe('delivered')
    expect(toastSuccess).toHaveBeenCalledWith('A child is born')
    expect(store.isLoading).toBe(false)
  })

  it('returns null when delivery fails', async () => {
    vi.mocked(pregnancyApi.deliver).mockRejectedValue(new Error('Too early'))

    const store = usePregnancyStore()
    store.pregnancies = [makePregnancy()]

    await expect(store.deliverBaby('preg-1')).resolves.toBeNull()
    expect(store.pregnancies[0].status).toBe('pregnant')
    expect(notifyErrorOnce).toHaveBeenCalled()
  })
})
