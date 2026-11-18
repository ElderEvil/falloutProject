import { api, apiGet, apiPost, apiPut } from '@/core/utils/api'
import type { components } from '@/core/types/api.generated'

type TrainingRead = components['schemas']['TrainingRead']
type TrainingProgress = components['schemas']['TrainingProgress']

export async function setContinuousTraining(vaultId: string, enabled: boolean) {
  return apiPut<components['schemas']['Vault']>(`/api/v1/vaults/${vaultId}`, {
    continuous_training: enabled,
  })
}

/**
 * Start training a dweller in a training room
 * @param dwellerId - UUID of the dweller to train
 * @param roomId - UUID of the training room
 * @returns Created training session
 */
export async function startTraining(dwellerId: string, roomId: string): Promise<TrainingRead> {
  return apiPost<TrainingRead>('/api/v1/training/start', null, {
    params: { dweller_id: dwellerId, room_id: roomId },
  })
}

/**
 * Get active training for a dweller
 * @param dwellerId - UUID of the dweller
 * @returns Active training session or null
 */
export async function getDwellerTraining(dwellerId: string): Promise<TrainingRead | null> {
  return apiGet<TrainingRead | null>(`/api/v1/training/dweller/${dwellerId}`)
}

/**
 * Get all active training sessions in a vault
 * @param vaultId - UUID of the vault
 * @returns List of active training sessions
 */
export async function getVaultTrainings(vaultId: string): Promise<TrainingRead[]> {
  return apiGet<TrainingRead[]>(`/api/v1/training/vault/${vaultId}`)
}

/**
 * Get training progress details
 * @param trainingId - UUID of the training session
 * @returns Training session with progress information
 */
export async function getTrainingProgress(trainingId: string): Promise<TrainingProgress> {
  return apiGet<TrainingProgress>(`/api/v1/training/${trainingId}`)
}

/**
 * Cancel an active training session
 * @param trainingId - UUID of the training session
 * @returns Cancelled training session
 */
export async function cancelTraining(trainingId: string): Promise<TrainingRead> {
  return apiPost<TrainingRead>(`/api/v1/training/${trainingId}/cancel`)
}

/**
 * Complete a training session, granting the stat increase to the dweller
 * @param trainingId - UUID of the training session to complete
 * @returns Completed training session
 */
export async function completeTraining(trainingId: string): Promise<TrainingRead> {
  return apiPost<TrainingRead>(`/api/v1/training/${trainingId}/complete`)
}

/**
 * Get all active training sessions in a room
 * @param roomId - UUID of the room
 * @returns List of active training sessions in the room
 */
export async function getRoomTrainings(roomId: string): Promise<TrainingRead[]> {
  return apiGet<TrainingRead[]>(`/api/v1/training/room/${roomId}`)
}

export async function setTrainingGoal(trainingId: string, goal: number): Promise<TrainingRead> {
  return api.patch<TrainingRead>(`/api/v1/training/${trainingId}/goal`, {
    goal_stat_value: goal,
  })
}
