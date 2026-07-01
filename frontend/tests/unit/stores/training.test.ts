import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { getErrorMessage } from '@/core/types/utils'

vi.mock('@/core/types/utils', () => ({
  getErrorMessage: vi.fn((e) => (e as Error).message || 'Unknown error'),
}))
vi.mock('@/modules/progression/services/trainingService', () => ({
  startTraining: vi.fn(),
  cancelTraining: vi.fn(),
  completeTraining: vi.fn(),
  getDwellerTraining: vi.fn(),
  getVaultTrainings: vi.fn(),
  getRoomTrainings: vi.fn(),
  getTrainingProgress: vi.fn(),
}))

import * as trainingService from '@/modules/progression/services/trainingService'

describe('Training Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  describe('State', () => {
    it('should initialize with empty state', () => {
      const store = useTrainingStore()

      expect(store.activeTrainings.size).toBe(0)
      expect(store.trainingHistory).toEqual([])
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeNull()
    })
  })

  describe('fetchVaultTrainings', () => {
    it('should fetch vault trainings and populate activeTrainings', async () => {
      const mockTrainings = [
        { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date(Date.now() + 3600000).toISOString() },
        { id: 't2', dweller_id: 'd2', room_id: 'r2', status: 'active', stat_being_trained: 'endurance', estimated_completion_at: new Date(Date.now() + 7200000).toISOString() },
      ]
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce(mockTrainings)

      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1', 'test-token')

      expect(trainingService.getVaultTrainings).toHaveBeenCalledWith('vault-1', 'test-token')
      expect(store.activeTrainings.size).toBe(2)
      expect(store.activeTrainings.get('t1')).toEqual(mockTrainings[0])
      expect(store.isLoading).toBe(false)
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(trainingService.getVaultTrainings).mockRejectedValueOnce(new Error('Network error'))

      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1', 'test-token')

      expect(store.isLoading).toBe(false)
      expect(store.error).toBeTruthy()
      expect(console.error).toHaveBeenCalled()
    })

    it('should skip trainings with status other than active', async () => {
      const mockTrainings = [
        { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'completed', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() },
        { id: 't2', dweller_id: 'd2', room_id: 'r2', status: 'cancelled', stat_being_trained: 'endurance', estimated_completion_at: new Date().toISOString() },
      ]
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce(mockTrainings)

      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1', 'test-token')

      expect(store.activeTrainings.size).toBe(0)
    })
  })

  describe('startTraining', () => {
    it('should start training and add to activeTrainings', async () => {
      const mockTraining = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date(Date.now() + 3600000).toISOString() }
      vi.mocked(trainingService.startTraining).mockResolvedValueOnce(mockTraining)

      const store = useTrainingStore()
      const result = await store.startTraining('d1', 'r1', 'test-token')

      expect(trainingService.startTraining).toHaveBeenCalledWith('d1', 'r1', 'test-token')
      expect(result).toEqual(mockTraining)
      expect(store.activeTrainings.get('t1')).toEqual(mockTraining)
    })

    it('should return null on error', async () => {
      vi.mocked(trainingService.startTraining).mockRejectedValueOnce(new Error('API error'))

      const store = useTrainingStore()
      const result = await store.startTraining('d1', 'r1', 'test-token')

      expect(result).toBeNull()
      expect(getErrorMessage).toHaveBeenCalled()
    })
  })

  describe('cancelTraining', () => {
    it('should cancel training and move to history', async () => {
      const mockCancelled = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'cancelled', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() }
      vi.mocked(trainingService.cancelTraining).mockResolvedValueOnce(mockCancelled)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', { ...mockCancelled, status: 'active' })

      const result = await store.cancelTraining('t1', 'test-token')

      expect(trainingService.cancelTraining).toHaveBeenCalledWith('t1', 'test-token')
      expect(result).toBe(true)
       expect(store.activeTrainings.has('t1')).toBe(false)
       expect(store.trainingHistory).toContainEqual(mockCancelled)
     })

     it('should return false on error', async () => {
       vi.mocked(trainingService.cancelTraining).mockRejectedValueOnce(new Error('API error'))

       const store = useTrainingStore()
       const result = await store.cancelTraining('t1', 'test-token')

       expect(result).toBe(false)
     })
   })

   describe('completeTraining', () => {
     it('should complete training and move to history', async () => {
       const mockCompleted = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'completed', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString(), progress: 1.0, completed_at: new Date().toISOString() }
       vi.mocked(trainingService.completeTraining).mockResolvedValueOnce(mockCompleted)

       const store = useTrainingStore()
       store.activeTrainings.set('t1', { ...mockCompleted, status: 'active', progress: 0.5, completed_at: undefined })

       const result = await store.completeTraining('t1', 'test-token')

       expect(trainingService.completeTraining).toHaveBeenCalledWith('t1', 'test-token')
       expect(result).toBe(true)
       expect(store.activeTrainings.has('t1')).toBe(false)
       expect(store.trainingHistory).toContainEqual(mockCompleted)
     })

     it('should return false on error', async () => {
       vi.mocked(trainingService.completeTraining).mockRejectedValueOnce(new Error('API error'))

       const store = useTrainingStore()
       const result = await store.completeTraining('t1', 'test-token')

       expect(result).toBe(false)
     })
   })

   describe('fetchDwellerTraining', () => {
     it('should add active training to map', async () => {
       const mockTraining = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date(Date.now() + 3600000).toISOString() }
       vi.mocked(trainingService.getDwellerTraining).mockResolvedValueOnce(mockTraining)

       const store = useTrainingStore()
       await store.fetchDwellerTraining('d1', 'test-token')

       expect(store.activeTrainings.get('t1')).toEqual(mockTraining)
     })

     it('should remove completed training from map', async () => {
       const mockTraining = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'completed', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() }
       vi.mocked(trainingService.getDwellerTraining).mockResolvedValueOnce(mockTraining)

       const store = useTrainingStore()
       store.activeTrainings.set('t1', { ...mockTraining, status: 'active' })

       await store.fetchDwellerTraining('d1', 'test-token')

       expect(store.activeTrainings.has('t1')).toBe(false)
     })
   })

   describe('fetchRoomTrainings', () => {
     it('should fetch room trainings and update map', async () => {
       const mockTrainings = [
         { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'agility', estimated_completion_at: new Date(Date.now() + 3600000).toISOString() },
       ]
       vi.mocked(trainingService.getRoomTrainings).mockResolvedValueOnce(mockTrainings)

       const store = useTrainingStore()
       const result = await store.fetchRoomTrainings('r1', 'test-token')

       expect(trainingService.getRoomTrainings).toHaveBeenCalledWith('r1', 'test-token')
       expect(result).toEqual(mockTrainings)
       expect(store.activeTrainings.get('t1')).toEqual(mockTrainings[0])
     })

     it('should return empty array on error', async () => {
       vi.mocked(trainingService.getRoomTrainings).mockRejectedValueOnce(new Error('Error'))

       const store = useTrainingStore()
       const result = await store.fetchRoomTrainings('r1', 'test-token')

       expect(result).toEqual([])
     })
   })

   describe('updateTrainingProgress', () => {
     it('should update active training in map', async () => {
       const mockProgress = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date(Date.now() + 3600000).toISOString(), progress: 50 }
       vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockProgress)

       const store = useTrainingStore()
       store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date(Date.now() + 3600000).toISOString() })

       await store.updateTrainingProgress('t1', 'test-token')

       expect(store.activeTrainings.get('t1')).toEqual(mockProgress)
     })

     it('should move completed training to history', async () => {
       const mockCompleted = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'completed', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString(), progress: 100 }
       vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockCompleted)

       const store = useTrainingStore()
       store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() })

       await store.updateTrainingProgress('t1', 'test-token')

       expect(store.activeTrainings.has('t1')).toBe(false)
       expect(store.trainingHistory).toContainEqual(mockCompleted)
    })

    it('should remove cancelled training', async () => {
      const mockCancelled = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'cancelled', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() }
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockCancelled)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', { ...mockCancelled, status: 'active' } as any)

      await store.updateTrainingProgress('t1', 'test-token')

      expect(store.activeTrainings.has('t1')).toBe(false)
    })
  })

  describe('Getters', () => {
    it('allActiveTrainings returns array from map', () => {
      const store = useTrainingStore()
      const training = { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() }
      store.activeTrainings.set('t1', training)

      expect(store.allActiveTrainings).toHaveLength(1)
      expect(store.allActiveTrainings[0]).toEqual(training)
    })

    it('getTrainingByDweller returns training for dweller', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'agility', estimated_completion_at: new Date().toISOString() })

      expect(store.getTrainingByDweller('d1')).toBeTruthy()
      expect(store.getTrainingByDweller('nonexistent')).toBeUndefined()
    })

    it('getTrainingsByRoom returns trainings for room', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'agility', estimated_completion_at: new Date().toISOString() })
      store.activeTrainings.set('t2', { id: 't2', dweller_id: 'd2', room_id: 'r1', status: 'active', stat_being_trained: 'luck', estimated_completion_at: new Date().toISOString() })
      store.activeTrainings.set('t3', { id: 't3', dweller_id: 'd3', room_id: 'r2', status: 'active', stat_being_trained: 'perception', estimated_completion_at: new Date().toISOString() })

      const roomTrainings = store.getTrainingsByRoom('r1')
      expect(roomTrainings).toHaveLength(2)
    })

    it('isDwellerTraining returns true for active training', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: new Date().toISOString() })

      expect(store.isDwellerTraining('d1')).toBe(true)
      expect(store.isDwellerTraining('nonexistent')).toBe(false)
    })

    it('completingSoon filters trainings ending within 10 minutes', () => {
      const store = useTrainingStore()
      const soon = new Date(Date.now() + 300000).toISOString()
      const later = new Date(Date.now() + 86400000).toISOString()
      store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'active', stat_being_trained: 'strength', estimated_completion_at: soon })
      store.activeTrainings.set('t2', { id: 't2', dweller_id: 'd2', room_id: 'r2', status: 'active', stat_being_trained: 'endurance', estimated_completion_at: later })

      expect(store.completingSoon).toHaveLength(1)
      expect(store.completingSoon[0].id).toBe('t1')
    })

    it('completingSoon excludes non-active trainings', () => {
      const store = useTrainingStore()
      const soon = new Date(Date.now() + 300000).toISOString()
      store.activeTrainings.set('t1', { id: 't1', dweller_id: 'd1', room_id: 'r1', status: 'completed', stat_being_trained: 'strength', estimated_completion_at: soon })

      expect(store.completingSoon).toHaveLength(0)
    })
  })

  describe('refreshAllTrainings', () => {
    it('should call fetchVaultTrainings', async () => {
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce([])

      const store = useTrainingStore()
      await store.refreshAllTrainings('vault-1', 'test-token')

      expect(trainingService.getVaultTrainings).toHaveBeenCalledWith('vault-1', 'test-token')
    })
  })

  describe('clearTrainings', () => {
    it('should reset all state', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', { id: 't1' } as any)
      store.trainingHistory.push({ id: 'old' } as any)
      store.error = 'some error'

      store.clearTrainings()

      expect(store.activeTrainings.size).toBe(0)
      expect(store.trainingHistory).toEqual([])
      expect(store.error).toBeNull()
    })
  })
})
