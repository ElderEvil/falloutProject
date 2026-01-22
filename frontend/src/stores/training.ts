import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { components } from '@/core/types/api.generated'
import * as trainingService from '@/services/trainingService'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/types/utils'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

export const useTrainingStore = defineStore('training', () => {
  const toast = useToast()

  // State
  const activeTrainings = ref<Map<string, TrainingRead | TrainingProgress>>(new Map())
  const trainingHistory = ref<(TrainingRead | TrainingProgress)[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const allActiveTrainings = computed(() => Array.from(activeTrainings.value.values()))

  const getTrainingByDweller = computed(() => (dwellerId: string) => {
    return Array.from(activeTrainings.value.values()).find(
      (t) => t.dweller_id === dwellerId
    )
  })

  const getTrainingsByRoom = computed(() => (roomId: string) => {
    return Array.from(activeTrainings.value.values()).filter(
      (t) => t.room_id === roomId
    )
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
      console.error('Failed to start training:', err)
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
      console.error('Failed to cancel training:', err)
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
      console.error('Failed to fetch dweller training:', err)
    }
  }

  async function fetchVaultTrainings(vaultId: string, token: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const trainings = await trainingService.getVaultTrainings(vaultId, token)

      // Clear and rebuild active trainings map
      activeTrainings.value.clear()
      trainings.forEach((training) => {
        if (training.id && training.status === 'active') {
          activeTrainings.value.set(training.id, training)
        }
      })
    } catch (err: unknown) {
      console.error('Failed to fetch vault trainings:', err)
      error.value = getErrorMessage(err)
    } finally {
      isLoading.value = false
    }
  }

  async function fetchRoomTrainings(roomId: string, token: string): Promise<TrainingRead[]> {
    try {
      const trainings = await trainingService.getRoomTrainings(roomId, token)

      // Update active trainings map with room trainings
      trainings.forEach((training) => {
        if (training.id && training.status === 'active') {
          activeTrainings.value.set(training.id, training)
        }
      })

      return trainings
    } catch (err: unknown) {
      console.error('Failed to fetch room trainings:', err)
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
      console.error('Failed to update training progress:', err)
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

    // Getters
    allActiveTrainings,
    getTrainingByDweller,
    getTrainingsByRoom,
    isDwellerTraining,
    completingSoon,

    // Actions
    startTraining,
    cancelTraining,
    fetchDwellerTraining,
    fetchVaultTrainings,
    fetchRoomTrainings,
    updateTrainingProgress,
    refreshAllTrainings,
    clearTrainings
  }
})
