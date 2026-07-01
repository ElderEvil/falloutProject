import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { usePregnancyStore } from '@/modules/social/stores/pregnancy'
import * as http from '@/core/plugins/httpClient'

vi.mock('@/core/plugins/httpClient')

describe('Pregnancy Store', () => {
  let mockPregnancy: {
    id: string
    mother_id: string
    father_id: string
    conceived_at: string
    due_at: string
    status: 'pregnant' | 'delivered' | 'miscarried'
    progress_percentage: number
    time_remaining_seconds: number
    is_due: boolean
    created_at?: string
    updated_at?: string
  }
  let mockDeliveryResult: {
    pregnancy_id: string
    child_id: string
    message: string
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()

    mockPregnancy = {
      id: 'preg-1',
      mother_id: 'dweller-1',
      father_id: 'dweller-2',
      conceived_at: '2026-01-01T00:00:00Z',
      due_at: '2026-01-04T00:00:00Z',
      status: 'pregnant' as const,
      progress_percentage: 25,
      time_remaining_seconds: 259200,
      is_due: false,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
    }

    mockDeliveryResult = {
      pregnancy_id: 'preg-1',
      child_id: 'child-1',
      message: 'Baby delivered successfully!',
    }
  })

  describe('State Initialization', () => {
    it('should initialize with empty pregnancies', () => {
      const store = usePregnancyStore()
      expect(store.pregnancies).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })

  describe('fetchVaultPregnancies', () => {
    it('should fetch pregnancies successfully', async () => {
      vi.mocked(http.apiGet).mockResolvedValueOnce([mockPregnancy])

      const store = usePregnancyStore()
      await store.fetchVaultPregnancies('vault-1')

      expect(http.apiGet).toHaveBeenCalledWith('/api/v1/pregnancies/vault/vault-1')
      expect(store.pregnancies).toEqual([mockPregnancy])
      expect(store.isLoading).toBe(false)
    })

    it('should handle fetch error', async () => {
      vi.mocked(http.apiGet).mockRejectedValueOnce(new Error('Network error'))

      const store = usePregnancyStore()
      await expect(store.fetchVaultPregnancies('vault-1')).rejects.toThrow('Network error')

      expect(store.pregnancies).toEqual([])
      expect(store.isLoading).toBe(false)
    })
  })

  describe('getPregnancy', () => {
    it('should fetch single pregnancy successfully', async () => {
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockPregnancy)

      const store = usePregnancyStore()
      const result = await store.getPregnancy('preg-1')

      expect(http.apiGet).toHaveBeenCalledWith('/api/v1/pregnancies/preg-1')
      expect(result).toEqual(mockPregnancy)
    })

    it('should handle fetch error', async () => {
      vi.mocked(http.apiGet).mockRejectedValueOnce(new Error('Not found'))

      const store = usePregnancyStore()
      const result = await store.getPregnancy('preg-1')

      expect(result).toBeNull()
    })
  })

  describe('deliverBaby', () => {
    it('should deliver baby successfully', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(mockDeliveryResult)

      const store = usePregnancyStore()
      store.pregnancies = [mockPregnancy]

      const result = await store.deliverBaby('preg-1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/pregnancies/preg-1/deliver')
      expect(result).toEqual(mockDeliveryResult)
      expect(store.pregnancies[0].status).toBe('delivered')
    })

    it('should handle delivery error', async () => {
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Delivery failed'))

      const store = usePregnancyStore()
      const result = await store.deliverBaby('preg-1')

      expect(result).toBeNull()
    })
  })

  describe('forceConception', () => {
    it('should force conception successfully', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(mockPregnancy)

      const store = usePregnancyStore()
      const result = await store.forceConception('dweller-1', 'dweller-2')

      expect(http.apiPost).toHaveBeenCalledWith(
        '/api/v1/pregnancies/debug/force-conception?mother_id=dweller-1&father_id=dweller-2'
      )
      expect(result).toEqual(mockPregnancy)
      expect(store.pregnancies).toContainEqual(mockPregnancy)
    })

    it('should handle force conception error', async () => {
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Failed'))

      const store = usePregnancyStore()
      const result = await store.forceConception('dweller-1', 'dweller-2')

      expect(result).toBeNull()
    })
  })

  describe('acceleratePregnancy', () => {
    it('should accelerate pregnancy successfully', async () => {
      vi.mocked(http.apiPost).mockResolvedValueOnce(undefined)

      const store = usePregnancyStore()
      store.pregnancies = [mockPregnancy]

      const result = await store.acceleratePregnancy('preg-1')

      expect(http.apiPost).toHaveBeenCalledWith('/api/v1/pregnancies/preg-1/debug/accelerate')
      expect(result).toBe(true)
      expect(store.pregnancies[0].is_due).toBe(true)
    })

    it('should handle acceleration error', async () => {
      vi.mocked(http.apiPost).mockRejectedValueOnce(new Error('Failed'))

      const store = usePregnancyStore()
      const result = await store.acceleratePregnancy('preg-1')

      expect(result).toBe(false)
    })
  })

  describe('formatTimeRemaining', () => {
    it('should format seconds into human readable string', () => {
      const store = usePregnancyStore()

      expect(store.formatTimeRemaining(3600)).toBe('1h 0m')
      expect(store.formatTimeRemaining(3661)).toBe('1h 1m')
      expect(store.formatTimeRemaining(61)).toBe('1m 1s')
      expect(store.formatTimeRemaining(30)).toBe('30s')
      expect(store.formatTimeRemaining(0)).toBe('0s')
    })
  })

  describe('Computed Properties', () => {
    it('should get active pregnancies', () => {
      const store = usePregnancyStore()
      store.pregnancies = [
        mockPregnancy,
        { ...mockPregnancy, id: 'preg-2', status: 'delivered' as const },
        { ...mockPregnancy, id: 'preg-3', status: 'miscarried' as const },
      ]

      const active = store.activePregnancies
      expect(active).toHaveLength(1)
      expect(active[0].id).toBe('preg-1')
    })

    it('should get due pregnancies', () => {
      const store = usePregnancyStore()
      store.pregnancies = [
        mockPregnancy,
        { ...mockPregnancy, id: 'preg-2', is_due: true },
        { ...mockPregnancy, id: 'preg-3', is_due: false },
      ]

      const due = store.duePregnancies
      expect(due).toHaveLength(1)
      expect(due[0].id).toBe('preg-2')
    })

    it('should get pregnancy by mother', () => {
      const store = usePregnancyStore()
      store.pregnancies = [mockPregnancy]

      const found = store.getPregnancyByMother('dweller-1')
      expect(found).toEqual(mockPregnancy)

      const notFound = store.getPregnancyByMother('non-existent')
      expect(notFound).toBeUndefined()
    })

    it('should not return delivered pregnancy for getPregnancyByMother', () => {
      const store = usePregnancyStore()
      store.pregnancies = [
        { ...mockPregnancy, status: 'delivered' as const },
      ]

      const result = store.getPregnancyByMother('dweller-1')
      expect(result).toBeUndefined()
    })
  })

  describe('clearPregnancies', () => {
    it('should clear all pregnancies', () => {
      const store = usePregnancyStore()
      store.pregnancies = [mockPregnancy]

      store.clearPregnancies()
      expect(store.pregnancies).toEqual([])
    })
  })
})
