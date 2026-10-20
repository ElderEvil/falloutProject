import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { components } from '@/core/types/api.generated'
import * as trainingService from '../services/trainingService'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { useAsyncAction } from '@/core/composables/useAsyncAction'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

export const useTrainingStore = defineStore('training', () => {
  const toast = useToast()

  // State
  const activeTrainings = ref<Map<string, TrainingRead | TrainingProgress>>(new Map())
  const trainingHistory = ref<(TrainingRead | TrainingProgress)[]>([])
  const error = ref<string | null>(null)
  const savingGoals = ref(new Set<string>())
  const isSettingContinuousTraining = ref(false)
  const {
    run: runFetchVaultTrainings,
    isLoading,
    error: fetchVaultTrainingsError,
  } = useAsyncAction(
    async (vaultId: string, token: string) => {
      const trainings = await trainingService.getVaultTrainings(vaultId, token)
      activeTrainings.value.clear()
      trainings.forEach((training) => {
        if (training.id && training.status === 'active')
          activeTrainings.value.set(training.id, training)
      })
      return true
    },
    { context: 'Failed to fetch vault trainings', showToast: false }
  )

  // Getters
  const allActiveTrainings = computed(() => Array.from(activeTrainings.value.values()))

  const getTrainingByDweller = computed(() => (dwellerId: string) => {
    return Array.from(activeTrainings.value.values()).find((t) => t.dweller_id === dwellerId)
  })

  const getTrainingsByRoom = computed(() => (roomId: string) => {
    return Array.from(activeTrainings.value.values()).filter((t) => t.room_id === roomId)
  })

  const isDwellerTraining = computed(() => (dwellerId: string) => {
    return Array.from(activeTrainings.value.values()).some(
      (t) => t.dweller_id === dwellerId && t.status === 'active'
    )
  })

  const completingSoon = computed(() => {
    const now = new Date().getTime()
    const tenMinutes = 10 * 60 * 1000 // 10 minutes in milliseconds

    return Array.from(activeTrainings.value.values()).filter((training) => {
      if (training.status !== 'active') return false
      const completionTime = new Date(training.estimated_completion_at).getTime()
      return completionTime - now <= tenMinutes && completionTime > now
    })
  })

  // Actions
  async function setContinuousTraining(
    vaultId: string,
    enabled: boolean,
    token: string
  ): Promise<boolean> {
    if (isSettingContinuousTraining.value) return false
    isSettingContinuousTraining.value = true
    try {
      const saved = await trainingService.setContinuousTraining(vaultId, enabled, token)
      if (useAuthStore().token !== token) return false
      const vault = useVaultStore().loadedVaults[vaultId]
      if (vault) vault.continuous_training = saved.continuous_training
      toast.success(
        saved.continuous_training
          ? 'Continuous training on. Repeat to individual goals.'
          : 'Continuous training off. Current rounds will finish.'
      )
      return true
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to update continuous training')
      return false
    } finally {
      isSettingContinuousTraining.value = false
    }
  }

  async function setTrainingGoal(
    trainingId: string,
    goal: number,
    token: string
  ): Promise<boolean> {
    if (savingGoals.value.has(trainingId)) return false
    savingGoals.value.add(trainingId)
    try {
      const saved = await trainingService.setTrainingGoal(trainingId, goal, token)
      if (useAuthStore().token !== token) return false
      const current = activeTrainings.value.get(trainingId)
      if (current) Object.assign(current, saved)
      return true
    } catch (err: unknown) {
      handleStoreError(err, 'Failed to save training goal')
      return false
    } finally {
      savingGoals.value.delete(trainingId)
    }
  }

  async function startTraining(
    dwellerId: string,
    roomId: string,
    token: string
  ): Promise<TrainingRead | null> {
    try {
      const training = await trainingService.startTraining(dwellerId, roomId, token)
      activeTrainings.value.set(training.id!, training)
      return training
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
      return null
    }
  }

  async function cancelTraining(trainingId: string, token: string): Promise<boolean> {
    try {
      const training = await trainingService.cancelTraining(trainingId, token)
      activeTrainings.value.delete(trainingId)
      trainingHistory.value.push(training)
      toast.success('Training cancelled')
      return true
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
      return false
    }
  }

  async function completeTraining(trainingId: string, token: string): Promise<boolean> {
    try {
      const training = await trainingService.completeTraining(trainingId, token)
      activeTrainings.value.delete(trainingId)
      trainingHistory.value.push(training)
      toast.success(`Training completed! ${training.stat_being_trained} increased!`)
      return true
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
      return false
    }
  }

  async function fetchDwellerTraining(dwellerId: string, token: string): Promise<void> {
    try {
      const training = await trainingService.getDwellerTraining(dwellerId, token)
      if (training && training.id) {
        if (training.status === 'active') {
          activeTrainings.value.set(training.id, training)
        } else {
          activeTrainings.value.delete(training.id)
        }
      }
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
    }
  }

  async function fetchVaultTrainings(vaultId: string, token: string): Promise<void> {
    error.value = null
    const result = await runFetchVaultTrainings(vaultId, token)
    if (!result) error.value = fetchVaultTrainingsError.value
  }

  async function fetchRoomTrainings(roomId: string, token: string): Promise<TrainingRead[]> {
    try {
      const trainings = await trainingService.getRoomTrainings(roomId, token)

      // A completed round may already have a different successor id.
      for (const [id, training] of activeTrainings.value) {
        if (training.room_id === roomId) activeTrainings.value.delete(id)
      }
      trainings.forEach((training) => {
        if (training.id && training.status === 'active') {
          activeTrainings.value.set(training.id, training)
        }
      })

      return trainings
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
      return []
    }
  }

  async function updateTrainingProgress(trainingId: string, token: string): Promise<void> {
    try {
      const progress = await trainingService.getTrainingProgress(trainingId, token)

      if (progress.id) {
        if (progress.status === 'active') {
          activeTrainings.value.set(progress.id, progress)
        } else if (progress.status === 'completed') {
          // Move to history and remove from active
          activeTrainings.value.delete(progress.id)
          trainingHistory.value.push(progress)

          // Show completion notification
          toast.success(`Training completed! ${progress.stat_being_trained} increased!`)
        } else if (progress.status === 'cancelled') {
          activeTrainings.value.delete(progress.id)
        }
      }
    } catch (err: unknown) {
      toast.error(getErrorMessage(err))
    }
  }

  async function refreshAllTrainings(vaultId: string, token: string): Promise<void> {
    await fetchVaultTrainings(vaultId, token)
  }

  function clearTrainings(): void {
    activeTrainings.value.clear()
    trainingHistory.value = []
    error.value = null
  }

  return {
    // State
    activeTrainings,
    trainingHistory,
    isLoading,
    error,
    isSettingContinuousTraining,
    setContinuousTraining,
    savingGoals,
    setTrainingGoal,

    // Getters
    allActiveTrainings,
    getTrainingByDweller,
    getTrainingsByRoom,
    isDwellerTraining,
    completingSoon,

    // Actions
    startTraining,
    cancelTraining,
    completeTraining,
    fetchDwellerTraining,
    fetchVaultTrainings,
    fetchRoomTrainings,
    updateTrainingProgress,
    refreshAllTrainings,
    clearTrainings,
  }
})
