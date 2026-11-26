import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { setActivePinia, createPinia } from 'pinia'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { getErrorMessage } from '@/core/types/utils'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { createToastMock } from '../helpers/mocks'

const toast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => toast }))

vi.mock('@/core/plugins/axios')
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
  setContinuousTraining: vi.fn(),
  setTrainingGoal: vi.fn(),
}))

import * as trainingService from '@/modules/progression/services/trainingService'
import type { components } from '@/core/types/api.generated'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

const HOUR = 3_600_000

/** A training row; only fields a test cares about need naming. */
const training = (overrides: Record<string, unknown> = {}) =>
  ({
    id: 't1',
    dweller_id: 'd1',
    room_id: 'r1',
    status: 'active',
    stat_being_trained: 'strength',
    estimated_completion_at: new Date(Date.now() + HOUR).toISOString(),
    ...overrides,
  }) as TrainingRead & TrainingProgress

const lateTraining = () => training({ id: 'old', room_id: 'room-a' })

describe('Training Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('keeps the latest vault response when an older request finishes last', async () => {
    const { promise, resolve } = Promise.withResolvers<TrainingRead[]>()
    vi.mocked(trainingService.getVaultTrainings)
      .mockReturnValueOnce(promise)
      .mockResolvedValueOnce([training({ id: 'current' })])
    const store = useTrainingStore()
    const pending = store.fetchVaultTrainings('vault-a')
    await store.fetchVaultTrainings('vault-b')
    resolve([training({ id: 'old' })])
    await pending
    expect([...store.activeTrainings.keys()]).toEqual(['current'])
  })

  it.each(['clear', 'session'] as const)(
    'rejects a pending vault response after %s invalidation',
    async (change) => {
      const { promise, resolve } = Promise.withResolvers<TrainingRead[]>()
      vi.mocked(trainingService.getVaultTrainings).mockReturnValueOnce(promise)
      const auth = useAuthStore()
      const store = useTrainingStore()
      const pending = store.fetchVaultTrainings('vault-a')
      if (change === 'session') auth.sessionGeneration++
      else store.clearTrainings()
      resolve([training({ id: 'old' })])
      await pending
      expect(store.activeTrainings.size).toBe(0)
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    }
  )

  describe('late responses after a context clear', () => {
    const vaultActions = {
      start: () => trainingService.startTraining,
      cancel: () => trainingService.cancelTraining,
      complete: () => trainingService.completeTraining,
      dweller: () => trainingService.getDwellerTraining,
      progress: () => trainingService.getTrainingProgress,
      room: () => trainingService.getRoomTrainings,
    } as const

    const invokers = {
      start: (store: ReturnType<typeof useTrainingStore>) =>
        store.startTraining('dweller', 'room-a'),
      cancel: (store: ReturnType<typeof useTrainingStore>) => store.cancelTraining('old'),
      complete: (store: ReturnType<typeof useTrainingStore>) => store.completeTraining('old'),
      dweller: (store: ReturnType<typeof useTrainingStore>) =>
        store.fetchDwellerTraining('dweller'),
      room: (store: ReturnType<typeof useTrainingStore>) => store.fetchRoomTrainings('room-a'),
      progress: (store: ReturnType<typeof useTrainingStore>) => store.updateTrainingProgress('old'),
    } as const

    it.each(
      (['start', 'cancel', 'complete', 'dweller', 'room', 'progress'] as const).flatMap((action) =>
        (['resolve', 'reject'] as const).map((outcome) => [action, outcome] as const)
      )
    )('%s ignores a late %s after context clear', async (action, outcome) => {
      const pendingResponse = Promise.withResolvers<TrainingRead & TrainingProgress>()
      vi.mocked(vaultActions[action]()).mockReturnValueOnce(pendingResponse.promise)
      const store = useTrainingStore()

      const pending = invokers[action](store)
      store.clearTrainings()
      if (outcome === 'reject') pendingResponse.reject(new Error('Old failure'))
      else if (action === 'room') pendingResponse.resolve([lateTraining()] as never)
      else pendingResponse.resolve(lateTraining())
      await pending

      expect(store.activeTrainings.size).toBe(0)
      expect(store.trainingHistory).toEqual([])
      expect(store.error).toBeNull()
      expect(toast.error).not.toHaveBeenCalled()
      expect(toast.success).not.toHaveBeenCalled()
    })

    it.each([
      ['goal', () => trainingService.setTrainingGoal],
      ['continuous', () => trainingService.setContinuousTraining],
    ] as const)('%s ignores a late response after clear', async (action, service) => {
      const pendingResponse = Promise.withResolvers<TrainingRead>()
      vi.mocked(service()).mockReturnValueOnce(pendingResponse.promise)
      const store = useTrainingStore()
      const pending =
        action === 'goal'
          ? store.setTrainingGoal('old', 7)
          : store.setContinuousTraining('vault-a', true)
      store.clearTrainings()
      pendingResponse.resolve(lateTraining())

      expect(await pending).toBe(false)
      expect(toast.error).not.toHaveBeenCalled()
      expect(toast.success).not.toHaveBeenCalled()
    })
  })

  it('saves only the selected dweller goal and keeps the saved value on failure', async () => {
    useAuthStore().token = 'token'
    const store = useTrainingStore()
    store.activeTrainings.set('t1', training({ goal_stat_value: 10 }))
    store.activeTrainings.set('t2', training({ id: 't2', goal_stat_value: 10 }))
    vi.mocked(trainingService.setTrainingGoal).mockResolvedValueOnce(
      training({ goal_stat_value: 7 }) as never
    )

    expect(await store.setTrainingGoal('t1', 7)).toBe(true)
    expect(store.activeTrainings.get('t1')?.goal_stat_value).toBe(7)
    expect(store.activeTrainings.get('t2')?.goal_stat_value).toBe(10)
    vi.mocked(trainingService.setTrainingGoal).mockRejectedValueOnce(new Error('Save failed'))
    expect(await store.setTrainingGoal('t1', 8)).toBe(false)
    expect(store.activeTrainings.get('t1')?.goal_stat_value).toBe(7)
    expect(store.savingGoals.size).toBe(0)
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

  describe('continuous training', () => {
    it('keeps the saved preference after a failed change', async () => {
      useAuthStore().token = 'token'
      const vaultStore = useVaultStore()
      vaultStore.loadedVaults['v1'] = { id: 'v1', continuous_training: true } as never
      vi.mocked(trainingService.setContinuousTraining).mockRejectedValueOnce(
        new Error('Save failed')
      )

      const store = useTrainingStore()
      expect(await store.setContinuousTraining('v1', false)).toBe(false)
      expect(vaultStore.loadedVaults['v1'].continuous_training).toBe(true)
      expect(store.isSettingContinuousTraining).toBe(false)
    })

    it('ignores duplicate changes and results from an old login', async () => {
      const auth = useAuthStore()
      auth.token = 'token'
      const vaultStore = useVaultStore()
      vaultStore.loadedVaults['v1'] = { id: 'v1', continuous_training: false } as never
      const response = Promise.withResolvers<unknown>()
      vi.mocked(trainingService.setContinuousTraining).mockReturnValueOnce(
        response.promise as never
      )

      const store = useTrainingStore()
      const pending = store.setContinuousTraining('v1', true)
      expect(store.isSettingContinuousTraining).toBe(true)
      expect(await store.setContinuousTraining('v1', true)).toBe(false)
      expect(trainingService.setContinuousTraining).toHaveBeenCalledTimes(1)
      auth.sessionGeneration += 1
      response.resolve({ continuous_training: true })
      expect(await pending).toBe(false)
      expect(vaultStore.loadedVaults['v1'].continuous_training).toBe(false)
    })
  })

  describe('fetchVaultTrainings', () => {
    it('should fetch vault trainings and populate activeTrainings', async () => {
      const mockTrainings = [
        training({ id: 't1' }),
        training({ id: 't2', dweller_id: 'd2', room_id: 'r2', stat_being_trained: 'endurance' }),
      ]
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce(mockTrainings)

      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1')
      expect(trainingService.getVaultTrainings).toHaveBeenCalledWith('vault-1')
      expect(store.activeTrainings.size).toBe(2)
      expect(store.activeTrainings.get('t1')).toEqual(mockTrainings[0])
      expect(store.isLoading).toBe(false)
    })

    it('should handle errors gracefully', async () => {
      vi.mocked(trainingService.getVaultTrainings).mockRejectedValueOnce(new Error('Network error'))
      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1')
      expect(store.isLoading).toBe(false)
      expect(store.error).toBeTruthy()
    })

    it('should skip trainings with status other than active', async () => {
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce([
        training({ id: 't1', status: 'completed' }),
        training({ id: 't2', status: 'cancelled' }),
      ])

      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1')
      expect(store.activeTrainings.size).toBe(0)
    })
  })

  describe('startTraining', () => {
    it('should start training and add to activeTrainings', async () => {
      const mockTraining = training()
      vi.mocked(trainingService.startTraining).mockResolvedValueOnce(mockTraining)

      const store = useTrainingStore()
      const result = await store.startTraining('d1', 'r1')
      expect(trainingService.startTraining).toHaveBeenCalledWith('d1', 'r1')
      expect(result).toEqual(mockTraining)
      expect(store.activeTrainings.get('t1')).toEqual(mockTraining)

      vi.mocked(trainingService.startTraining).mockRejectedValueOnce(new Error('API error'))
      expect(await store.startTraining('d1', 'r1')).toBeNull()
      expect(getErrorMessage).toHaveBeenCalled()
    })
  })

  describe('cancelTraining', () => {
    it('should cancel training and move to history', async () => {
      const mockCancelled = training({ status: 'cancelled' })
      vi.mocked(trainingService.cancelTraining).mockResolvedValueOnce(mockCancelled)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', training())
      expect(await store.cancelTraining('t1')).toBe(true)
      expect(trainingService.cancelTraining).toHaveBeenCalledWith('t1')
      expect(store.activeTrainings.has('t1')).toBe(false)
      expect(store.trainingHistory).toContainEqual(mockCancelled)

      vi.mocked(trainingService.cancelTraining).mockRejectedValueOnce(new Error('API error'))
      expect(await store.cancelTraining('t1')).toBe(false)
    })
  })

  describe('completeTraining', () => {
    it('should complete training and move to history', async () => {
      const mockCompleted = training({ status: 'completed', progress: 1.0, completed_at: null })
      vi.mocked(trainingService.completeTraining).mockResolvedValueOnce(mockCompleted)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', training({ progress: 0.5, completed_at: undefined }))
      expect(await store.completeTraining('t1')).toBe(true)
      expect(trainingService.completeTraining).toHaveBeenCalledWith('t1')
      expect(store.activeTrainings.has('t1')).toBe(false)
      expect(store.trainingHistory).toContainEqual(mockCompleted)

      vi.mocked(trainingService.completeTraining).mockRejectedValueOnce(new Error('API error'))
      expect(await store.completeTraining('t1')).toBe(false)
    })
  })

  describe('fetchDwellerTraining', () => {
    it('adds an active dweller training to the map and drops a completed one', async () => {
      const mockTraining = training()
      vi.mocked(trainingService.getDwellerTraining).mockResolvedValueOnce(mockTraining)
      const store = useTrainingStore()
      await store.fetchDwellerTraining('d1')
      expect(store.activeTrainings.get('t1')).toEqual(mockTraining)

      vi.mocked(trainingService.getDwellerTraining).mockResolvedValueOnce(
        training({ status: 'completed' })
      )
      await store.fetchDwellerTraining('d1')
      expect(store.activeTrainings.has('t1')).toBe(false)
    })
  })

  describe('fetchRoomTrainings', () => {
    it('should fetch room trainings and replace only that room', async () => {
      const mockTrainings = [training({ stat_being_trained: 'agility' })]
      vi.mocked(trainingService.getRoomTrainings).mockResolvedValueOnce(mockTrainings)

      const store = useTrainingStore()
      store.activeTrainings.set('previous-round', training({ id: 'previous-round', room_id: 'r1' }))
      store.activeTrainings.set('other-room', training({ id: 'other-room', room_id: 'r2' }))
      const result = await store.fetchRoomTrainings('r1')
      expect(trainingService.getRoomTrainings).toHaveBeenCalledWith('r1')
      expect(result).toEqual(mockTrainings)
      expect(store.activeTrainings.get('t1')).toEqual(mockTrainings[0])
      expect(store.activeTrainings.has('previous-round')).toBe(false)
      expect(store.activeTrainings.has('other-room')).toBe(true)
    })

    it('should return empty array on error', async () => {
      vi.mocked(trainingService.getRoomTrainings).mockRejectedValueOnce(new Error('Error'))
      const store = useTrainingStore()
      expect(await store.fetchRoomTrainings('r1')).toEqual([])
    })
  })

  describe('updateTrainingProgress', () => {
    it('should update active training in map', async () => {
      const mockProgress = training({ progress: 50 })
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockProgress)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', training())
      await store.updateTrainingProgress('t1')
      expect(store.activeTrainings.get('t1')).toEqual(mockProgress)
    })

    it('should move completed training to history', async () => {
      const mockCompleted = training({ status: 'completed', progress: 100 })
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockCompleted)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', training())
      await store.updateTrainingProgress('t1')
      expect(store.activeTrainings.has('t1')).toBe(false)
      expect(store.trainingHistory).toContainEqual(mockCompleted)
    })

    it('should remove cancelled training', async () => {
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(
        training({ status: 'cancelled' })
      )

      const store = useTrainingStore()
      store.activeTrainings.set('t1', training())
      await store.updateTrainingProgress('t1')
      expect(store.activeTrainings.has('t1')).toBe(false)
    })
  })

  describe('Getters', () => {
    it('allActiveTrainings returns array from map', () => {
      const store = useTrainingStore()
      const row = training()
      store.activeTrainings.set('t1', row)
      expect(store.allActiveTrainings).toEqual([row])
    })

    it('getTrainingByDweller returns training for dweller', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', training({ stat_being_trained: 'agility' }))
      expect(store.getTrainingByDweller('d1')).toBeTruthy()
      expect(store.getTrainingByDweller('nonexistent')).toBeUndefined()
    })

    it('getTrainingsByRoom returns trainings for room', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', training({ stat_being_trained: 'agility' }))
      store.activeTrainings.set('t2', training({ id: 't2', dweller_id: 'd2' }))
      store.activeTrainings.set(
        't3',
        training({ id: 't3', dweller_id: 'd3', room_id: 'r2', stat_being_trained: 'perception' })
      )

      expect(store.getTrainingsByRoom('r1')).toHaveLength(2)
    })

    it('isDwellerTraining returns true for active training', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', training())
      expect(store.isDwellerTraining('d1')).toBe(true)
      expect(store.isDwellerTraining('nonexistent')).toBe(false)
    })

    it('completingSoon filters trainings ending within 10 minutes', () => {
      const store = useTrainingStore()
      const soon = new Date(Date.now() + 300000).toISOString()
      const later = new Date(Date.now() + 86400000).toISOString()
      store.activeTrainings.set('t1', training({ estimated_completion_at: soon }))
      store.activeTrainings.set(
        't2',
        training({ id: 't2', dweller_id: 'd2', room_id: 'r2', estimated_completion_at: later })
      )

      expect(store.completingSoon.map((row) => row.id)).toEqual(['t1'])
    })

    it('completingSoon excludes non-active trainings', () => {
      const store = useTrainingStore()
      store.activeTrainings.set(
        't1',
        training({
          status: 'completed',
          estimated_completion_at: new Date(Date.now() + 300000).toISOString(),
        })
      )

      expect(store.completingSoon).toHaveLength(0)
    })
  })

  describe('refreshAllTrainings', () => {
    it('should call fetchVaultTrainings', async () => {
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce([])
      const store = useTrainingStore()
      await store.refreshAllTrainings('vault-1')
      expect(trainingService.getVaultTrainings).toHaveBeenCalledWith('vault-1')
    })
  })

  describe('clearTrainings', () => {
    it('should reset all state', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', training())
      store.trainingHistory.push(training({ id: 'old' }))
      store.error = 'some error'

      store.clearTrainings()
      expect(store.activeTrainings.size).toBe(0)
      expect(store.trainingHistory).toEqual([])
      expect(store.error).toBeNull()
    })
  })
})
