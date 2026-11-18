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

describe('Training Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('keeps the latest vault response when an older request finishes last', async () => {
    const { promise, resolve } = Promise.withResolvers<TrainingRead[]>()
    const oldTraining = { id: 'old', status: 'active' } as TrainingRead
    const current = { id: 'current', status: 'active' } as TrainingRead
    vi.mocked(trainingService.getVaultTrainings)
      .mockReturnValueOnce(promise)
      .mockResolvedValueOnce([current])
    const store = useTrainingStore()
    const pending = store.fetchVaultTrainings('vault-a')
    await store.fetchVaultTrainings('vault-b')
    resolve([oldTraining])
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
      resolve([{ id: 'old', status: 'active' } as TrainingRead])
      await pending
      expect(store.activeTrainings.size).toBe(0)
      expect(store.error).toBeNull()
      expect(store.isLoading).toBe(false)
    }
  )

  for (const action of ['start', 'cancel', 'complete', 'dweller', 'room', 'progress'] as const) {
    it.each(['resolve', 'reject'] as const)(
      `${action} ignores a late %s after context clear`,
      async (outcome) => {
        const { promise, resolve, reject } = Promise.withResolvers<
          TrainingRead & TrainingProgress
        >()
        const room = Promise.withResolvers<TrainingRead[]>()
        const value = { id: 'old', status: 'active', room_id: 'room-a' } as TrainingRead &
          TrainingProgress
        if (action === 'room')
          vi.mocked(trainingService.getRoomTrainings).mockReturnValueOnce(room.promise)
        else {
          const service = {
            start: trainingService.startTraining,
            cancel: trainingService.cancelTraining,
            complete: trainingService.completeTraining,
            dweller: trainingService.getDwellerTraining,
            progress: trainingService.getTrainingProgress,
          }[action]
          vi.mocked(service).mockReturnValueOnce(promise)
        }
        const store = useTrainingStore()
        const actions = {
          start: () => store.startTraining('dweller', 'room-a'),
          cancel: () => store.cancelTraining('old'),
          complete: () => store.completeTraining('old'),
          dweller: () => store.fetchDwellerTraining('dweller'),
          room: () => store.fetchRoomTrainings('room-a'),
          progress: () => store.updateTrainingProgress('old'),
        }
        const pending = actions[action]()
        store.clearTrainings()
        if (outcome === 'resolve') {
          if (action === 'room') room.resolve([value])
          else resolve(value)
        } else if (action === 'room') room.reject(new Error('Old failure'))
        else reject(new Error('Old failure'))
        await pending
        expect(store.activeTrainings.size).toBe(0)
        expect(store.trainingHistory).toEqual([])
        expect(store.error).toBeNull()
        expect(toast.error).not.toHaveBeenCalled()
        expect(toast.success).not.toHaveBeenCalled()
      }
    )
  }

  for (const action of ['goal', 'continuous'] as const) {
    it.each(['resolve', 'reject'] as const)(
      `${action} ignores a late %s after clear`,
      async (outcome) => {
        const { promise, resolve, reject } = Promise.withResolvers<
          TrainingRead & components['schemas']['Vault']
        >()
        if (action === 'goal')
          vi.mocked(trainingService.setTrainingGoal).mockReturnValueOnce(promise)
        else vi.mocked(trainingService.setContinuousTraining).mockReturnValueOnce(promise)
        const store = useTrainingStore()
        const pending =
          action === 'goal'
            ? store.setTrainingGoal('old', 7)
            : store.setContinuousTraining('vault-a', true)
        store.clearTrainings()
        if (outcome === 'reject') reject(new Error('Old failure'))
        else
          resolve({ id: 'old', goal_stat_value: 7, continuous_training: true } as TrainingRead &
            components['schemas']['Vault'])
        expect(await pending).toBe(false)
        expect(toast.error).not.toHaveBeenCalled()
        expect(toast.success).not.toHaveBeenCalled()
      }
    )
  }

  it('saves only the selected dweller goal and keeps the saved value on failure', async () => {
    useAuthStore().token = 'token'
    const store = useTrainingStore()
    store.activeTrainings.set('t1', { id: 't1', goal_stat_value: 10 } as any)
    store.activeTrainings.set('t2', { id: 't2', goal_stat_value: 10 } as any)
    vi.mocked(trainingService.setTrainingGoal).mockResolvedValueOnce({
      id: 't1',
      goal_stat_value: 7,
    } as any)
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
      vaultStore.loadedVaults['v1'] = { id: 'v1', continuous_training: true } as any
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
      vaultStore.loadedVaults['v1'] = { id: 'v1', continuous_training: false } as any
      let finish!: (value: any) => void
      vi.mocked(trainingService.setContinuousTraining).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finish = resolve
          })
      )
      const store = useTrainingStore()
      const pending = store.setContinuousTraining('v1', true)
      expect(store.isSettingContinuousTraining).toBe(true)
      expect(await store.setContinuousTraining('v1', true)).toBe(false)
      expect(trainingService.setContinuousTraining).toHaveBeenCalledTimes(1)
      auth.sessionGeneration += 1
      finish({ continuous_training: true })
      expect(await pending).toBe(false)
      expect(vaultStore.loadedVaults['v1'].continuous_training).toBe(false)
    })
  })

  describe('fetchVaultTrainings', () => {
    it('should fetch vault trainings and populate activeTrainings', async () => {
      const mockTrainings = [
        {
          id: 't1',
          dweller_id: 'd1',
          room_id: 'r1',
          status: 'active',
          stat_being_trained: 'strength',
          estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
        },
        {
          id: 't2',
          dweller_id: 'd2',
          room_id: 'r2',
          status: 'active',
          stat_being_trained: 'endurance',
          estimated_completion_at: new Date(Date.now() + 7200000).toISOString(),
        },
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
      const mockTrainings = [
        {
          id: 't1',
          dweller_id: 'd1',
          room_id: 'r1',
          status: 'completed',
          stat_being_trained: 'strength',
          estimated_completion_at: new Date().toISOString(),
        },
        {
          id: 't2',
          dweller_id: 'd2',
          room_id: 'r2',
          status: 'cancelled',
          stat_being_trained: 'endurance',
          estimated_completion_at: new Date().toISOString(),
        },
      ]
      vi.mocked(trainingService.getVaultTrainings).mockResolvedValueOnce(mockTrainings)

      const store = useTrainingStore()
      await store.fetchVaultTrainings('vault-1')

      expect(store.activeTrainings.size).toBe(0)
    })
  })

  describe('startTraining', () => {
    it('should start training and add to activeTrainings', async () => {
      const mockTraining = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
      }
      vi.mocked(trainingService.startTraining).mockResolvedValueOnce(mockTraining)

      const store = useTrainingStore()
      const result = await store.startTraining('d1', 'r1')

      expect(trainingService.startTraining).toHaveBeenCalledWith('d1', 'r1')
      expect(result).toEqual(mockTraining)
      expect(store.activeTrainings.get('t1')).toEqual(mockTraining)
    })

    it('should return null on error', async () => {
      vi.mocked(trainingService.startTraining).mockRejectedValueOnce(new Error('API error'))

      const store = useTrainingStore()
      const result = await store.startTraining('d1', 'r1')

      expect(result).toBeNull()
      expect(getErrorMessage).toHaveBeenCalled()
    })
  })

  describe('cancelTraining', () => {
    it('should cancel training and move to history', async () => {
      const mockCancelled = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'cancelled',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
      }
      vi.mocked(trainingService.cancelTraining).mockResolvedValueOnce(mockCancelled)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', { ...mockCancelled, status: 'active' })

      const result = await store.cancelTraining('t1')

      expect(trainingService.cancelTraining).toHaveBeenCalledWith('t1')
      expect(result).toBe(true)
      expect(store.activeTrainings.has('t1')).toBe(false)
      expect(store.trainingHistory).toContainEqual(mockCancelled)
    })

    it('should return false on error', async () => {
      vi.mocked(trainingService.cancelTraining).mockRejectedValueOnce(new Error('API error'))

      const store = useTrainingStore()
      const result = await store.cancelTraining('t1')

      expect(result).toBe(false)
    })
  })

  describe('completeTraining', () => {
    it('should complete training and move to history', async () => {
      const mockCompleted = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'completed',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
        progress: 1.0,
        completed_at: new Date().toISOString(),
      }
      vi.mocked(trainingService.completeTraining).mockResolvedValueOnce(mockCompleted)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', {
        ...mockCompleted,
        status: 'active',
        progress: 0.5,
        completed_at: undefined,
      })

      const result = await store.completeTraining('t1')

      expect(trainingService.completeTraining).toHaveBeenCalledWith('t1')
      expect(result).toBe(true)
      expect(store.activeTrainings.has('t1')).toBe(false)
      expect(store.trainingHistory).toContainEqual(mockCompleted)
    })

    it('should return false on error', async () => {
      vi.mocked(trainingService.completeTraining).mockRejectedValueOnce(new Error('API error'))

      const store = useTrainingStore()
      const result = await store.completeTraining('t1')

      expect(result).toBe(false)
    })
  })

  describe('fetchDwellerTraining', () => {
    it('should add active training to map', async () => {
      const mockTraining = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
      }
      vi.mocked(trainingService.getDwellerTraining).mockResolvedValueOnce(mockTraining)

      const store = useTrainingStore()
      await store.fetchDwellerTraining('d1')

      expect(store.activeTrainings.get('t1')).toEqual(mockTraining)
    })

    it('should remove completed training from map', async () => {
      const mockTraining = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'completed',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
      }
      vi.mocked(trainingService.getDwellerTraining).mockResolvedValueOnce(mockTraining)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', { ...mockTraining, status: 'active' })

      await store.fetchDwellerTraining('d1')

      expect(store.activeTrainings.has('t1')).toBe(false)
    })
  })

  describe('fetchRoomTrainings', () => {
    it('should fetch room trainings and update map', async () => {
      const mockTrainings = [
        {
          id: 't1',
          dweller_id: 'd1',
          room_id: 'r1',
          status: 'active',
          stat_being_trained: 'agility',
          estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
        },
      ]
      vi.mocked(trainingService.getRoomTrainings).mockResolvedValueOnce(mockTrainings)

      const store = useTrainingStore()
      store.activeTrainings.set('previous-round', {
        id: 'previous-round',
        room_id: 'r1',
        status: 'active',
      } as any)
      store.activeTrainings.set('other-room', {
        id: 'other-room',
        room_id: 'r2',
        status: 'active',
      } as any)
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
      const result = await store.fetchRoomTrainings('r1')

      expect(result).toEqual([])
    })
  })

  describe('updateTrainingProgress', () => {
    it('should update active training in map', async () => {
      const mockProgress = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
        progress: 50,
      }
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockProgress)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date(Date.now() + 3600000).toISOString(),
      })

      await store.updateTrainingProgress('t1')

      expect(store.activeTrainings.get('t1')).toEqual(mockProgress)
    })

    it('should move completed training to history', async () => {
      const mockCompleted = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'completed',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
        progress: 100,
      }
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockCompleted)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
      })

      await store.updateTrainingProgress('t1')

      expect(store.activeTrainings.has('t1')).toBe(false)
      expect(store.trainingHistory).toContainEqual(mockCompleted)
    })

    it('should remove cancelled training', async () => {
      const mockCancelled = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'cancelled',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
      }
      vi.mocked(trainingService.getTrainingProgress).mockResolvedValueOnce(mockCancelled)

      const store = useTrainingStore()
      store.activeTrainings.set('t1', { ...mockCancelled, status: 'active' } as any)

      await store.updateTrainingProgress('t1')

      expect(store.activeTrainings.has('t1')).toBe(false)
    })
  })

  describe('Getters', () => {
    it('allActiveTrainings returns array from map', () => {
      const store = useTrainingStore()
      const training = {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
      }
      store.activeTrainings.set('t1', training)

      expect(store.allActiveTrainings).toHaveLength(1)
      expect(store.allActiveTrainings[0]).toEqual(training)
    })

    it('getTrainingByDweller returns training for dweller', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'agility',
        estimated_completion_at: new Date().toISOString(),
      })

      expect(store.getTrainingByDweller('d1')).toBeTruthy()
      expect(store.getTrainingByDweller('nonexistent')).toBeUndefined()
    })

    it('getTrainingsByRoom returns trainings for room', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'agility',
        estimated_completion_at: new Date().toISOString(),
      })
      store.activeTrainings.set('t2', {
        id: 't2',
        dweller_id: 'd2',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'luck',
        estimated_completion_at: new Date().toISOString(),
      })
      store.activeTrainings.set('t3', {
        id: 't3',
        dweller_id: 'd3',
        room_id: 'r2',
        status: 'active',
        stat_being_trained: 'perception',
        estimated_completion_at: new Date().toISOString(),
      })

      const roomTrainings = store.getTrainingsByRoom('r1')
      expect(roomTrainings).toHaveLength(2)
    })

    it('isDwellerTraining returns true for active training', () => {
      const store = useTrainingStore()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: new Date().toISOString(),
      })

      expect(store.isDwellerTraining('d1')).toBe(true)
      expect(store.isDwellerTraining('nonexistent')).toBe(false)
    })

    it('completingSoon filters trainings ending within 10 minutes', () => {
      const store = useTrainingStore()
      const soon = new Date(Date.now() + 300000).toISOString()
      const later = new Date(Date.now() + 86400000).toISOString()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'active',
        stat_being_trained: 'strength',
        estimated_completion_at: soon,
      })
      store.activeTrainings.set('t2', {
        id: 't2',
        dweller_id: 'd2',
        room_id: 'r2',
        status: 'active',
        stat_being_trained: 'endurance',
        estimated_completion_at: later,
      })

      expect(store.completingSoon).toHaveLength(1)
      expect(store.completingSoon[0].id).toBe('t1')
    })

    it('completingSoon excludes non-active trainings', () => {
      const store = useTrainingStore()
      const soon = new Date(Date.now() + 300000).toISOString()
      store.activeTrainings.set('t1', {
        id: 't1',
        dweller_id: 'd1',
        room_id: 'r1',
        status: 'completed',
        stat_being_trained: 'strength',
        estimated_completion_at: soon,
      })

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
