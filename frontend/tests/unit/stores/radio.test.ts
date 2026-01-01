import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRadioStore } from '@/stores/radio'
import axios from '@/plugins/axios'

vi.mock('@/plugins/axios')

describe('Radio Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockRadioStats = {
    has_radio: true,
    recruitment_rate: 0.05,
    rate_per_hour: 3.0,
    estimated_hours_per_recruit: 0.33,
    radio_rooms_count: 1,
    manual_cost_caps: 500,
    radio_mode: 'recruitment',
    speedup_multipliers: [
      { room_id: 'room-1', speedup: 1.0 }
    ]
  }

  const mockRecruitmentResponse = {
    dweller: {
      id: 'dweller-1',
      first_name: 'John',
      last_name: 'Doe',
      vault_id: 'vault-1',
      gender: 'male',
      level: 1
    },
    message: 'John Doe has joined your vault!',
    caps_spent: 500
  }

  describe('State Initialization', () => {
    it('should initialize with null radio stats', () => {
      const store = useRadioStore()
      expect(store.radioStats).toBeNull()
      expect(store.isLoading).toBe(false)
      expect(store.isRecruiting).toBe(false)
    })
  })

  describe('fetchRadioStats', () => {
    it('should fetch radio stats successfully', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockRadioStats })

      const store = useRadioStore()
      await store.fetchRadioStats('vault-1')

      expect(axios.get).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/stats')
      expect(store.radioStats).toEqual(mockRadioStats)
      expect(store.isLoading).toBe(false)
    })

    it('should handle fetch error', async () => {
      vi.mocked(axios.get).mockRejectedValueOnce(new Error('Network error'))

      const store = useRadioStore()
      await store.fetchRadioStats('vault-1')

      expect(store.radioStats).toBeNull()
      expect(store.isLoading).toBe(false)
    })
  })

  describe('manualRecruit', () => {
    it('should recruit dweller successfully', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockRecruitmentResponse })

      const store = useRadioStore()
      const result = await store.manualRecruit('vault-1')

      expect(axios.post).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/recruit', {})
      expect(result).toEqual(mockRecruitmentResponse)
      expect(store.isRecruiting).toBe(false)
    })

    it('should handle recruitment error', async () => {
      vi.mocked(axios.post).mockRejectedValueOnce({
        response: { data: { detail: 'Insufficient caps' } }
      })

      const store = useRadioStore()
      const result = await store.manualRecruit('vault-1')

      expect(result).toBeNull()
      expect(store.isRecruiting).toBe(false)
    })

    it('should pass override parameters', async () => {
      vi.mocked(axios.post).mockResolvedValueOnce({ data: mockRecruitmentResponse })

      const store = useRadioStore()
      const override = { override: { first_name: 'Custom' } }
      await store.manualRecruit('vault-1', override)

      expect(axios.post).toHaveBeenCalledWith('/api/v1/radio/vault/vault-1/recruit', override)
    })
  })

  describe('setRadioMode', () => {
    it('should set radio mode successfully', async () => {
      vi.mocked(axios.put).mockResolvedValueOnce({
        data: { message: 'Radio mode set to happiness', radio_mode: 'happiness' }
      })
      vi.mocked(axios.get).mockResolvedValueOnce({
        data: { ...mockRadioStats, radio_mode: 'happiness' }
      })

      const store = useRadioStore()
      const result = await store.setRadioMode('vault-1', 'happiness')

      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/radio/vault/vault-1/mode',
        null,
        { params: { mode: 'happiness' } }
      )
      expect(result).toBe(true)
    })

    it('should handle mode change error', async () => {
      vi.mocked(axios.put).mockRejectedValueOnce(new Error('Failed'))

      const store = useRadioStore()
      const result = await store.setRadioMode('vault-1', 'happiness')

      expect(result).toBe(false)
    })
  })

  describe('setRadioSpeedup', () => {
    it('should set speedup successfully', async () => {
      vi.mocked(axios.put).mockResolvedValueOnce({
        data: { message: 'Speedup set', room_id: 'room-1', speedup: 5.0 }
      })
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockRadioStats })

      const store = useRadioStore()
      const result = await store.setRadioSpeedup('vault-1', 'room-1', 5.0)

      expect(axios.put).toHaveBeenCalledWith(
        '/api/v1/radio/vault/vault-1/room/room-1/speedup',
        null,
        { params: { speedup: 5.0 } }
      )
      expect(result).toBe(true)
    })

    it('should handle speedup error', async () => {
      vi.mocked(axios.put).mockRejectedValueOnce({
        response: { data: { detail: 'Speedup must be between 1.0 and 10.0' } }
      })

      const store = useRadioStore()
      const result = await store.setRadioSpeedup('vault-1', 'room-1', 15.0)

      expect(result).toBe(false)
    })
  })

  describe('formatRecruitmentRate', () => {
    it('should format rate for no radio', () => {
      const store = useRadioStore()
      const formatted = store.formatRecruitmentRate(null)
      expect(formatted).toBe('No radio room')
    })

    it('should format rate for radio without recruitment', () => {
      const store = useRadioStore()
      const stats = { ...mockRadioStats, estimated_hours_per_recruit: 0 }
      const formatted = store.formatRecruitmentRate(stats)
      expect(formatted).toBe('No recruitment possible')
    })

    it('should format rate in minutes', () => {
      const store = useRadioStore()
      const stats = { ...mockRadioStats, estimated_hours_per_recruit: 0.5 }
      const formatted = store.formatRecruitmentRate(stats)
      expect(formatted).toBe('~30 min per recruit')
    })

    it('should format rate in hours', () => {
      const store = useRadioStore()
      const stats = { ...mockRadioStats, estimated_hours_per_recruit: 2.5 }
      const formatted = store.formatRecruitmentRate(stats)
      expect(formatted).toBe('~2.5 hours per recruit')
    })

    it('should format rate in days', () => {
      const store = useRadioStore()
      const stats = { ...mockRadioStats, estimated_hours_per_recruit: 48 }
      const formatted = store.formatRecruitmentRate(stats)
      expect(formatted).toBe('~2.0 days per recruit')
    })
  })

  describe('clearRadioStats', () => {
    it('should clear radio stats', async () => {
      vi.mocked(axios.get).mockResolvedValueOnce({ data: mockRadioStats })

      const store = useRadioStore()
      await store.fetchRadioStats('vault-1')
      expect(store.radioStats).not.toBeNull()

      store.clearRadioStats()
      expect(store.radioStats).toBeNull()
    })
  })
})
