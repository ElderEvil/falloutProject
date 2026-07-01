import { describe, it, expect, beforeEach, vi } from 'vitest'
import * as http from '@/core/plugins/httpClient'

vi.mock('@/core/plugins/httpClient')

import {
  startTraining,
  getDwellerTraining,
  getVaultTrainings,
  getTrainingProgress,
  cancelTraining,
  getRoomTrainings,
} from '@/modules/progression/services/trainingService'

describe('trainingService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('startTraining', () => {
    it('should POST to start training endpoint with params', async () => {
      const mockTraining = { id: 't1', dweller_id: 'd1', status: 'active', stat_being_trained: 'strength' }
      vi.mocked(http.apiPost).mockResolvedValueOnce(mockTraining)

      const result = await startTraining('d1', 'r1', 'test-token')

      expect(http.apiPost).toHaveBeenCalledWith(
        '/api/v1/training/start?dweller_id=d1&room_id=r1',
        undefined,
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockTraining)
    })
  })

  describe('getDwellerTraining', () => {
    it('should fetch dweller training', async () => {
      const mockTraining = { id: 't1', dweller_id: 'd1', status: 'active' }
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockTraining)

      const result = await getDwellerTraining('d1', 'test-token')

      expect(http.apiGet).toHaveBeenCalledWith(
        '/api/v1/training/dweller/d1',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockTraining)
    })

    it('should return null when no training exists', async () => {
      vi.mocked(http.apiGet).mockResolvedValueOnce(null)

      const result = await getDwellerTraining('d1', 'test-token')

      expect(result).toBeNull()
    })
  })

  describe('getVaultTrainings', () => {
    it('should fetch vault trainings', async () => {
      const mockTrainings = [{ id: 't1', dweller_id: 'd1' }]
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockTrainings)

      const result = await getVaultTrainings('vault-1', 'test-token')

      expect(http.apiGet).toHaveBeenCalledWith(
        '/api/v1/training/vault/vault-1',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockTrainings)
    })
  })

  describe('getTrainingProgress', () => {
    it('should fetch training progress', async () => {
      const mockProgress = { id: 't1', status: 'active', progress: 50 }
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockProgress)

      const result = await getTrainingProgress('t1', 'test-token')

      expect(http.apiGet).toHaveBeenCalledWith(
        '/api/v1/training/t1',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockProgress)
    })
  })

  describe('cancelTraining', () => {
    it('should POST to cancel training endpoint', async () => {
      const mockCancelled = { id: 't1', status: 'cancelled' }
      vi.mocked(http.apiPost).mockResolvedValueOnce(mockCancelled)

      const result = await cancelTraining('t1', 'test-token')

      expect(http.apiPost).toHaveBeenCalledWith(
        '/api/v1/training/t1/cancel',
        undefined,
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockCancelled)
    })
  })

  describe('getRoomTrainings', () => {
    it('should fetch room trainings', async () => {
      const mockTrainings = [{ id: 't1', room_id: 'r1' }]
      vi.mocked(http.apiGet).mockResolvedValueOnce(mockTrainings)

      const result = await getRoomTrainings('r1', 'test-token')

      expect(http.apiGet).toHaveBeenCalledWith(
        '/api/v1/training/room/r1',
        expect.objectContaining({
          headers: { Authorization: 'Bearer test-token' },
        })
      )
      expect(result).toEqual(mockTrainings)
    })
  })
})
