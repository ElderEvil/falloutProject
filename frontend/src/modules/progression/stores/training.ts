import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'
import type { components } from '@/core/types/api.generated'
import * as trainingService from '../services/trainingService'
import { useToast } from '@/core/composables/useToast'
import { notifyErrorOnce, getErrorMessage, handleStoreError } from '@/core/utils/errorHandler'
import { parseUtcMs } from '@/core/utils/time'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

export const useTrainingStore = defineStore('training', () => {
  const toast = useToast()
  const authStore = useAuthStore()

  // State
  const activeTrainings = ref<Map<string, TrainingRead | TrainingProgress>>(new Map())
  const trainingHistory = ref<(TrainingRead | TrainingProgress)[]>([])
  const error = ref<string | null>(null)
  const savingGoals = ref(new Set<string>())
  const isSettingContinuousTraining = ref(false)
  const isLoading = ref(false)
  let contextVersion = 0
  let vaultRequest = 0
  let trainingVaultId: string | null = null

  watch(
    [() => authStore.sessionGeneration, () => useVaultStore().activeVaultId],
    () => {
      trainingVaultId = null
      clearTrainings()
    },
    { flush: 'sync' }
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
      const completionTime = parseUtcMs(training.estimated_completion_at)
      return completionTime - now <= tenMinutes && completionTime > now
    })
  })

  // Actions
  async function setContinuousTraining(vaultId: string, enabled: boolean): Promise<boolean> {
    if (isSettingContinuousTraining.value) return false
    isSettingContinuousTraining.value = true
    const version = contextVersion
    const session = authStore.sessionGeneration
    try {
      const saved = await trainingService.setContinuousTraining(vaultId, enabled)
      if (version !== contextVersion || session !== authStore.sessionGeneration) return false
      const vault = useVaultStore().loadedVaults[vaultId]
      if (vault) vault.continuous_training = saved.continuous_training
      toast.success(
        saved.continuous_training
          ? 'Continuous training on. Repeat to individual goals.'
          : 'Continuous training off. Current rounds will finish.'
      )
      return true
    } catch (err: unknown) {
      if (version !== contextVersion || session !== authStore.sessionGeneration) return false
      handleStoreError(err, 'Failed to update continuous training')
      return false
    } finally {
      isSettingContinuousTraining.value = false
    }
  }

  async function setTrainingGoal(trainingId: string, goal: number): Promise<boolean> {
    if (savingGoals.value.has(trainingId)) return false
    savingGoals.value.add(trainingId)
    const version = contextVersion
    const session = authStore.sessionGeneration
    try {
      const saved = await trainingService.setTrainingGoal(trainingId, goal)
      if (version !== contextVersion || session !== authStore.sessionGeneration) return false
      const current = activeTrainings.value.get(trainingId)
      if (current) Object.assign(current, saved)
      return true
    } catch (err: unknown) {
      if (version !== contextVersion || session !== authStore.sessionGeneration) return false
      handleStoreError(err, 'Failed to save training goal')
      return false
    } finally {
      savingGoals.value.delete(trainingId)
    }
  }

  async function startTraining(dwellerId: string, roomId: string): Promise<TrainingRead | null> {
    const version = contextVersion
    try {
      const training = await trainingService.startTraining(dwellerId, roomId)
      if (version !== contextVersion) return null
      activeTrainings.value.set(training.id!, training)
      return training
    } catch (err: unknown) {
      if (version !== contextVersion) return null
      notifyErrorOnce(err, getErrorMessage(err))
      return null
    }
  }

  async function cancelTraining(trainingId: string): Promise<boolean> {
    const version = contextVersion
    try {
      const training = await trainingService.cancelTraining(trainingId)
      if (version !== contextVersion) return false
      activeTrainings.value.delete(trainingId)
      trainingHistory.value.push(training)
      toast.success('Training cancelled')
      return true
    } catch (err: unknown) {
      if (version !== contextVersion) return false
      notifyErrorOnce(err, getErrorMessage(err))
      return false
    }
  }

  async function completeTraining(trainingId: string): Promise<boolean> {
    const version = contextVersion
    try {
      const training = await trainingService.completeTraining(trainingId)
      if (version !== contextVersion) return false
      activeTrainings.value.delete(trainingId)
      trainingHistory.value.push(training)
      return true
    } catch (err: unknown) {
      if (version !== contextVersion) return false
      notifyErrorOnce(err, getErrorMessage(err))
      return false
    }
  }

  async function fetchDwellerTraining(dwellerId: string): Promise<void> {
    const version = contextVersion
    try {
      const training = await trainingService.getDwellerTraining(dwellerId)
      if (version !== contextVersion) return
      if (training && training.id) {
        if (training.status === 'active') {
          activeTrainings.value.set(training.id, training)
        } else {
          activeTrainings.value.delete(training.id)
        }
      }
    } catch (err: unknown) {
      if (version !== contextVersion) return
      notifyErrorOnce(err, getErrorMessage(err))
    }
  }

  async function fetchVaultTrainings(vaultId: string): Promise<void> {
    if (trainingVaultId !== vaultId) {
      clearTrainings()
      trainingVaultId = vaultId
    }
    const version = contextVersion
    const request = ++vaultRequest
    isLoading.value = true
    error.value = null
    try {
      const trainings = await trainingService.getVaultTrainings(vaultId)
      if (version !== contextVersion || request !== vaultRequest) return
      activeTrainings.value.clear()
      for (const training of trainings) {
        if (training.id && training.status === 'active')
          activeTrainings.value.set(training.id, training)
      }
    } catch (err: unknown) {
      if (version !== contextVersion || request !== vaultRequest) return
      error.value = handleStoreError(err, 'Failed to fetch vault trainings')
    } finally {
      if (request === vaultRequest) isLoading.value = false
    }
  }

  async function fetchRoomTrainings(roomId: string): Promise<TrainingRead[]> {
    const version = contextVersion
    try {
      const trainings = await trainingService.getRoomTrainings(roomId)
      if (version !== contextVersion) return []

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
      if (version !== contextVersion) return []
      notifyErrorOnce(err, getErrorMessage(err))
      return []
    }
  }

  async function updateTrainingProgress(trainingId: string): Promise<void> {
    const version = contextVersion
    try {
      const progress = await trainingService.getTrainingProgress(trainingId)
      if (version !== contextVersion) return

      if (progress.id) {
        if (progress.status === 'active') {
          activeTrainings.value.set(progress.id, progress)
        } else if (progress.status === 'completed') {
          // Move to history and remove from active
          activeTrainings.value.delete(progress.id)
          trainingHistory.value.push(progress)
        } else if (progress.status === 'cancelled') {
          activeTrainings.value.delete(progress.id)
        }
      }
    } catch (err: unknown) {
      if (version !== contextVersion) return
      notifyErrorOnce(err, getErrorMessage(err))
    }
  }

  async function refreshAllTrainings(vaultId: string): Promise<void> {
    await fetchVaultTrainings(vaultId)
  }

  function clearTrainings(): void {
    contextVersion++
    vaultRequest++
    isLoading.value = false
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
